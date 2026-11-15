export type GraphNode = {
  id: string;
  label: string;
  document_count: number;
  total_occurrences: number;
  tfidf_score?: number;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  document_count: number;
  strength: number;
  pmi?: number;
  npmi?: number;
};

export type KnowledgeGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export function computeBetweennessCentrality(
  nodes: GraphNode[],
  edges: GraphEdge[],
): Map<string, number> {
  const centrality = new Map<string, number>();
  for (const node of nodes) {
    centrality.set(node.id, 0);
  }

  if (nodes.length < 3 || edges.length === 0) {
    return centrality;
  }

  // Build undirected adjacency list
  const adj = new Map<string, string[]>();
  for (const node of nodes) {
    adj.set(node.id, []);
  }
  for (const edge of edges) {
    adj.get(edge.source)?.push(edge.target);
    adj.get(edge.target)?.push(edge.source);
  }

  // Brandes' Betweenness Centrality Algorithm
  for (const s of nodes) {
    const sId = s.id;
    const S: string[] = [];
    const P = new Map<string, string[]>();
    const sigma = new Map<string, number>();
    const d = new Map<string, number>();

    for (const node of nodes) {
      P.set(node.id, []);
      sigma.set(node.id, 0);
      d.set(node.id, -1);
    }
    sigma.set(sId, 1);
    d.set(sId, 0);

    const Q: string[] = [sId];
    while (Q.length > 0) {
      const v = Q.shift()!;
      S.push(v);
      const vDist = d.get(v)!;

      const neighbors = adj.get(v) ?? [];
      for (const w of neighbors) {
        // Path discovery
        if (d.get(w)! < 0) {
          d.set(w, vDist + 1);
          Q.push(w);
        }
        // Path counting
        if (d.get(w)! === vDist + 1) {
          sigma.set(w, sigma.get(w)! + sigma.get(v)!);
          P.get(w)!.push(v);
        }
      }
    }

    const delta = new Map<string, number>();
    for (const node of nodes) {
      delta.set(node.id, 0);
    }

    // Accumulation (reverse BFS order)
    while (S.length > 0) {
      const w = S.pop()!;
      const sigmaW = sigma.get(w)!;
      for (const v of P.get(w)!) {
        const c = (sigma.get(v)! / sigmaW) * (1 + delta.get(w)!);
        delta.set(v, delta.get(v)! + c);
      }
      if (w !== sId) {
        centrality.set(w, centrality.get(w)! + delta.get(w)!);
      }
    }
  }

  // For undirected graph, divide by 2 because each pair is visited from both directions
  for (const [id, val] of centrality.entries()) {
    centrality.set(id, val / 2);
  }

  return centrality;
}

export function findBridgeConceptIds(
  nodes: GraphNode[],
  edges: GraphEdge[],
  maxBridges = 5,
): Set<string> {
  const scores = computeBetweennessCentrality(nodes, edges);
  const nonZero = Array.from(scores.entries()).filter(([_, score]) => score > 0);
  if (nonZero.length === 0) return new Set<string>();

  nonZero.sort((a, b) => b[1] - a[1]);

  // Select top concepts with positive centrality (up to maxBridges, at least 1)
  const topCount = Math.min(
    Math.max(1, Math.ceil(nonZero.length * 0.25)),
    Math.min(nonZero.length, maxBridges),
  );

  return new Set(nonZero.slice(0, topCount).map(([id]) => id));
}

export type GraphPathStep = {
  fromNodeId: string;
  toNodeId: string;
  edgeId: string;
  relationshipType: string;
  strength: number;
};

export type GraphPath = {
  nodeIds: string[];
  steps: GraphPathStep[];
  totalHops: number;
};

export function findShortestPath(
  nodes: GraphNode[],
  edges: GraphEdge[],
  startNodeId: string,
  targetNodeId: string,
): GraphPath | null {
  if (startNodeId === targetNodeId) {
    return {
      nodeIds: [startNodeId],
      steps: [],
      totalHops: 0,
    };
  }

  type NeighborEdge = {
    neighborId: string;
    edge: GraphEdge;
  };

  const adj = new Map<string, NeighborEdge[]>();
  for (const node of nodes) {
    adj.set(node.id, []);
  }

  for (const edge of edges) {
    adj.get(edge.source)?.push({ neighborId: edge.target, edge });
    adj.get(edge.target)?.push({ neighborId: edge.source, edge });
  }

  const queue: string[] = [startNodeId];
  const visited = new Set<string>([startNodeId]);
  const parent = new Map<string, { prevNodeId: string; edge: GraphEdge }>();

  let found = false;

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === targetNodeId) {
      found = true;
      break;
    }

    const neighbors = adj.get(current) ?? [];
    neighbors.sort((a, b) => b.edge.strength - a.edge.strength);

    for (const { neighborId, edge } of neighbors) {
      if (!visited.has(neighborId)) {
        visited.add(neighborId);
        parent.set(neighborId, { prevNodeId: current, edge });
        queue.push(neighborId);
      }
    }
  }

  if (!found && !parent.has(targetNodeId)) {
    return null;
  }

  const nodeIds: string[] = [];
  const steps: GraphPathStep[] = [];
  let curr = targetNodeId;

  while (curr !== startNodeId) {
    nodeIds.unshift(curr);
    const p = parent.get(curr)!;
    steps.unshift({
      fromNodeId: p.prevNodeId,
      toNodeId: curr,
      edgeId: p.edge.id,
      relationshipType: p.edge.relationship_type,
      strength: p.edge.strength,
    });
    curr = p.prevNodeId;
  }
  nodeIds.unshift(startNodeId);

  return {
    nodeIds,
    steps,
    totalHops: steps.length,
  };
}

export type TopicCluster = {
  id: number;
  name: string;
  nodeIds: string[];
  topConceptNames: string[];
  colorIndex: number;
};

export function deriveClusterTopics(
  nodes: GraphNode[],
  edges: GraphEdge[],
  clusters: Map<string, number>,
): TopicCluster[] {
  const clusterMap = new Map<number, GraphNode[]>();

  for (const node of nodes) {
    const clusterId = clusters.get(node.id) ?? 0;
    if (!clusterMap.has(clusterId)) {
      clusterMap.set(clusterId, []);
    }
    clusterMap.get(clusterId)!.push(node);
  }

  const degrees = new Map<string, number>();
  for (const node of nodes) {
    degrees.set(node.id, 0);
  }
  for (const edge of edges) {
    degrees.set(edge.source, (degrees.get(edge.source) ?? 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) ?? 0) + 1);
  }

  const topicClusters: TopicCluster[] = [];

  for (const [clusterId, clusterNodes] of clusterMap.entries()) {
    clusterNodes.sort((a, b) => {
      const tfidfA = a.tfidf_score ?? 0;
      const tfidfB = b.tfidf_score ?? 0;
      if (tfidfB !== tfidfA) return tfidfB - tfidfA;
      if (b.total_occurrences !== a.total_occurrences) {
        return b.total_occurrences - a.total_occurrences;
      }
      return (degrees.get(b.id) ?? 0) - (degrees.get(a.id) ?? 0);
    });

    const topNames = clusterNodes.slice(0, 3).map((n) => n.label);

    const formatName = (str: string) =>
      str.replace(/\b\w/g, (char) => char.toUpperCase());

    let clusterTitle = "";
    if (topNames.length === 1) {
      clusterTitle = formatName(topNames[0]);
    } else if (topNames.length >= 2) {
      clusterTitle = `${formatName(topNames[0])} & ${formatName(topNames[1])}`;
    } else {
      clusterTitle = `Topic ${clusterId + 1}`;
    }

    topicClusters.push({
      id: clusterId,
      name: clusterTitle,
      nodeIds: clusterNodes.map((n) => n.id),
      topConceptNames: topNames,
      colorIndex: clusterId,
    });
  }

  topicClusters.sort((a, b) => b.nodeIds.length - a.nodeIds.length);
  return topicClusters;
}

export type PositionedNode = GraphNode & { x: number; y: number };

export function concentricLayout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width = 960,
  height = 640,
): PositionedNode[] {
  if (nodes.length === 0) return [];
  const centerX = width / 2;
  const centerY = height / 2;
  if (nodes.length === 1) {
    return [{ ...nodes[0], x: centerX, y: centerY }];
  }

  const centrality = computeBetweennessCentrality(nodes, edges);
  const degrees = new Map<string, number>();
  for (const node of nodes) {
    degrees.set(node.id, 0);
  }
  for (const edge of edges) {
    degrees.set(edge.source, (degrees.get(edge.source) ?? 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) ?? 0) + 1);
  }

  const scoredNodes = [...nodes].sort((a, b) => {
    const scoreA =
      (centrality.get(a.id) ?? 0) * 10 +
      (degrees.get(a.id) ?? 0) * 2 +
      Math.min(a.total_occurrences, 20);
    const scoreB =
      (centrality.get(b.id) ?? 0) * 10 +
      (degrees.get(b.id) ?? 0) * 2 +
      Math.min(b.total_occurrences, 20);
    return scoreB - scoreA;
  });

  const numHubs = Math.max(1, Math.min(4, Math.ceil(nodes.length * 0.15)));
  const numCore = Math.max(1, Math.ceil(nodes.length * 0.35));

  const ring0 = scoredNodes.slice(0, numHubs);
  const ring1 = scoredNodes.slice(numHubs, numHubs + numCore);
  const ring2 = scoredNodes.slice(numHubs + numCore);

  const radius0 = ring0.length === 1 ? 0 : 75;
  const radius1 = Math.min(width, height) * 0.28;
  const radius2 = Math.min(width, height) * 0.42;

  const rings: { nodes: GraphNode[]; radius: number }[] = [
    { nodes: ring0, radius: radius0 },
    { nodes: ring1, radius: radius1 },
    { nodes: ring2, radius: radius2 },
  ];

  const result: PositionedNode[] = [];

  for (const { nodes: ringNodes, radius } of rings) {
    const count = ringNodes.length;
    if (count === 0) continue;

    if (radius === 0 || count === 1) {
      result.push({
        ...ringNodes[0],
        x: centerX,
        y: centerY,
      });
      continue;
    }

    const angleStep = (2 * Math.PI) / count;
    for (let i = 0; i < count; i++) {
      const angle = -Math.PI / 2 + i * angleStep;
      result.push({
        ...ringNodes[i],
        x: Math.round(centerX + Math.cos(angle) * radius),
        y: Math.round(centerY + Math.sin(angle) * radius),
      });
    }
  }

  return result;
}

export async function getKnowledgeGraph({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: typeof fetch;
  workspaceId: string;
}): Promise<KnowledgeGraph> {
  const response = await fetchImplementation(
    `${apiBaseUrl.replace(/\/$/, "")}/api/v1/workspaces/${workspaceId}/graph`,
  );
  if (!response.ok) {
    throw new Error(`Graph request failed with status ${response.status}`);
  }
  return response.json() as Promise<KnowledgeGraph>;
}
