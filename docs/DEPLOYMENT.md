# Nodesh Deployment Guide

This guide covers deploying Nodesh online with a live public URL and custom domain without requiring a credit card.

---

## Architecture for Online Deployment

Nodesh consists of:
1. **Frontend**: Next.js 15 (React 19) web application (`apps/web`).
2. **Backend**: FastAPI (Python 3.11+) REST API (`apps/api`).
3. **Database**: SQLite (embedded, zero external setup) or PostgreSQL.
4. **Storage**: Local persistent filesystem (`uploads/`).

---

## 100% Free & Zero-Card Deployment (Hugging Face Spaces + Vercel)

> [!NOTE]
> **No credit card or payment method is required for either platform.**
> - **Hugging Face Spaces**: Select the **Gradio SDK** (100% free with 2 vCPUs · 16 GB RAM). Our root `app.py` automatically mounts the full FastAPI REST API onto it.
> - **Vercel**: Next.js 15 frontend hosted on the global edge (Hobby tier is 100% free).

---

### Step 1: Deploy Backend API on Hugging Face Spaces

1. Create a free account at [huggingface.co](https://huggingface.co) (login via GitHub or email; **zero card required**).
2. Go to **[huggingface.co/new-space](https://huggingface.co/new-space)**.
3. Configure your Space:
   - **Space Name**: `nodesh-api`
   - **License**: `mit`
   - **Space SDK**: Select **Gradio** *(100% free forever; DO NOT choose Docker as Docker requires a paid PRO plan)*
   - **Space hardware**: `Free CPU (2 vCPU · 16 GB RAM)`
   - **Visibility**: `Public`
4. Click **Create Space**.
5. Connect your local git repository and push to Hugging Face:
   ```sh
   # Add Hugging Face Space as a git remote
   git remote add space https://huggingface.co/spaces/<your-hf-username>/nodesh-api

   # Push to Hugging Face
   git push space main
   ```
   *(Hugging Face will automatically install `requirements.txt`, run migrations, and launch `app.py` on port 7860).*
6. Once the build badge says **Running**, your live backend URL is:
   `https://<your-hf-username>-nodesh-api.hf.space`
7. Test the health endpoint in your browser or curl:
   ```sh
   curl https://<your-hf-username>-nodesh-api.hf.space/health
   # Returns: {"status":"healthy"}
   ```

---

### Step 2: Deploy Frontend on Vercel

1. Sign in to [Vercel.com](https://vercel.com) with GitHub (**zero card required** on Hobby tier).
2. Click **Add New...** → **Project**.
3. Import your GitHub repository: `suyashahire/Nodesh`.
4. Configure the project:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click *Edit* and select `apps/web`.
5. Under **Environment Variables**, add:
   - **Key**: `NEXT_PUBLIC_API_BASE_URL`
   - **Value**: `https://<your-hf-username>-nodesh-api.hf.space` (from Step 1)
6. Click **Deploy**.
7. In ~45 seconds, Vercel gives you your production URL: `https://nodesh.vercel.app`.

---

## Self-Hosted Production Run (Docker Compose on VPS)

For a self-hosted cloud instance (e.g. AWS EC2, DigitalOcean Droplet, Hetzner):

```sh
# Copy and configure environment variables
cp .env.example .env

# Start with production Compose file
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```
