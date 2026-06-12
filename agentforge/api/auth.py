"""Pluggable authentication: turn a request into a verified ``Principal``.

``AUTH_BACKEND`` selects the scheme:

- ``"none"`` (default) — no authentication; the caller's ``X-Tenant-ID`` header
  is trusted (dev / single-tenant). ``authenticate`` returns ``None`` so the
  tenant falls back to header / default resolution in ``tenancy``.
- ``"api_key"`` — a static ``<key>:<tenant>`` map (``API_KEYS``). The bearer key
  both authenticates the caller and fixes its tenant.
- ``"oidc"`` — an RS256 JWT validated against a JWKS URL (``OIDC_JWKS_URL``) or a
  static PEM public key (``OIDC_PUBLIC_KEY``); the tenant is read from the
  ``OIDC_TENANT_CLAIM`` claim.

In every authenticated backend the credential *carries* the tenant, so the
``X-Tenant-ID`` header is ignored once auth is on — a caller can only ever act
as the tenant its credential grants. ``authenticate`` either returns a
``Principal`` or raises ``401`` (bad/missing credential) / ``403`` (authenticated
but the credential carries no usable tenant). The returned tenant id is *not*
shape-validated here; ``tenancy.resolve_tenant`` applies the same validation to
both the header and credential paths.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from agentforge.config import Settings, get_settings

_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class Principal:
    """An authenticated caller and the tenant its credential grants."""

    subject: str
    tenant_id: str


def authenticate(request: Request) -> Principal | None:
    """Verify the request's credential and return its ``Principal``.

    Returns ``None`` only for ``AUTH_BACKEND=none`` (no auth configured),
    signalling the caller to fall back to trusted-header tenant resolution.
    Every other backend either returns a ``Principal`` or raises.
    """
    settings = get_settings()
    backend = settings.auth_backend.lower()
    if backend == "none":
        return None
    if backend == "api_key":
        return _authenticate_api_key(request, settings)
    if backend == "oidc":
        return _authenticate_oidc(request, settings)
    raise HTTPException(
        status_code=500, detail=f"Unknown AUTH_BACKEND {settings.auth_backend!r}"
    )


def _bearer_token(request: Request) -> str:
    """Extract the bearer token, or 401 if the Authorization header is absent."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization: Bearer header",
            headers=_BEARER_CHALLENGE,
        )
    return token.strip()


def parse_api_keys(raw: str) -> dict[str, str]:
    """``"<key>:<tenant>,<key>:<tenant>"`` -> ``{key: tenant}``.

    Whitespace and blank entries are ignored; a malformed pair raises so a
    misconfiguration surfaces at startup rather than silently dropping a key.
    """
    mapping: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        key, sep, tenant = entry.partition(":")
        if not sep or not key.strip() or not tenant.strip():
            raise ValueError(
                f"Malformed API_KEYS entry {entry!r}; expected '<key>:<tenant>'"
            )
        mapping[key.strip()] = tenant.strip()
    return mapping


def _authenticate_api_key(request: Request, settings: Settings) -> Principal:
    keys = parse_api_keys(settings.api_keys)
    if not keys:
        raise HTTPException(
            status_code=500, detail="AUTH_BACKEND=api_key but API_KEYS is empty"
        )
    token = _bearer_token(request)
    tenant = keys.get(token)
    if tenant is None:
        raise HTTPException(
            status_code=401, detail="Invalid API key", headers=_BEARER_CHALLENGE
        )
    # Don't echo the secret in the subject; the tenant is identity enough here.
    return Principal(subject=f"apikey:{tenant}", tenant_id=tenant)


def _authenticate_oidc(request: Request, settings: Settings) -> Principal:
    import jwt  # PyJWT

    token = _bearer_token(request)
    try:
        claims = jwt.decode(
            token,
            _oidc_signing_key(settings, token),
            algorithms=["RS256"],
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            options={
                "require": ["exp"],
                "verify_iss": settings.oidc_issuer is not None,
                "verify_aud": settings.oidc_audience is not None,
            },
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401, detail=f"Invalid token: {exc}", headers=_BEARER_CHALLENGE
        ) from exc
    tenant = claims.get(settings.oidc_tenant_claim)
    if not isinstance(tenant, str) or not tenant:
        raise HTTPException(
            status_code=403,
            detail=f"Token has no usable {settings.oidc_tenant_claim!r} claim",
        )
    return Principal(subject=str(claims.get("sub", "")), tenant_id=tenant)


def _oidc_signing_key(settings: Settings, token: str):
    """Resolve the RS256 verification key: JWKS endpoint or a static PEM."""
    if settings.oidc_jwks_url:
        from jwt import PyJWKClient

        return PyJWKClient(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
    if settings.oidc_public_key:
        return settings.oidc_public_key
    raise HTTPException(
        status_code=500,
        detail="AUTH_BACKEND=oidc requires OIDC_JWKS_URL or OIDC_PUBLIC_KEY",
    )
