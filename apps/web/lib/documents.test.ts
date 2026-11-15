import { describe, expect, it, vi } from "vitest";

import { deleteDocument, getDocumentComparison, listDocuments } from "./documents";

const document = {
  id: "f3479c31-1b10-4514-91bb-7c2c89ea944a",
  workspace_id: "e817dfd3-caf5-4c82-9d90-161c69b517e3",
  original_filename: "ideas.md",
  media_type: "text/markdown",
  size_bytes: 12,
  extraction_status: "completed",
  extracted_characters: 12,
  created_at: "2026-11-14T00:00:00Z",
};

describe("listDocuments", () => {
  it("reads the current workspace document list", async () => {
    const fetchImplementation = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([document]), { status: 200 }));

    await expect(
      listDocuments({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: document.workspace_id,
      }),
    ).resolves.toEqual([document]);

    expect(fetchImplementation).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/workspaces/${document.workspace_id}/documents`,
    );
  });
});

describe("deleteDocument", () => {
  it("deletes a document by id", async () => {
    const fetchImplementation = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      deleteDocument({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: document.workspace_id,
        documentId: document.id,
      }),
    ).resolves.toBeUndefined();

    expect(fetchImplementation).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/workspaces/${document.workspace_id}/documents/${document.id}`,
      { method: "DELETE" },
    );
  });
});

describe("getDocumentComparison", () => {
  it("requests workspace multi-document comparison", async () => {
    const comparison = {
      workspace_id: document.workspace_id,
      total_documents: 1,
      documents: [],
      shared_concepts: [],
      pairwise_overlap: [],
    };
    const fetchImplementation = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(comparison), { status: 200 }));

    await expect(
      getDocumentComparison({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: document.workspace_id,
      }),
    ).resolves.toEqual(comparison);

    expect(fetchImplementation).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/workspaces/${document.workspace_id}/documents/comparison`,
    );
  });
});

