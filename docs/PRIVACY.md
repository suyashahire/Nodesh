# Privacy and data lifecycle

Nodesh currently uses anonymous, browser-held workspace IDs. It does not implement accounts, analytics, or external AI calls.

## What is stored

- Source documents are stored in the configured `UPLOADS_DIR` under a server-generated workspace directory.
- PostgreSQL stores workspace metadata, extracted text, concepts, relationships, and relationship evidence.
- The browser stores only the anonymous workspace UUID in local storage.

## Deletion

The **Delete workspace and data** control permanently removes the workspace database records and its uploaded files. Clearing browser site data alone only removes the local reference; it does not delete server-side data.

## Current limitations

This is a development-stage privacy posture. Before handling sensitive or regulated data in production, add authentication, retention policies, encrypted backups, access logging, rate limits, and an operational incident process.
