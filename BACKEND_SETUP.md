# Pathly API setup

Pathly runs as a small monorepo: the Next.js app stays at the project root, while the FastAPI service lives in `backend/`. PostgreSQL stores durable application data, local disk stores uploaded learning materials during development, and Chroma stores the local vector index.

## Quick start with Docker

Requirements: Docker Desktop with Compose v2.

1. Copy the environment template and replace its secrets:

   ```bash
   cp .env.example .env
   openssl rand -hex 32
   ```

2. Put the generated value in `SECRET_KEY`. Add `GEMINI_API_KEY` and `GOOGLE_CLIENT_ID` when those integrations are needed.

3. Start the full stack:

   ```bash
   docker compose up --build
   ```

4. Open the services:

   - Web app: <http://localhost:3000>
   - API documentation: <http://localhost:8000/docs>
   - Alternative API documentation: <http://localhost:8000/redoc>
   - Health check: <http://localhost:8000/api/v1/health>

The API container runs `alembic upgrade head` before it starts. PostgreSQL, uploads, Chroma data, `node_modules`, and the Next.js build cache use named volumes, so normal container restarts do not erase them.

Stop the stack with `docker compose down`. Adding `--volumes` also deletes the local database, uploaded files, and vector index, so use it only when a full reset is intended.

## Run without Docker

### Database

Run PostgreSQL 16 locally and create a database and user matching `.env`. For a host-run API, `DATABASE_URL` must use `localhost`; the `postgres` hostname is only available inside Compose.

### Backend

Python 3.12 is recommended.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

If the backend uses a conventional requirements file instead of optional `pyproject.toml` dependencies, replace the install command with `pip install -r requirements.txt`.

### Frontend

In a second terminal:

```bash
cp frontend_env.example .env.local
npm install
npm run dev
```

`NEXT_PUBLIC_API_URL` should be `http://localhost:8000/api/v1` for local browser use.

## Database migrations

Apply committed migrations:

```bash
cd backend
alembic upgrade head
```

Create a migration after changing SQLAlchemy models, review the generated file, then apply it:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Inspect the current revision with `alembic current` and migration history with `alembic history`.

## Tests and quality checks

Backend:

```bash
cd backend
pytest
ruff check .
```

Frontend:

```bash
npm run lint
npm run build
```

Full Compose status and logs:

```bash
docker compose ps
docker compose logs -f api
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL connection URL. Compose overrides this with its internal `postgres` hostname. |
| `SECRET_KEY` | Signs Pathly access tokens. Use a long, random, private value and rotate it if exposed. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Short access-token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-session lifetime. |
| `GOOGLE_CLIENT_ID` | OAuth web client ID used to verify Google ID tokens. |
| `GEMINI_API_KEY` | Server-side Gemini credential. Never expose it as a `NEXT_PUBLIC_` variable. |
| `GEMINI_GENERATION_MODEL` | Gemini model used for summaries, learning paths, quizzes, and chat. |
| `GEMINI_EMBEDDING_MODEL` | Gemini model used for document and query embeddings. |
| `CORS_ORIGINS` | Exact frontend origins allowed to call the API. Do not use `*` with credentialed requests. |
| `STORAGE_BACKEND` | Storage provider selector; `local` is the development default. |
| `LOCAL_STORAGE_PATH` | Host path or container path used for uploads. |
| `MAX_UPLOAD_SIZE_MB` | Per-file upload limit enforced by the API. |
| `CHROMA_PATH` | Persistent local Chroma index directory. |
| `NEXT_PUBLIC_API_URL` | API base URL reachable from the user's browser. |

## Gemini configuration

Create a Gemini API key in Google AI Studio and store it only in the backend environment as `GEMINI_API_KEY`. The API should return a clear service-unavailable response for AI-only operations when the key is absent; ordinary account and subject operations should continue to work.

Generation and embedding model names are configurable so they can be upgraded without code changes. Uploaded documents remain the source of truth: generated answers should return their retrieved material and page/chunk references where available.

## Google sign-in configuration

1. Create a Web application OAuth client in Google Cloud Console.
2. Add `http://localhost:3000` as an authorized JavaScript origin for development.
3. Set the client ID in `GOOGLE_CLIENT_ID` on the API and in the frontend's Google Identity Services configuration.
4. The browser obtains a Google ID token and sends it to the Pathly Google-auth endpoint. The API validates its signature, audience, issuer, and expiry before creating or signing in a user.

Do not send a Google client secret to the browser. An ID-token sign-in flow does not need that secret in frontend code.

## Material storage and S3 migration

Development uses the local storage implementation selected by `STORAGE_BACKEND=local`. Database rows should keep provider-neutral object keys and metadata, not absolute filesystem paths. That boundary allows an S3 implementation to be added without changing routes or material records.

For production S3 support:

1. Implement the existing storage interface with `put`, `open` or `download`, and `delete` operations backed by an S3-compatible client.
2. Add configuration such as `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, and an optional key prefix.
3. Set `STORAGE_BACKEND=s3` and inject the S3 implementation from the storage factory.
4. Prefer workload roles in production. If static credentials are unavoidable, keep them in a secret manager rather than `.env` or Git.
5. Enable encryption, private bucket access, lifecycle policies, malware scanning, and signed download URLs where appropriate.

Chroma is suitable for local development. At production scale, the vector-store service can be replaced behind the retrieval interface while preserving PostgreSQL material and chunk metadata.

## Production checklist

- Set `ENVIRONMENT=production` and `DEBUG=false`.
- Use unique high-entropy database and token secrets.
- Serve the web app and API over HTTPS.
- Restrict `CORS_ORIGINS` to deployed frontend origins.
- Run migrations as a one-time release job instead of from every API replica.
- Remove `--reload` and source bind mounts from production deployment.
- Back up PostgreSQL and object storage, and define retention policies.
- Put rate limits and request-size limits at the reverse proxy and application layers.
- Send structured logs and health metrics to an observability service.
- Keep Gemini and Google credentials in the hosting platform's secret manager.
