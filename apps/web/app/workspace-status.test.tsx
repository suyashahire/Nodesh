import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// @ts-expect-error vitest / jsdom act flag
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

import { WorkspaceStatus } from "./workspace-status";

describe("WorkspaceStatus Editorial Shell & Navigator", () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);

    // Mock localStorage
    const storage: Record<string, string> = {
      "nodesh.workspace-id": "ws-editorial-123",
    };
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn((key: string) => storage[key] ?? null),
        setItem: vi.fn((key: string, val: string) => {
          storage[key] = val;
        }),
        removeItem: vi.fn((key: string) => {
          delete storage[key];
        }),
        clear: vi.fn(),
      },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    document.body.removeChild(container);
    vi.restoreAllMocks();
  });

  it("renders the editorial top bar and empty navigator when no documents exist", async () => {
    // Mock API responses for empty workspace
    vi.spyOn(window, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.includes("/workspaces/ws-editorial-123/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/concepts")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/relationships")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/graph")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ nodes: [], edges: [] }) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/stats")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              workspace_id: "ws-editorial-123",
              total_documents: 0,
              total_concepts: 0,
              total_relationships: 0,
              average_strength: 0,
              max_strength: 0,
              density: 0,
            }),
        } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/comparison")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              workspace_id: "ws-editorial-123",
              documents: [],
              shared_concepts: [],
              pairwise_overlap: [],
            }),
        } as Response);
      }
      // workspace fetch
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "ws-editorial-123",
            name: "Research Workspace",
            created_at: new Date().toISOString(),
          }),
      } as Response);
    });

    const root = createRoot(container);
    await act(async () => {
      root.render(<WorkspaceStatus />);
    });

    // Top bar checks
    const wordmark = container.querySelector(".app-wordmark");
    expect(wordmark?.textContent).toBe("Nodesh");

    const topbarMeta = container.querySelectorAll(".topbar-meta");
    expect(topbarMeta.length).toBeGreaterThan(0);
    expect(container.textContent).toContain("0 documents");

    // Primary action
    const primaryBtn = container.querySelector(".btn-primary-action");
    expect(primaryBtn?.textContent).toBe("+ Add document");

    // Mode toggle
    expect(container.querySelector(".topbar-mode-toggle")).not.toBeNull();

    // Document Navigator: calm guided empty state
    expect(container.querySelector(".doc-empty-state")).not.toBeNull();
    expect(container.textContent).toContain("No documents added");
    expect(container.textContent).toContain("Drop PDF, DOCX, TXT, or MD files here");

    const documentsToggle = container.querySelector(".mobile-documents-toggle") as HTMLButtonElement;
    expect(documentsToggle.getAttribute("aria-expanded")).toBe("false");
    await act(async () => documentsToggle.click());
    expect(container.querySelector(".doc-navigator-open")).not.toBeNull();
    expect(documentsToggle.getAttribute("aria-expanded")).toBe("true");
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(container.querySelector(".doc-navigator-open")).toBeNull();
    expect(container.querySelector(".mobile-documents-backdrop")).toBeNull();
  });

  it("renders focused document list and comparison option when documents exist", async () => {
    const mockDocs = [
      {
        id: "d1",
        workspace_id: "ws-editorial-123",
        original_filename: "transformer_architectures.pdf",
        storage_path: "storage/d1.pdf",
        content_hash: "h1",
        mime_type: "application/pdf",
        size_bytes: 45200,
        concept_count: 8,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: "d2",
        workspace_id: "ws-editorial-123",
        original_filename: "attention_mechanisms.pdf",
        storage_path: "storage/d2.pdf",
        content_hash: "h2",
        mime_type: "application/pdf",
        size_bytes: 31200,
        concept_count: 6,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];

    const mockGraph = {
      nodes: [
        { id: "c1", label: "Self-Attention", document_count: 2, total_occurrences: 8, tfidf_score: 3.5 },
      ],
      edges: [],
    };

    const mockComparison = {
      workspace_id: "ws-editorial-123",
      documents: [
        { document_id: "d1", filename: "transformer_architectures.pdf", total_concepts: 8, unique_concept_count: 5, unique_concepts: ["Encoder", "Decoder"] },
        { document_id: "d2", filename: "attention_mechanisms.pdf", total_concepts: 6, unique_concept_count: 3, unique_concepts: ["QKV Matrix"] },
      ],
      shared_concepts: [
        { id: "c1", name: "Self-Attention", document_count: 2, total_occurrences: 8, document_names: ["transformer_architectures.pdf", "attention_mechanisms.pdf"] },
      ],
      pairwise_overlap: [
        {
          doc_a_id: "d1",
          doc_a_name: "transformer_architectures.pdf",
          doc_b_id: "d2",
          doc_b_name: "attention_mechanisms.pdf",
          shared_concept_count: 1,
          shared_concepts: ["Self-Attention"],
          jaccard_similarity: 0.25,
        },
      ],
    };

    vi.spyOn(window, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.includes("/comparison")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockComparison) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDocs) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/concepts")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/relationships")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/graph")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockGraph) } as Response);
      }
      if (u.includes("/workspaces/ws-editorial-123/stats")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              workspace_id: "ws-editorial-123",
              total_documents: 2,
              total_concepts: 1,
              total_relationships: 0,
              average_strength: 0,
              max_strength: 0,
              density: 0,
            }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "ws-editorial-123",
            name: "Research Workspace",
            created_at: new Date().toISOString(),
          }),
      } as Response);
    });

    const root = createRoot(container);
    await act(async () => {
      root.render(<WorkspaceStatus />);
    });

    // Document Navigator list items
    const docItems = container.querySelectorAll(".doc-item");
    expect(docItems.length).toBe(2);
    expect(container.textContent).toContain("transformer_architectures.pdf");
    expect(container.textContent).toContain("attention_mechanisms.pdf");

    // Compact drop strip (no giant cards)
    expect(container.querySelector(".compact-drop-strip")).not.toBeNull();
    expect(container.textContent).toContain("+ Drop or click to add files");

    // Compare button is present when >= 2 documents
    const compareBtn = container.querySelector(".btn-nav-compare") as HTMLButtonElement;
    expect(compareBtn).not.toBeNull();

    // Clicking compare button opens the modal
    await act(async () => {
      compareBtn.click();
    });
    expect(container.querySelector(".comparison-modal")).not.toBeNull();
    expect(container.textContent).toContain("Document Pair Similarity (Jaccard Overlap)");
    expect(container.textContent).toContain("25% match");

    // Clicking close button dismisses modal
    const closeBtn = container.querySelector(".comparison-modal .inspector-close") as HTMLButtonElement;
    await act(async () => {
      closeBtn.click();
    });
    expect(container.querySelector(".comparison-modal")).toBeNull();

    // Document filter interaction
    const firstDoc = container.querySelector(".doc-item") as HTMLElement;
    await act(async () => {
      firstDoc.click();
    });
    expect(firstDoc.classList.contains("doc-item-filtered")).toBe(true);
  });
});
