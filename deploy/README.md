# Deploying AgentForge

`docker compose up` is for local use. This is the path to a real deployment.

## Published images

Every version tag (`vX.Y.Z`) builds and pushes two images to GitHub Container
Registry via [`.github/workflows/release.yml`](../.github/workflows/release.yml):

| Image | Contents |
|---|---|
| `ghcr.io/gridatek/agentforge-api` | FastAPI gateway + agent graph (runs as non-root, port 8000) |
| `ghcr.io/gridatek/agentforge-console` | Angular console built and served by nginx (port 80) |

Each image is tagged with the full version (`0.1.0`), the minor line (`0.1`), the
commit SHA, and `latest`. Cut a release with:

```bash
git tag v0.1.0
git push origin v0.1.0
```

(Or trigger **Release** manually from the Actions tab.) Every PR also *builds*
both images (no push) so a broken Dockerfile fails CI before merge.

## Running the published images

You still need a Postgres+pgvector instance and an embedding/chat provider.

```bash
# Shared network so the console can reach the API by name.
docker network create agentforge-net

docker run -d --name api --network agentforge-net \
  -e DATABASE_URL=postgresql+psycopg://USER:PASS@db-host:5432/agentforge \
  -e CHAT_MODEL=anthropic:claude-opus-4-8 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e EMBEDDING_MODEL=openai:text-embedding-3-small \
  -e EMBEDDING_DIM=1536 \
  -e OPENAI_API_KEY=sk-... \
  -p 8000:8000 \
  ghcr.io/gridatek/agentforge-api:latest

# The console proxies /api to API_UPSTREAM (defaults to api:8000).
docker run -d --name console --network agentforge-net \
  -p 4200:80 ghcr.io/gridatek/agentforge-console:latest
```

The full env contract is in [`.env.example`](../.env.example).

## Ingesting the corpus

Auto-ingest on API startup (`AUTO_INGEST=true`) is meant for the local demo. In
production, run ingestion as a one-shot job against the same image instead, so the
API stays stateless and replica-safe:

```bash
docker run --rm \
  -e DATABASE_URL=... -e EMBEDDING_MODEL=... -e EMBEDDING_DIM=... \
  ghcr.io/gridatek/agentforge-api:latest \
  python -m agentforge.rag.ingest examples/banking-compliance/corpus
```

## Kubernetes

Manifests live under [`k8s/`](k8s/): a `Namespace`, Postgres `StatefulSet`
(swap for managed Postgres in real prod), the API `Deployment` + `Service` (2
replicas, `/health` probes, non-root), the console `Deployment` + `Service`, a
one-shot ingest `Job`, and a template `Ingress`. They're tied together with
Kustomize and schema-validated in CI (`k8s-validate` via kubeconform).

```bash
# 1. Create the namespace + your secret (never commit the filled-in copy).
kubectl apply -f deploy/k8s/namespace.yaml
cp deploy/k8s/secret.example.yaml deploy/k8s/secret.yaml   # gitignored
$EDITOR deploy/k8s/secret.yaml                             # set password + API keys
kubectl apply -f deploy/k8s/secret.yaml

# 2. Deploy the stack (pin a version in kustomization.yaml instead of :latest).
kubectl apply -k deploy/k8s

# 3. Ingest the corpus once the DB is ready.
kubectl -n agentforge rollout status statefulset/db
kubectl apply -f deploy/k8s/ingest-job.yaml
kubectl -n agentforge wait --for=condition=complete job/ingest --timeout=300s
```

Edit `ingress.yaml` host (or delete it and expose the console Service your own
way). The console reverse-proxies `/api` to the API Service same-origin, so only
the console needs to be exposed and there's no build-time API host to set. If the
API runs in a different namespace, point the proxy at it by setting
`API_UPSTREAM` (e.g. `api.other-ns.svc.cluster.local:8000`) on the console
container.
