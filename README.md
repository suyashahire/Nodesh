# Nodesh

> Turn collections of documents into a calm, explorable knowledge graph — completely offline, deterministic, and private.

Most document tools today fall into one of two camps: they are either dumb search bars returning lists of disjointed files, or they wrap a third-party LLM that hallucinates connections, leaks your notes to cloud APIs, and charges per token.

**Nodesh** is built on a different principle: **your documents already contain their own structure.** 

By applying classical statistical NLP, mutual information theory, and graph centrality, Nodesh maps out the concepts and evidence hiding in your research papers, notes, and resumes. It runs in milliseconds on your local machine with zero external AI models, zero GPU requirements, and zero API keys.

---

## What it looks like

- **Parchment Knowledge Canvas**: A calm, editorial graph surface designed for thinking. Nodes are sized by graph importance and semantic weight rather than raw frequency.
- **Contextual Evidence Inspector**: Clicking any concept opens a right-side drawer showing exact source sentences extracted using TextRank PageRank, along with co-occurring neighbors.
- **Relational Proof**: Edges are not decorative lines. Clicking any connection reveals the exact paragraph snippets and Normalized Pointwise Mutual Information (NPMI) score proving *why* the two concepts belong together.
- **Document Navigator & Comparison**: Filter the graph to see concepts unique to a single document, or switch to intersection mode to see shared concepts across multiple files.
- **Non-Destructive Alias Merging**: Suggests likely duplicates (`React` vs `React.js`) with manual one-click merging that never mutates or destroys raw source files.

---

## How it works

Nodesh avoids machine learning dependencies in favor of reproducible, explainable algorithms:

### 1. Clause-Bounded Concept Extraction
Instead of blindly chunking text or splitting on spaces (which causes page headers and line wraps to merge into garbage bigrams), Nodesh segments text at grammatical clause boundaries (punctuation, quotes, line breaks). Candidates are scored using **Okapi BM25-smoothed TF-IDF** with phrase-level subsumption deduplication—so `Decision Tree` won't leave behind a redundant, orphaned `Tree` node.

### 2. Evidence-Backed Graph Topology
Connections are calculated by sliding contextual windows across paragraphs:
- **NPMI (Normalized Pointwise Mutual Information)**: Measures whether two ideas appear together significantly more often than random chance, bounding connection strength between `-1.0` and `+1.0`.
- **Predicate Classification**: Connective phrases between co-occurring entities are parsed to label edges with semantic types like `uses`, `improves`, `causes`, `trained_for`, and `built_with`.

### 3. TextRank Extractive Dossiers
When you inspect a concept, Nodesh builds a sentence similarity graph using cosine token overlap and runs the **PageRank** power-iteration algorithm. It extracts the most salient explanatory sentences directly from your documents without hallucinating words.

---

## Quickstart

### Prerequisites
- Python 3.11+ (Python 3.13 supported)
- Node.js 20+

### 1. Start the API
```sh
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn nodesh_api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Web App
From the root directory:
```sh
npm install
npm run dev:web
```

Open [http://localhost:3000](http://localhost:3000) in your browser. Drop in a few PDFs, Markdown files, or Word documents, and click **Analyze workspace**.

---

## Architecture & Tech Stack

| Layer | Technology | Why |
| :--- | :--- | :--- |
| **Frontend** | Next.js 15, React 19, TypeScript | Instant server hydration, typed API client contracts |
| **Graph Surface** | Canvas2D | Silky smooth 60fps rendering of 100+ nodes and edges |
| **Backend** | FastAPI, Python 3.13 | High-throughput asynchronous REST API |
| **Persistence** | SQLite / PostgreSQL + SQLAlchemy | Zero-config SQLite for local use, PostgreSQL for production |
| **Testing** | Pytest (41 tests) + Vitest (33 tests) | 100% pass rate across unit, integration, and security suites |

---

## Built with Security in Mind

Nodesh was engineered to safely ingest untrusted documents:
- **Magic-Byte Inspection**: Uploads are verified by byte signature (`%PDF-`, `PK\x03\x04`), rejecting disguised executables or spoofed MIME types.
- **Decompression Bomb Protection**: Word documents (`.docx`) are inspected for uncompressed size and compression ratios before extraction to prevent zip bombs.
- **Algorithmic Bounds**: TextRank PageRank is strictly bounded to the top 250 salient sentences, preventing quadratic $O(S^2)$ memory explosion on massive files.
- **Strict Quotas**: 10MB per document, 25 documents / 50MB maximum per workspace, with sliding-window rate limiting.

---

## Running Tests

```sh
# Backend tests (extraction, PageRank, relationships, security quotas)
pytest apps/api/tests

# Frontend tests (canvas interactions, inspectors, workspace shell)
npm run test:web

# TypeScript strict type check
npx tsc -p apps/web/tsconfig.json --noEmit
```

---

## License

MIT © [Suyash Ahire](https://github.com/suyashahire)
