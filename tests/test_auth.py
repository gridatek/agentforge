"""Pluggable authentication: the AUTH_BACKEND seam in front of tenant resolution.

Covers the three backends offline — ``none`` (trusted header), ``api_key``
(static key->tenant map), and ``oidc`` (RS256 JWT verified against a locally
minted keypair, no network) — plus the guarantee that an authenticated
credential's tenant overrides any X-Tenant-ID the caller sends.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import agentforge.api.auth as auth
import agentforge.api.tenancy as tenancy


class _Req:
    """Minimal Starlette Request stand-in (only ``.headers.get`` is used)."""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or {}


def _settings(**overrides):
    base = dict(
        auth_backend="none",
        api_keys="",
        oidc_jwks_url=None,
        oidc_public_key=None,
        oidc_issuer=None,
        oidc_audience=None,
        oidc_tenant_claim="tenant",
        # consulted by tenancy.resolve_tenant on the none/header path
        default_tenant="default",
        require_tenant=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _use(monkeypatch, **overrides):
    settings = _settings(**overrides)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(tenancy, "get_settings", lambda: settings)
    return settings


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- parse_api_keys ---------------------------------------------------------


def test_parse_api_keys_maps_each_key_to_its_tenant():
    assert auth.parse_api_keys("k1:acme, k2:globex") == {"k1": "acme", "k2": "globex"}


def test_parse_api_keys_ignores_blanks():
    assert auth.parse_api_keys("  ,k1:acme,  ") == {"k1": "acme"}


@pytest.mark.parametrize("raw", ["nocolon", "k1:", ":tenant"])
def test_parse_api_keys_rejects_malformed(raw):
    with pytest.raises(ValueError):
        auth.parse_api_keys(raw)


# --- none backend -----------------------------------------------------------


def test_none_backend_returns_no_principal(monkeypatch):
    _use(monkeypatch, auth_backend="none")
    assert auth.authenticate(_Req(_bearer("anything"))) is None


# --- api_key backend --------------------------------------------------------


def test_api_key_valid_key_yields_its_tenant(monkeypatch):
    _use(monkeypatch, auth_backend="api_key", api_keys="sk-acme:acme,sk-glx:globex")
    principal = auth.authenticate(_Req(_bearer("sk-glx")))
    assert principal is not None
    assert principal.tenant_id == "globex"


def test_api_key_invalid_key_is_401(monkeypatch):
    _use(monkeypatch, auth_backend="api_key", api_keys="sk-acme:acme")
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer("wrong")))
    assert exc.value.status_code == 401


def test_api_key_missing_header_is_401(monkeypatch):
    _use(monkeypatch, auth_backend="api_key", api_keys="sk-acme:acme")
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req())
    assert exc.value.status_code == 401


def test_api_key_empty_config_is_500(monkeypatch):
    _use(monkeypatch, auth_backend="api_key", api_keys="")
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer("sk-acme")))
    assert exc.value.status_code == 500


def test_api_key_tenant_overrides_x_tenant_header(monkeypatch):
    # The credential carries the tenant; a spoofed X-Tenant-ID must not win.
    _use(monkeypatch, auth_backend="api_key", api_keys="sk-acme:acme")
    headers = {**_bearer("sk-acme"), "X-Tenant-ID": "globex"}
    assert tenancy.resolve_tenant(_Req(headers)) == "acme"


def test_unknown_backend_is_500(monkeypatch):
    _use(monkeypatch, auth_backend="weird")
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer("x")))
    assert exc.value.status_code == 500


# --- oidc backend (RS256, locally minted keypair) ---------------------------


@pytest.fixture(scope="module")
def rsa_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _sign(private_pem: str, claims: dict) -> str:
    import jwt

    return jwt.encode(claims, private_pem, algorithm="RS256")


def _exp(minutes: int = 5) -> int:
    now = dt.datetime.now(tz=dt.timezone.utc)
    return int((now + dt.timedelta(minutes=minutes)).timestamp())


def test_oidc_valid_token_yields_claim_tenant(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _use(monkeypatch, auth_backend="oidc", oidc_public_key=public_pem)
    token = _sign(private_pem, {"sub": "u-1", "tenant": "acme", "exp": _exp()})
    principal = auth.authenticate(_Req(_bearer(token)))
    assert principal is not None
    assert principal.subject == "u-1"
    assert principal.tenant_id == "acme"


def test_oidc_custom_tenant_claim(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _use(
        monkeypatch,
        auth_backend="oidc",
        oidc_public_key=public_pem,
        oidc_tenant_claim="org_id",
    )
    token = _sign(private_pem, {"org_id": "globex", "exp": _exp()})
    assert auth.authenticate(_Req(_bearer(token))).tenant_id == "globex"


def test_oidc_bad_signature_is_401(monkeypatch, rsa_keys):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_pem, public_pem = rsa_keys
    # A different private key signs — verification against public_pem must fail.
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    _use(monkeypatch, auth_backend="oidc", oidc_public_key=public_pem)
    token = _sign(other_pem, {"tenant": "acme", "exp": _exp()})
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer(token)))
    assert exc.value.status_code == 401


def test_oidc_expired_token_is_401(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _use(monkeypatch, auth_backend="oidc", oidc_public_key=public_pem)
    token = _sign(private_pem, {"tenant": "acme", "exp": _exp(minutes=-5)})
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer(token)))
    assert exc.value.status_code == 401


def test_oidc_missing_tenant_claim_is_403(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _use(monkeypatch, auth_backend="oidc", oidc_public_key=public_pem)
    token = _sign(private_pem, {"sub": "u-1", "exp": _exp()})
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer(token)))
    assert exc.value.status_code == 403


def test_oidc_wrong_issuer_is_401(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _use(
        monkeypatch,
        auth_backend="oidc",
        oidc_public_key=public_pem,
        oidc_issuer="https://expected.example",
    )
    token = _sign(
        private_pem, {"tenant": "acme", "iss": "https://attacker.example", "exp": _exp()}
    )
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer(token)))
    assert exc.value.status_code == 401


def test_oidc_without_key_or_jwks_is_500(monkeypatch, rsa_keys):
    private_pem, _ = rsa_keys
    _use(monkeypatch, auth_backend="oidc")  # neither jwks_url nor public_key
    token = _sign(private_pem, {"tenant": "acme", "exp": _exp()})
    with pytest.raises(HTTPException) as exc:
        auth.authenticate(_Req(_bearer(token)))
    assert exc.value.status_code == 500


# --- tenancy integration ----------------------------------------------------


def test_resolve_tenant_rejects_ill_formed_credential_tenant(monkeypatch):
    # A credential carrying a tenant with the composite delimiter is a 400.
    _use(monkeypatch, auth_backend="api_key", api_keys="sk:bad:tenant")
    with pytest.raises(HTTPException) as exc:
        tenancy.resolve_tenant(_Req(_bearer("sk")))
    assert exc.value.status_code == 400
