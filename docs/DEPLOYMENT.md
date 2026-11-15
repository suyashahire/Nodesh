# Nodesh Deployment Guide

This guide covers deploying Nodesh online with a live public URL and custom domain.

---

## Architecture for Online Deployment

Nodesh consists of:
1. **Frontend**: Next.js 15 (React 19) web application (`apps/web`).
2. **Backend**: FastAPI (Python 3.11+) REST API (`apps/api`).
3. **Database**: PostgreSQL (managed cloud or containerized).
4. **Storage**: Local disk or persistent cloud volume (`uploads/`).

---

## Recommended Free-Tier Cloud Deployment (Vercel + Render)

### Step 1: Push to GitHub

1. Create a new public repository on [GitHub](https://github.com/new) named `nodesh`.
2. Connect your local repository and push:
   ```sh
   git remote add origin https://github.com/<your-username>/nodesh.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 2: Deploy Backend API & Database (Render)

1. Sign in to [Render.com](https://render.com) using your GitHub account.
2. Click **New +** → **Blueprint**.
3. Select your `nodesh` repository. Render automatically reads `render.yaml` from the root directory.
4. Render will create:
   - **`nodesh-api`**: FastAPI Web Service running on Python 3.11.
   - **`nodesh-db`**: Managed PostgreSQL Database.
5. Click **Apply**.
6. Once deployed, note your public API URL (e.g., `https://nodesh-api.onrender.com`).

---

### Step 3: Deploy Frontend Web Application (Vercel)

1. Sign in to [Vercel.com](https://vercel.com) using your GitHub account.
2. Click **Add New...** → **Project**.
3. Import your `nodesh` repository.
4. In the configuration screen:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click *Edit* and select `apps/web`.
5. Under **Environment Variables**, add:
   - **`NEXT_PUBLIC_API_BASE_URL`**: `https://nodesh-api.onrender.com` (your Render backend URL from Step 2).
6. Click **Deploy**.
7. In ~60 seconds, Vercel gives you an instant live URL (e.g., `https://nodesh.vercel.app`).
8. *(Optional)* Return to Render environment settings for `nodesh-api` and update `WEB_ORIGIN` to match your Vercel URL (e.g., `https://nodesh.vercel.app`).

---

## Alternative: All-in-One Cloud Deployment (Railway)

If you prefer deploying the entire stack on one platform:

1. Sign in to [Railway.app](https://railway.app).
2. Click **New Project** → **Deploy from GitHub repo** → select `nodesh`.
3. Add a **PostgreSQL** database service.
4. Link `DATABASE_URL` to the API service.
5. Generate domain for frontend and backend.

---

## Self-Hosted Production Run (Docker Compose on a VPS)

For a self-hosted cloud instance (e.g. AWS EC2, DigitalOcean Droplet, Hetzner):

```sh
# Copy and configure environment variables
cp .env.example .env

# Start with production Compose file
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

Use Nginx or Caddy with Let's Encrypt for automatic HTTPS/TLS termination.
