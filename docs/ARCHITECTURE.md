# Architecture

Nodesh begins as a modular monolith: one repository and deployable API, with clearly bounded modules that can evolve independently when justified.

```text
apps/
  api/       FastAPI application and future domain modules
  web/       Next.js user interface
docs/        Product and architecture documentation
compose.yaml Local PostgreSQL only
```

## Milestone 0 scope

- FastAPI application with a versioned health contract.
- Next.js TypeScript application shell.
- PostgreSQL service for local development; persistence is deliberately not wired into the health endpoint.
- Shared environment-variable convention through `.env.example`.

No IDE-specific configuration or agent-specific behavior is required to work in this repository.

## Milestone 1: anonymous workspaces

The API owns a PostgreSQL `workspaces` table managed through Alembic migrations. A workspace ID is a randomly generated UUID, held only in the browser's local storage. It acts as the anonymous workspace capability: it enables resuming the workspace without introducing accounts, profiles, or authentication in this milestone.

The web shell creates a workspace when no local ID exists, attempts to resume a stored ID on later visits, and replaces a stale ID with a new workspace. Future documents, extracted concepts, and graph data will belong to a workspace.

## Milestone 2: document ingestion

Documents belong to one workspace and are stored on the local filesystem under a server-generated UUID filename. The original user filename is metadata only and is never used as a storage path. The API accepts PDF, DOCX, UTF-8 text, and Markdown files, extracts their readable text synchronously, and persists the result with document metadata.

This milestone intentionally excludes OCR, semantic analysis, topic extraction, and external AI services. Scanned PDFs can be uploaded but may produce no text until a later OCR capability is introduced.

## Milestone 3: topics and concepts

Nodesh uses a deterministic, English-language baseline extractor. It removes common stop words, counts meaningful keywords, and gives extra weight to repeated two-word phrases. The result is intentionally transparent and reproducible, rather than model-driven.

Concepts are aggregated per workspace and linked to every source document that produced them. Re-running analysis replaces prior links for each document and recomputes the workspace aggregates, so the operation is idempotent. This creates a clean seam for richer NLP methods in later milestones without coupling the application to a specific model.

## Milestone 4: relationship extraction and resolution

Relationships are an undirected, evidence-backed `co_occurs_with` baseline. Each relationship uses a canonical ordering of its two resolved concept IDs, preventing duplicate A→B and B→A edges. A per-document evidence record retains the occurrence counts that produced the edge. Re-running extraction replaces evidence and recomputes the aggregate strength, keeping the graph reproducible and explainable.
