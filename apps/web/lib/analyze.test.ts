import { describe, expect, it, vi } from "vitest";

import { analyzeWorkspace } from "./analyze";

describe("analyzeWorkspace", () => {
  it("requests full workspace analysis pipeline", async () => {
    const mockResult = {
      documents_analyzed: 1,
      concepts: [],
      relationships: [],
      graph: { nodes: [], edges: [] },
    };
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockResult), { status: 200 }),
    );

    await expect(
      analyzeWorkspace({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "ws-123",
      }),
    ).resolves.toEqual(mockResult);

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/ws-123/analyze",
      { method: "POST" },
    );
  });
});
