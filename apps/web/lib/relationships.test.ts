import { describe, expect, it, vi } from "vitest";

import {
  extractRelationships,
  formatPredicate,
  getPredicateClass,
  getRelationshipEvidence,
} from "./relationships";

describe("extractRelationships", () => {
  it("requests an evidence-backed relationship refresh", async () => {
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ documents_analyzed: 1, relationships: [] }), { status: 200 }),
    );

    await expect(
      extractRelationships({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
      }),
    ).resolves.toEqual({ documents_analyzed: 1, relationships: [] });

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/relationships/extract",
      { method: "POST" },
    );
  });

  it("requests evidence for a specific relationship", async () => {
    const evidence = [
      {
        document_id: "doc-1",
        original_filename: "test.pdf",
        source_occurrences: 2,
        target_occurrences: 2,
        snippet: "text snippet",
      },
    ];
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(evidence), { status: 200 }),
    );

    await expect(
      getRelationshipEvidence({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
        relationshipId: "rel-id",
      }),
    ).resolves.toEqual(evidence);

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/relationships/rel-id/evidence",
    );
  });
});

describe("Predicate formatters", () => {
  it("formats predicates into natural human readable strings", () => {
    expect(formatPredicate("built_with")).toBe("built with");
    expect(formatPredicate("uses")).toBe("uses");
    expect(formatPredicate("applied_to")).toBe("applied to");
    expect(formatPredicate("co_occurs_with")).toBe("related to");
    expect(formatPredicate(undefined)).toBe("related to");
  });

  it("maps predicates to corresponding CSS class names", () => {
    expect(getPredicateClass("built_with")).toBe("predicate-built_with");
    expect(getPredicateClass("uses")).toBe("predicate-uses");
    expect(getPredicateClass("unknown")).toBe("predicate-co_occurs_with");
    expect(getPredicateClass(undefined)).toBe("predicate-co_occurs_with");
  });
});

