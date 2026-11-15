import { describe, expect, it, vi } from "vitest";

import {
  computeBetweennessCentrality,
  concentricLayout,
  deriveClusterTopics,
  findBridgeConceptIds,
  findShortestPath,
  getKnowledgeGraph,
  type GraphEdge,
  type GraphNode,
} from "./graph";

describe("getKnowledgeGraph", () => {
  it("requests one workspace-scoped graph snapshot", async () => {
    const graph = { nodes: [], edges: [] };
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(graph), { status: 200 }),
    );

    await expect(
      getKnowledgeGraph({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: "workspace-id",
      }),
    ).resolves.toEqual(graph);

    expect(fetchImplementation).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workspaces/workspace-id/graph",
    );
  });
});

describe("Betweenness Centrality & Bridge Concept Detection", () => {
  it("computes exact betweenness on a path graph A - B - C", () => {
    const nodes: GraphNode[] = [
      { id: "A", label: "A", document_count: 1, total_occurrences: 1 },
      { id: "B", label: "B", document_count: 1, total_occurrences: 1 },
      { id: "C", label: "C", document_count: 1, total_occurrences: 1 },
    ];
    const edges: GraphEdge[] = [
      {
        id: "e1",
        source: "A",
        target: "B",
        relationship_type: "uses",
        document_count: 1,
        strength: 1,
      },
      {
        id: "e2",
        source: "B",
        target: "C",
        relationship_type: "uses",
        document_count: 1,
        strength: 1,
      },
    ];

    const centrality = computeBetweennessCentrality(nodes, edges);
    expect(centrality.get("A")).toBe(0);
    expect(centrality.get("B")).toBe(1);
    expect(centrality.get("C")).toBe(0);

    const bridges = findBridgeConceptIds(nodes, edges);
    expect(bridges.has("B")).toBe(true);
    expect(bridges.has("A")).toBe(false);
    expect(bridges.has("C")).toBe(false);
  });

  it("handles barbell graph connecting two distinct clusters via bridge", () => {
    // Cluster 1: A1 - A2 - A3 (triangle)
    // Bridge: BridgeNode
    // Cluster 2: B1 - B2 - B3 (triangle)
    // A3 - BridgeNode - B1
    const nodes: GraphNode[] = [
      { id: "A1", label: "A1", document_count: 1, total_occurrences: 1 },
      { id: "A2", label: "A2", document_count: 1, total_occurrences: 1 },
      { id: "A3", label: "A3", document_count: 1, total_occurrences: 1 },
      { id: "Bridge", label: "Bridge", document_count: 1, total_occurrences: 1 },
      { id: "B1", label: "B1", document_count: 1, total_occurrences: 1 },
      { id: "B2", label: "B2", document_count: 1, total_occurrences: 1 },
      { id: "B3", label: "B3", document_count: 1, total_occurrences: 1 },
    ];

    const edges: GraphEdge[] = [
      { id: "1", source: "A1", target: "A2", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "2", source: "A2", target: "A3", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "3", source: "A3", target: "A1", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "4", source: "A3", target: "Bridge", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "5", source: "Bridge", target: "B1", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "6", source: "B1", target: "B2", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "7", source: "B2", target: "B3", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
      { id: "8", source: "B3", target: "B1", relationship_type: "co_occurs_with", document_count: 1, strength: 1 },
    ];

    const centrality = computeBetweennessCentrality(nodes, edges);
    // Bridge has the highest centrality in this barbell graph (all 3 A nodes must pass through Bridge to reach all 3 B nodes = 3 * 3 = 9 shortest paths)
    expect(centrality.get("Bridge")).toBe(9);

    const bridges = findBridgeConceptIds(nodes, edges);
    expect(bridges.has("Bridge")).toBe(true);
  });
});

describe("findShortestPath", () => {
  const nodes: GraphNode[] = [
    { id: "cancer", label: "breast cancer", document_count: 1, total_occurrences: 2 },
    { id: "tree", label: "decision tree", document_count: 1, total_occurrences: 4 },
    { id: "python", label: "python", document_count: 1, total_occurrences: 10 },
    { id: "fastapi", label: "fastapi", document_count: 1, total_occurrences: 5 },
    { id: "isolated", label: "unrelated note", document_count: 1, total_occurrences: 1 },
  ];

  const edges: GraphEdge[] = [
    { id: "e1", source: "cancer", target: "tree", relationship_type: "applied_to", document_count: 1, strength: 3 },
    { id: "e2", source: "tree", target: "python", relationship_type: "built_with", document_count: 1, strength: 6 },
    { id: "e3", source: "python", target: "fastapi", relationship_type: "uses", document_count: 1, strength: 8 },
  ];

  it("finds multi-hop path across knowledge graph", () => {
    const path = findShortestPath(nodes, edges, "cancer", "fastapi");
    expect(path).not.toBeNull();
    expect(path?.totalHops).toBe(3);
    expect(path?.nodeIds).toEqual(["cancer", "tree", "python", "fastapi"]);
    expect(path?.steps.map((s) => s.relationshipType)).toEqual(["applied_to", "built_with", "uses"]);
  });

  it("returns 0 hops when start is target", () => {
    const path = findShortestPath(nodes, edges, "python", "python");
    expect(path).not.toBeNull();
    expect(path?.totalHops).toBe(0);
    expect(path?.nodeIds).toEqual(["python"]);
  });

  it("returns null for disconnected nodes", () => {
    const path = findShortestPath(nodes, edges, "cancer", "isolated");
    expect(path).toBeNull();
  });
});

describe("deriveClusterTopics", () => {
  it("generates descriptive cluster names from top ranked concepts", () => {
    const nodes: GraphNode[] = [
      { id: "1", label: "random forest", document_count: 1, total_occurrences: 8, tfidf_score: 5.2 },
      { id: "2", label: "decision tree", document_count: 1, total_occurrences: 6, tfidf_score: 4.8 },
      { id: "3", label: "fastapi", document_count: 1, total_occurrences: 7, tfidf_score: 5.0 },
      { id: "4", label: "mongodb", document_count: 1, total_occurrences: 4, tfidf_score: 3.5 },
    ];
    const edges: GraphEdge[] = [
      { id: "e1", source: "1", target: "2", relationship_type: "uses", document_count: 1, strength: 4 },
      { id: "e2", source: "3", target: "4", relationship_type: "uses", document_count: 1, strength: 3 },
    ];

    const clusterMap = new Map<string, number>([
      ["1", 0],
      ["2", 0],
      ["3", 1],
      ["4", 1],
    ]);

    const topics = deriveClusterTopics(nodes, edges, clusterMap);
    expect(topics.length).toBe(2);

    const mlTopic = topics.find((t) => t.id === 0);
    expect(mlTopic?.name).toBe("Random Forest & Decision Tree");
    expect(mlTopic?.topConceptNames).toEqual(["random forest", "decision tree"]);

    const webTopic = topics.find((t) => t.id === 1);
    expect(webTopic?.name).toBe("Fastapi & Mongodb");
    expect(webTopic?.topConceptNames).toEqual(["fastapi", "mongodb"]);
  });
});

describe("concentricLayout", () => {
  it("positions nodes deterministically with hubs closer to center", () => {
    const nodes: GraphNode[] = [
      { id: "hub", label: "central hub", document_count: 2, total_occurrences: 15 },
      { id: "c1", label: "concept 1", document_count: 1, total_occurrences: 5 },
      { id: "c2", label: "concept 2", document_count: 1, total_occurrences: 4 },
      { id: "c3", label: "concept 3", document_count: 1, total_occurrences: 3 },
      { id: "leaf", label: "leaf node", document_count: 1, total_occurrences: 1 },
    ];
    const edges: GraphEdge[] = [
      { id: "e1", source: "hub", target: "c1", relationship_type: "uses", document_count: 1, strength: 5 },
      { id: "e2", source: "hub", target: "c2", relationship_type: "uses", document_count: 1, strength: 4 },
      { id: "e3", source: "hub", target: "c3", relationship_type: "uses", document_count: 1, strength: 3 },
      { id: "e4", source: "c3", target: "leaf", relationship_type: "uses", document_count: 1, strength: 1 },
    ];

    const positioned = concentricLayout(nodes, edges, 960, 640);
    expect(positioned.length).toBe(5);

    // All positioned nodes should have valid x and y
    for (const p of positioned) {
      expect(p.x).toBeGreaterThan(0);
      expect(p.x).toBeLessThan(960);
      expect(p.y).toBeGreaterThan(0);
      expect(p.y).toBeLessThan(640);
    }

    // Hub node should be at or nearest to center (480, 320)
    const hub = positioned.find((p) => p.id === "hub");
    const leaf = positioned.find((p) => p.id === "leaf");
    expect(hub).toBeDefined();
    expect(leaf).toBeDefined();

    const distHub = Math.hypot(hub!.x - 480, hub!.y - 320);
    const distLeaf = Math.hypot(leaf!.x - 480, leaf!.y - 320);
    expect(distHub).toBeLessThan(distLeaf);
  });
});


