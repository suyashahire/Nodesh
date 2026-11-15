# Deploy Nodesh

## Free demo: Render API + Vercel frontend

The free Render service uses temporary SQLite and uploads. Data is lost when the
service restarts, redeploys, or spins down after inactivity. Cold starts can take
about a minute. Closing a browser tab does not delete server data.

### 1. Push the repository

Push the deployment changes to `main` at https://github.com/suyashahire/Nodesh.
Do not upload `.env`, local databases, or uploaded documents.

### 2. Deploy the API

Open https://dashboard.render.com/select-repo?type=blueprint and select Nodesh.
Render reads `render.yaml`; choose the Free plan. Enter `http://localhost:3000`
for `WEB_ORIGIN` initially, then replace it with the frontend origin in step 4.
No separate database is needed for this demo.

For manual Web Service setup:

| Setting | Value |
| --- | --- |
| Runtime | Python |
| Root directory | `apps/api` |
| Build command | `pip install -e .` |
| Start command | `alembic upgrade head && uvicorn nodesh_api.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/healthz` |
| Plan | Free |
| `PYTHON_VERSION` | `3.11.9` |
| `DATABASE_URL` | `sqlite:////tmp/nodesh.db` |
| `UPLOADS_DIR` | `/tmp/nodesh-uploads` |
| `WEB_ORIGIN` | Actual frontend origin, no trailing slash |

Wait for Live, then open the actual API URL followed by `/healthz`.
Expected response: `{"status":"ok","service":"nodesh-api"}`.

### 3. Deploy the frontend

Open https://vercel.com/new and import Nodesh.

| Setting | Value |
| --- | --- |
| Framework | Next.js |
| Root directory | `apps/web` |
| Build/install commands | Framework defaults |
| `NEXT_PUBLIC_API_BASE_URL` | Actual Render URL, including `https://` |

### 4. Connect and verify

Set Render's `WEB_ORIGIN` to the actual Vercel origin and redeploy the API.
Trusted origins can be comma-separated; avoid `*` for the public deployment.
If the API URL changes, update the Vercel variable and rebuild the frontend.

Open the frontend, upload two small documents, and confirm automatic graph
analysis, concept summaries, relationship evidence, document comparison, refresh
and resume, and JSON/PNG exports.

Workspace IDs grant access to their data. Do not share them or upload confidential
files to the public demo. Use the workspace deletion control when finished.

## Persistent deployment

The existing production Compose configuration uses PostgreSQL and an uploads volume.
Configure `.env` from `.env.example`, set strong database credentials and actual
origins, and terminate HTTPS with a reverse proxy.

```sh
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

## References

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://vercel.com/docs/monorepos

The root Dockerfile and `app.py` are alternative backend entrypoints. Check current
Hugging Face account requirements before deploying there; the previous claim that
Gradio compute is always free was inaccurate.
