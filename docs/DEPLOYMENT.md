# Deployment

## Local production-style run

Create a production environment file with strong PostgreSQL credentials and a public API URL, then run:

```sh
docker compose -f compose.yaml -f compose.production.yaml up --build
```

The API container applies Alembic migrations before it starts. Uploaded documents persist in the named `nodesh-uploads` volume; PostgreSQL persists in `postgres-data`.

## Required configuration

- `POSTGRES_PASSWORD`: a strong, deployment-specific password.
- `WEB_ORIGIN`: the browser-facing Nodesh URL, used by API CORS.
- `NEXT_PUBLIC_API_BASE_URL`: the browser-accessible API URL. This value is compiled into the web image during its build.
- `MAX_UPLOAD_BYTES`: optional per-document size limit; default is 20 MiB.

Use TLS termination at your reverse proxy or hosting platform. Do not expose PostgreSQL publicly in an Internet-facing deployment.
