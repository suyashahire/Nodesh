# Nodesh

Nodesh turns a collection of documents into an interconnected, calm, and explorable knowledge graph workspace.

Built with a **FastAPI** backend, **Next.js 15 (React 19)** frontend, and zero external ML dependencies—Nodesh uses deterministic statistical NLP (TF-IDF + Okapi BM25, PMI/NPMI co-occurrence, and TextRank PageRank) to extract concepts, relationships, and document evidence.

---

## Features

- **Editorial Knowledge Workspace**: Calm, focused application shell with a paper parchment canvas, quiet toolbar, collapsible navigator, and contextual right-side inspector.
- **Deterministic Concept Extraction**: Classical statistical NLP with clause-bounded n-grams, technical acronym whitelisting (`AI`, `ML`, `DL`, `FastAPI`, `BERT`), and multi-level phrase subsumption deduplication.
- **Semantic Relationship Graph**: Evidence-backed co-occurrence with Pointwise Mutual Information (PMI/NPMI) and typed relationship predicates (`uses`, `improves`, `causes`, `compared_to`, `trained_for`, `built_with`).
- **Interactive Graph Canvas**: Canvas supporting both force-directed organic and concentric circle layouts, radar minimap, connected neighbor highlights, node importance sizing, and topic cluster legends.
- **Concept Dossiers & Evidence**: Contextual inspector powered by TextRank PageRank extractive summarization, presenting key quotes, source references, and co-occurring neighbors.
- **Multi-Document Comparison & Alias Merging**: Non-destructive, suggestion-only alias merging and multi-document overlap comparison.
- **Hardened Security & Strict Quotas**: Mandatory magic-byte inspection (`%PDF-`, `PK\x03\x04`), 10MB file limit, 25-doc/50MB workspace quotas, decompression bomb mitigation, sliding-window rate limiting, and strict security headers.

---

## Prerequisites

- Node.js 20 or newer
- Python 3.11 or newer (Python 3.13 tested)
- Docker Compose (optional for containerized run)

---

## Quick Start

### 1. Backend Setup
From `apps/api`:
```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn --app-dir src nodesh_api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
From the repository root:
```sh
npm install
npm run dev:web
```

The web shell is available at `http://localhost:3000`; the API health endpoint runs at `http://localhost:8000/health`.

---

## Validation & Testing

Run the complete test suites:

```sh
# Backend tests (41 tests: extraction, textrank, graph, security, quotas)
pytest apps/api/tests

# Frontend tests (33 tests: workspace shell, graph views, inspectors)
npm run test:web

# TypeScript typecheck
npx tsc -p apps/web/tsconfig.json --noEmit
```

---

## Production Deployment

Run locally with production settings via Docker Compose:
```sh
docker compose -f compose.yaml -f compose.production.yaml up --build
```

For detailed architecture, deployment, and privacy documentation, see `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, and `docs/PRIVACY.md`.
