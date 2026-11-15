"""Hugging Face Space entrypoint: Mounts Nodesh FastAPI backend inside Gradio."""

import os
from pathlib import Path
import sys

# Add apps/api/src to Python import path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "api" / "src"))

# Production defaults for Hugging Face free container
os.environ.setdefault("DATABASE_URL", "sqlite:///./nodesh.db")
os.environ.setdefault("UPLOADS_DIR", "./uploads")
os.environ.setdefault("WEB_ORIGIN", "*")

# Ensure uploads directory exists
Path("./uploads").mkdir(parents=True, exist_ok=True)

# Run database migrations
try:
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path(__file__).parent / "apps" / "api" / "alembic.ini"
    if alembic_ini.exists():
        cfg = Config(str(alembic_ini))
        cfg.set_main_option(
            "script_location",
            str(Path(__file__).parent / "apps" / "api" / "migrations"),
        )
        command.upgrade(cfg, "head")
except Exception as err:
    print(f"Migration note: {err}")

from nodesh_api.main import app as fastapi_app
import gradio as gr
import uvicorn

# Informative UI landing page when accessed directly in a browser
with gr.Blocks(title="Nodesh API") as demo:
    gr.Markdown("# 🚀 Nodesh Graph API")
    gr.Markdown(
        "Deterministic NLP and knowledge graph backend is **online and healthy**."
    )
    gr.Markdown("- **Interactive Swagger Docs**: [/docs](/docs)")
    gr.Markdown("- **Health Status**: [/health](/health)")
    gr.Markdown(
        "- **GitHub Repository**: [suyashahire/Nodesh](https://github.com/suyashahire/Nodesh)"
    )

app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
