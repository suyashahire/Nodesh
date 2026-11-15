import { describe, expect, it, vi } from "vitest";

import { extractConcepts, getConceptDossier, getMergeSuggestions, mergeConcepts } from "./concepts";

describe("extractConcepts", () => {
  it("requests a workspace concept refresh", async () => {
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ documents_analyzed: 1, concepts: [] }), { status: 200 }),
    );

    await expect(
      extractConcepts({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
      }),
    ).resolves.toEqual({ documents_analyzed: 1, concepts: [] });

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/concepts/extract",
      { method: "POST" },
    );
  });

  it("requests concept merge suggestions", async () => {
    const suggestions = [
      {
        source_concept_id: "src-1",
        source_name: "random forests",
        target_concept_id: "tgt-1",
        target_name: "random forest",
        similarity: 0.95,
        reason: "Plural/singular variant",
      },
    ];
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(suggestions), { status: 200 }),
    );

    await expect(
      getMergeSuggestions({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
      }),
    ).resolves.toEqual(suggestions);

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/concepts/merge-suggestions",
    );
  });

  it("submits a manual concept merge request", async () => {
    const result = {
      merged_into_concept_id: "tgt-1",
      merged_concept_name: "random forest",
      source_occurrences_merged: 3,
      new_total_occurrences: 7,
    };
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(result), { status: 200 }),
    );

    await expect(
      mergeConcepts({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
        sourceConceptId: "src-1",
        targetConceptId: "tgt-1",
      }),
    ).resolves.toEqual(result);

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/concepts/merge",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_concept_id: "src-1",
          target_concept_id: "tgt-1",
        }),
      },
    );
  });

  it("fetches concept extractive dossier summary", async () => {
    const dossier = {
      concept_id: "c-1",
      concept_name: "random forest",
      summary: "Random forest constructs decision trees. It outputs the majority class.",
      key_sentences: [
        "Random forest constructs decision trees.",
        "It outputs the majority class.",
      ],
      source_documents: ["guide.txt"],
    };
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(dossier), { status: 200 }),
    );

    await expect(
      getConceptDossier({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
        conceptId: "c-1",
      }),
    ).resolves.toEqual(dossier);

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/concepts/c-1/dossier",
    );
  });
});

