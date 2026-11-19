"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

import {
  computeBetweennessCentrality,
  concentricLayout,
  deriveClusterTopics,
  findBridgeConceptIds,
  findShortestPath,
  type GraphEdge,
  type GraphNode,
  type GraphPath,
  type KnowledgeGraph,
  type PositionedNode,
  type TopicCluster,
} from "../lib/graph";
import {
  ConceptDossier,
  ConceptMergeSuggestion,
  getConceptDossier,
  getMergeSuggestions,
  mergeConcepts,
  type WorkspaceConcept,
} from "../lib/concepts";
import {
  formatPredicate,
  getPredicateClass,
  getRelationshipEvidence,
  type RelationshipEvidence,
} from "../lib/relationships";

const WIDTH = 960;
const HEIGHT = 640;
const CENTER_X = WIDTH / 2;
const CENTER_Y = HEIGHT / 2;

// Subdued, calm editorial palette tailored for warm paper / parchment canvas
export const CLUSTER_THEMES = [
  { stroke: "#3d648f", fill: "#eaf1f8", text: "#1e395b" }, // Slate Blue
  { stroke: "#467551", fill: "#edf5ef", text: "#22472b" }, // Sage Green
  { stroke: "#8a6645", fill: "#f8f1ea", text: "#593d24" }, // Warm Clay
  { stroke: "#77567a", fill: "#f5edf7", text: "#4c324f" }, // Dusty Heather
  { stroke: "#85733e", fill: "#f7f4ea", text: "#52451f" }, // Muted Ochre
  { stroke: "#3f7370", fill: "#eaf5f4", text: "#214a47" }, // River Pine
  { stroke: "#8f5244", fill: "#faeee9", text: "#5f3025" }, // Faded Terracotta
];

function detectClusters(nodes: GraphNode[], edges: GraphEdge[]): Map<string, number> {
  const nodeIndex = new Map(nodes.map((n, i) => [n.id, i]));
  const labels = nodes.map((_, i) => i);

  for (let iter = 0; iter < 4; iter++) {
    for (let i = 0; i < nodes.length; i++) {
      const neighborWeights = new Map<number, number>();
      neighborWeights.set(labels[i], 1.0);

      for (const edge of edges) {
        const si = nodeIndex.get(edge.source);
        const ti = nodeIndex.get(edge.target);
        if (si === undefined || ti === undefined) continue;

        if (si === i) {
          const l = labels[ti];
          neighborWeights.set(l, (neighborWeights.get(l) ?? 0) + Math.max(edge.strength, 1));
        } else if (ti === i) {
          const l = labels[si];
          neighborWeights.set(l, (neighborWeights.get(l) ?? 0) + Math.max(edge.strength, 1));
        }
      }

      let maxWeight = -1;
      let bestLabel = labels[i];
      for (const [l, weight] of neighborWeights.entries()) {
        if (weight > maxWeight) {
          maxWeight = weight;
          bestLabel = l;
        }
      }
      labels[i] = bestLabel;
    }
  }

  const uniqueLabels = Array.from(new Set(labels));
  const labelToCluster = new Map(uniqueLabels.map((l, idx) => [l, idx]));

  const result = new Map<string, number>();
  for (let i = 0; i < nodes.length; i++) {
    result.set(nodes[i].id, labelToCluster.get(labels[i]) ?? 0);
  }
  return result;
}

function forceLayout(nodes: GraphNode[], edges: GraphEdge[], iterations = 90): PositionedNode[] {
  if (nodes.length === 0) return [];
  if (nodes.length === 1) {
    return [{ ...nodes[0], x: CENTER_X, y: CENTER_Y }];
  }

  const positioned: (PositionedNode & { vx: number; vy: number })[] = nodes.map((node, i) => {
    const angle = i * 2.399963;
    const r = Math.min(WIDTH, HEIGHT) * 0.36 * Math.sqrt((i + 0.5) / Math.max(nodes.length, 1));
    return {
      ...node,
      x: CENTER_X + Math.cos(angle) * r,
      y: CENTER_Y + Math.sin(angle) * r,
      vx: 0,
      vy: 0,
    };
  });

  const nodeIndex = new Map(positioned.map((n, i) => [n.id, i]));
  const deg = new Array(nodes.length).fill(0);
  for (const edge of edges) {
    const si = nodeIndex.get(edge.source);
    const ti = nodeIndex.get(edge.target);
    if (si !== undefined && ti !== undefined) {
      deg[si]++;
      deg[ti]++;
    }
  }

  const minDist = 110;

  for (let iter = 0; iter < iterations; iter++) {
    const alpha = Math.max(0.04, 1 - iter / iterations);

    // Repulsion
    for (let i = 0; i < positioned.length; i++) {
      for (let j = i + 1; j < positioned.length; j++) {
        const dx = positioned[j].x - positioned[i].x;
        const dy = positioned[j].y - positioned[i].y;
        const dist = Math.max(Math.hypot(dx, dy), 1);
        const force = (45000 / (dist * dist)) * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        positioned[i].vx -= fx;
        positioned[i].vy -= fy;
        positioned[j].vx += fx;
        positioned[j].vy += fy;

        if (dist < minDist) {
          const overlap = (minDist - dist) / dist;
          const push = overlap * 0.45 * alpha;
          positioned[i].vx -= dx * push;
          positioned[i].vy -= dy * push;
          positioned[j].vx += dx * push;
          positioned[j].vy += dy * push;

          if (iter > iterations * 0.5) {
            const hardPush = (minDist - dist) * 0.25;
            const nx = dx / dist;
            const ny = dy / dist;
            positioned[i].x -= nx * hardPush;
            positioned[i].y -= ny * hardPush;
            positioned[j].x += nx * hardPush;
            positioned[j].y += ny * hardPush;
          }
        }
      }
    }

    // Springs
    for (const edge of edges) {
      const si = nodeIndex.get(edge.source);
      const ti = nodeIndex.get(edge.target);
      if (si === undefined || ti === undefined) continue;
      const dx = positioned[ti].x - positioned[si].x;
      const dy = positioned[ti].y - positioned[si].y;
      const dist = Math.max(Math.hypot(dx, dy), 1);
      const targetDist = 180;
      const degreeFactor = Math.sqrt(Math.max(deg[si], 1) * Math.max(deg[ti], 1));
      const kSpring = (0.06 / Math.max(1, degreeFactor * 0.35)) * alpha;
      const spring = (dist - targetDist) * kSpring;
      const fx = (dx / dist) * spring;
      const fy = (dy / dist) * spring;
      positioned[si].vx += fx;
      positioned[si].vy += fy;
      positioned[ti].vx -= fx;
      positioned[ti].vy -= fy;
    }

    // Centering gravity
    for (const node of positioned) {
      node.vx += (CENTER_X - node.x) * 0.006 * alpha;
      node.vy += (CENTER_Y - node.y) * 0.006 * alpha;
    }

    // Bounds & velocity damping
    for (const node of positioned) {
      node.x = Math.max(80, Math.min(WIDTH - 80, node.x + node.vx));
      node.y = Math.max(70, Math.min(HEIGHT - 70, node.y + node.vy));
      node.vx *= 0.65;
      node.vy *= 0.65;
    }
  }

  return positioned.map(({ vx, vy, ...node }) => node);
}

function truncateLabel(label: string, isExpanded: boolean): string {
  if (isExpanded || label.length <= 18) return label;
  return `${label.slice(0, 17)}…`;
}

function highlightKeywords(text: string, kw1: string, kw2: string) {
  if (!text) return null;
  const words = [...kw1.split(/\s+/), ...kw2.split(/\s+/)].filter((w) => w.length >= 3);
  if (words.length === 0) return text;
  const pattern = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, idx) => {
    if (words.some((w) => w.toLowerCase() === part.toLowerCase())) {
      return (
        <mark className="snippet-highlight" key={idx}>
          {part}
        </mark>
      );
    }
    return part;
  });
}

export function KnowledgeGraphView({
  graph,
  apiBaseUrl,
  workspaceId,
  selectedConnectionId,
  onClearConnection,
  onWorkspaceRefresh,
  activeDocumentFilter,
  onClearDocumentFilter,
  concepts,
  isToolbarOpen = true,
  onToggleToolbar,
  layoutMode: controlledLayoutMode,
  onLayoutModeChange,
}: {
  graph: KnowledgeGraph;
  apiBaseUrl?: string;
  workspaceId?: string;
  selectedConnectionId?: string | null;
  onClearConnection?: () => void;
  onWorkspaceRefresh?: () => void;
  activeDocumentFilter?: { id: string; name: string } | "shared" | null;
  onClearDocumentFilter?: () => void;
  concepts?: WorkspaceConcept[];
  isToolbarOpen?: boolean;
  onToggleToolbar?: () => void;
  layoutMode?: "force" | "concentric";
  onLayoutModeChange?: (mode: "force" | "concentric") => void;
}) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterBridgesOnly, setFilterBridgesOnly] = useState(false);
  const [minimumStrength, setMinimumStrength] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [customPositions, setCustomPositions] = useState<Map<string, { x: number; y: number }>>(
    () => new Map(),
  );

  const [evidence, setEvidence] = useState<RelationshipEvidence[] | null>(null);
  const [isLoadingEvidence, setIsLoadingEvidence] = useState(false);

  // Concept merge suggestions and manual alias merging
  const [mergeSuggestions, setMergeSuggestions] = useState<ConceptMergeSuggestion[]>([]);
  const [isMerging, setIsMerging] = useState(false);
  const [isManualMergeOpen, setIsManualMergeOpen] = useState(false);
  const [manualTargetId, setManualTargetId] = useState("");

  // Topic cluster filter and Connection Path Finder
  const [activeTopicClusterId, setActiveTopicClusterId] = useState<number | null>(null);
  const [activePath, setActivePath] = useState<GraphPath | null>(null);
  const [isPathFinderOpen, setIsPathFinderOpen] = useState(false);
  const [pathTargetId, setPathTargetId] = useState("");
  const [pathError, setPathError] = useState<string | null>(null);

  // Layout mode & Label density & Minimap
  const [internalLayoutMode, setInternalLayoutMode] = useState<"force" | "concentric">("force");
  const layoutMode = controlledLayoutMode ?? internalLayoutMode;
  const setLayoutMode = onLayoutModeChange ?? setInternalLayoutMode;

  const [labelDensity, setLabelDensity] = useState<"all" | "hubs" | "hover">("all");
  const [isMinimapVisible, setIsMinimapVisible] = useState(true);

  // Concept TextRank Dossier
  const [dossier, setDossier] = useState<ConceptDossier | null>(null);
  const [isLoadingDossier, setIsLoadingDossier] = useState(false);

  const isDraggingCanvasRef = useRef(false);
  const canvasDragStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const nodeDragRef = useRef<{
    id: string;
    startX: number;
    startY: number;
    origX: number;
    origY: number;
    hasMoved: boolean;
  } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const touchPointersRef = useRef(new Map<number, { x: number; y: number }>());
  const pinchRef = useRef<{
    distance: number;
    zoom: number;
    anchor: { x: number; y: number };
  } | null>(null);
  const suppressTouchClickRef = useRef(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const maxStrength = Math.max(...graph.edges.map((edge) => edge.strength), 1);
  const effectiveMinimumStrength = Math.min(minimumStrength, Math.ceil(maxStrength));

  // Sync selected connection from parent (e.g. document filter or external trigger)
  useEffect(() => {
    if (selectedConnectionId) {
      setSelectedEdgeId(selectedConnectionId);
      setSelectedNodeId(null);
    }
  }, [selectedConnectionId]);

  // Global hotkey '/' to focus search, and 'Escape' to deselect/close inspector
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "/" && document.activeElement !== searchInputRef.current) {
        e.preventDefault();
        searchInputRef.current?.focus();
      } else if (e.key === "Escape") {
        if (selectedNodeId !== null || selectedEdgeId !== null) {
          setSelectedNodeId(null);
          setSelectedEdgeId(null);
          if (onClearConnection) onClearConnection();
        } else if (activePath !== null) {
          setActivePath(null);
        } else if (searchQuery) {
          setSearchQuery("");
          searchInputRef.current?.blur();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedNodeId, selectedEdgeId, activePath, searchQuery, onClearConnection]);

  // Fetch relationship evidence when an edge is selected
  useEffect(() => {
    if (!selectedEdgeId || !apiBaseUrl || !workspaceId) {
      setEvidence(null);
      return;
    }
    let isCurrent = true;
    setIsLoadingEvidence(true);
    getRelationshipEvidence({
      apiBaseUrl,
      fetchImplementation: window.fetch.bind(window),
      workspaceId,
      relationshipId: selectedEdgeId,
    })
      .then((data) => {
        if (isCurrent) setEvidence(data);
      })
      .catch(() => {
        if (isCurrent) setEvidence([]);
      })
      .finally(() => {
        if (isCurrent) setIsLoadingEvidence(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedEdgeId, apiBaseUrl, workspaceId]);

  // Fetch concept dossier (classical TextRank summary) when a node is selected
  useEffect(() => {
    if (!selectedNodeId || !apiBaseUrl || !workspaceId) {
      setDossier(null);
      return;
    }
    let isCurrent = true;
    setIsLoadingDossier(true);
    getConceptDossier({
      apiBaseUrl,
      fetchImplementation: window.fetch.bind(window),
      workspaceId,
      conceptId: selectedNodeId,
    })
      .then((data) => {
        if (isCurrent) setDossier(data);
      })
      .catch(() => {
        if (isCurrent) setDossier(null);
      })
      .finally(() => {
        if (isCurrent) setIsLoadingDossier(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedNodeId, apiBaseUrl, workspaceId]);

  // Fetch merge suggestions for the workspace
  useEffect(() => {
    if (!apiBaseUrl || !workspaceId) return;
    let isCurrent = true;
    getMergeSuggestions({
      apiBaseUrl,
      fetchImplementation: window.fetch.bind(window),
      workspaceId,
    })
      .then((data) => {
        if (isCurrent) setMergeSuggestions(data);
      })
      .catch(() => {
        if (isCurrent) setMergeSuggestions([]);
      });

    return () => {
      isCurrent = false;
    };
  }, [apiBaseUrl, workspaceId, graph]);

  async function handleMerge(
    sourceId: string,
    targetId: string,
    sourceName: string,
    targetName: string,
  ) {
    if (!apiBaseUrl || !workspaceId || isMerging) return;
    const confirmed = window.confirm(
      `Merge "${sourceName}" into "${targetName}"?\n\nThis will combine mentions, update relationships, and remove the alias permanently.`,
    );
    if (!confirmed) return;

    setIsMerging(true);
    try {
      await mergeConcepts({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId,
        sourceConceptId: sourceId,
        targetConceptId: targetId,
      });
      setSelectedNodeId(null);
      if (onWorkspaceRefresh) onWorkspaceRefresh();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to merge concepts.");
    } finally {
      setIsMerging(false);
    }
  }

  useEffect(() => {
    setCustomPositions(new Map());
  }, [graph.nodes, layoutMode]);

  const visibleEdges = useMemo(
    () => graph.edges.filter((edge) => edge.strength >= effectiveMinimumStrength),
    [graph.edges, effectiveMinimumStrength],
  );

  const nodeDegrees = useMemo(() => {
    const deg = new Map<string, number>();
    for (const n of graph.nodes) {
      deg.set(n.id, 0);
    }
    for (const e of visibleEdges) {
      deg.set(e.source, (deg.get(e.source) ?? 0) + 1);
      deg.set(e.target, (deg.get(e.target) ?? 0) + 1);
    }
    return deg;
  }, [graph.nodes, visibleEdges]);

  const forceNodes = useMemo(
    () => forceLayout(graph.nodes, graph.edges),
    [graph.nodes, graph.edges],
  );

  const concentricNodes = useMemo(
    () => concentricLayout(graph.nodes, visibleEdges, WIDTH, HEIGHT),
    [graph.nodes, visibleEdges],
  );

  const computedNodes = layoutMode === "concentric" ? concentricNodes : forceNodes;

  const nodes = useMemo(() => {
    if (customPositions.size === 0) return computedNodes;
    return computedNodes.map((node) => {
      const custom = customPositions.get(node.id);
      return custom ? { ...node, x: custom.x, y: custom.y } : node;
    });
  }, [computedNodes, customPositions]);

  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  const conceptById = useMemo(() => {
    return new Map(concepts?.map((c) => [c.id, c]) ?? []);
  }, [concepts]);

  const documentFilterMatches = useMemo(() => {
    if (!activeDocumentFilter) return null;
    const matches = new Set<string>();
    for (const node of graph.nodes) {
      if (activeDocumentFilter === "shared") {
        if (node.document_count >= 2) {
          matches.add(node.id);
        }
      } else {
        const c = conceptById.get(node.id);
        if (c?.source_documents?.includes(activeDocumentFilter.name)) {
          matches.add(node.id);
        }
      }
    }
    return matches;
  }, [activeDocumentFilter, graph.nodes, conceptById]);

  // Community Detection (Clusters)
  const nodeClusters = useMemo(
    () => detectClusters(graph.nodes, visibleEdges),
    [graph.nodes, visibleEdges],
  );

  // Auto-named Topic Clusters for legend filter
  const topicClusters = useMemo(
    () => deriveClusterTopics(graph.nodes, visibleEdges, nodeClusters),
    [graph.nodes, visibleEdges, nodeClusters],
  );

  // Active path node/edge lookups
  const pathNodeIds = useMemo(() => new Set(activePath?.nodeIds ?? []), [activePath]);
  const pathEdgeIds = useMemo(
    () => new Set(activePath?.steps.map((s) => s.edgeId) ?? []),
    [activePath],
  );

  const sortedVisibleEdges = useMemo(() => {
    if (!activePath) return visibleEdges;
    return [...visibleEdges].sort((a, b) => {
      const aPath = pathEdgeIds.has(a.id) ? 1 : 0;
      const bPath = pathEdgeIds.has(b.id) ? 1 : 0;
      return aPath - bPath;
    });
  }, [visibleEdges, activePath, pathEdgeIds]);

  // Betweenness Centrality & Bridge Concept Detection
  const betweennessScores = useMemo(
    () => computeBetweennessCentrality(graph.nodes, visibleEdges),
    [graph.nodes, visibleEdges],
  );

  const bridgeNodeIds = useMemo(
    () => findBridgeConceptIds(graph.nodes, visibleEdges),
    [graph.nodes, visibleEdges],
  );

  const presets = useMemo(() => {
    if (graph.edges.length <= 25 || maxStrength <= 2) return null;
    const sorted = graph.edges.map((e) => e.strength).sort((a, b) => a - b);
    const median = Math.ceil(sorted[Math.floor(sorted.length * 0.6)] ?? 2);
    const topTier = Math.ceil(sorted[Math.floor(sorted.length * 0.85)] ?? 4);
    return {
      all: 1,
      key: Math.max(2, median),
      top: Math.max(median + 1, topTier),
    };
  }, [graph.edges, maxStrength]);

  const activeFocusId = selectedNodeId ?? hoveredNodeId;

  // Selected edge object
  const selectedEdge = useMemo(
    () => (selectedEdgeId ? visibleEdges.find((e) => e.id === selectedEdgeId) ?? null : null),
    [selectedEdgeId, visibleEdges],
  );

  // Neighbors of active focus node
  const neighborInfo = useMemo(() => {
    if (!activeFocusId) return { neighborIds: new Set<string>(), neighbors: [] };
    const neighborIds = new Set<string>();
    const neighbors: {
      id: string;
      label: string;
      strength: number;
      pmi?: number;
      npmi?: number;
      edgeId: string;
      predicate: string;
      direction: "outgoing" | "incoming" | "undirected";
    }[] = [];

    for (const edge of visibleEdges) {
      if (edge.source === activeFocusId) {
        neighborIds.add(edge.target);
        const targetNode = nodeById.get(edge.target);
        if (targetNode) {
          neighbors.push({
            id: targetNode.id,
            label: targetNode.label,
            strength: edge.strength,
            pmi: edge.pmi,
            npmi: edge.npmi,
            edgeId: edge.id,
            predicate: edge.relationship_type,
            direction: edge.relationship_type === "co_occurs_with" ? "undirected" : "outgoing",
          });
        }
      } else if (edge.target === activeFocusId) {
        neighborIds.add(edge.source);
        const sourceNode = nodeById.get(edge.source);
        if (sourceNode) {
          neighbors.push({
            id: sourceNode.id,
            label: sourceNode.label,
            strength: edge.strength,
            pmi: edge.pmi,
            npmi: edge.npmi,
            edgeId: edge.id,
            predicate: edge.relationship_type,
            direction: edge.relationship_type === "co_occurs_with" ? "undirected" : "incoming",
          });
        }
      }
    }
    neighbors.sort((a, b) => b.strength - a.strength);
    return { neighborIds, neighbors };
  }, [activeFocusId, visibleEdges, nodeById]);

  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? null;

  // Search filter
  const isSearchActive = searchQuery.trim().length > 0;
  const searchMatches = useMemo(() => {
    if (!isSearchActive) return new Set<string>();
    const query = searchQuery.trim().toLowerCase();
    return new Set(nodes.filter((n) => n.label.toLowerCase().includes(query)).map((n) => n.id));
  }, [searchQuery, isSearchActive, nodes]);

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && searchMatches.size > 0) {
      const firstMatchId = Array.from(searchMatches)[0];
      const matchNode = nodeById.get(firstMatchId);
      if (matchNode) {
        setSelectedNodeId(matchNode.id);
        setSelectedEdgeId(null);
        setPan({
          x: CENTER_X - matchNode.x * zoom,
          y: CENTER_Y - matchNode.y * zoom,
        });
      }
    } else if (e.key === "Escape") {
      setSearchQuery("");
      searchInputRef.current?.blur();
    }
  }

  // Canvas pan handlers
  function screenPointToGraph(x: number, y: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect?.width || !rect.height) return { x, y };
    const scale = Math.min(rect.width / WIDTH, rect.height / HEIGHT);
    return {
      x: (x - rect.left - (rect.width - WIDTH * scale) / 2) / scale,
      y: (y - rect.top - (rect.height - HEIGHT * scale) / 2) / scale,
    };
  }

  // Capture touch pointers before node handlers so pinching also works over nodes.
  function handleTouchPointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (event.pointerType !== "touch") return;
    const pointers = touchPointersRef.current;
    if (pointers.size === 0) suppressTouchClickRef.current = false;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size < 2) return;
    event.preventDefault();
    event.stopPropagation();
    if (pinchRef.current) return;
    const [a, b] = Array.from(pointers.values());
    const midpoint = screenPointToGraph((a.x + b.x) / 2, (a.y + b.y) / 2);
    pinchRef.current = {
      distance: Math.max(1, Math.hypot(b.x - a.x, b.y - a.y)),
      zoom,
      anchor: { x: (midpoint.x - pan.x) / zoom, y: (midpoint.y - pan.y) / zoom },
    };
    suppressTouchClickRef.current = true;
    nodeDragRef.current = null;
    isDraggingCanvasRef.current = false;
    setHoveredNodeId(null);
    for (const id of pointers.keys()) event.currentTarget.setPointerCapture(id);
  }

  function handleTouchPointerMove(event: React.PointerEvent<SVGSVGElement>) {
    if (event.pointerType !== "touch" || !touchPointersRef.current.has(event.pointerId)) return;
    const pointers = touchPointersRef.current;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const pinch = pinchRef.current;
    if (!pinch) return;
    event.preventDefault();
    event.stopPropagation();
    if (pointers.size < 2) return;
    const [a, b] = Array.from(pointers.values());
    const next = Math.max(0.4, Math.min(3,
      pinch.zoom * Math.hypot(b.x - a.x, b.y - a.y) / pinch.distance,
    ));
    const midpoint = screenPointToGraph((a.x + b.x) / 2, (a.y + b.y) / 2);
    setZoom(next);
    setPan({ x: midpoint.x - pinch.anchor.x * next, y: midpoint.y - pinch.anchor.y * next });
  }

  function handleTouchPointerEnd(event: React.PointerEvent<SVGSVGElement>) {
    if (event.pointerType !== "touch") return;
    touchPointersRef.current.delete(event.pointerId);
    if (!pinchRef.current) return;
    event.stopPropagation();
    // Keep the gesture active until both fingers lift, preventing accidental node taps.
    if (touchPointersRef.current.size === 0) pinchRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // The browser may already have released a cancelled pointer.
    }
  }

  function screenDeltaToGraph(dx: number, dy: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    const scale = rect && rect.width && rect.height
      ? Math.min(rect.width / WIDTH, rect.height / HEIGHT)
      : 1;
    return { x: dx / scale, y: dy / scale };
  }

  function zoomBy(factor: number) {
    const next = Math.max(0.4, Math.min(3, zoom * factor));
    const ratio = next / zoom;
    setPan({
      x: CENTER_X - (CENTER_X - pan.x) * ratio,
      y: CENTER_Y - (CENTER_Y - pan.y) * ratio,
    });
    setZoom(next);
  }

  function handleCanvasPointerDown(event: React.PointerEvent<SVGSVGElement>) {
    const target = event.target as HTMLElement;
    if (target.closest(".graph-node") || target.closest(".graph-edge")) return;

    // Deselect on blank canvas click
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    if (onClearConnection) onClearConnection();

    isDraggingCanvasRef.current = true;
    canvasDragStartRef.current = {
      x: event.clientX,
      y: event.clientY,
      panX: pan.x,
      panY: pan.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleCanvasPointerMove(event: React.PointerEvent<SVGSVGElement>) {
    if (nodeDragRef.current) {
      const dx = event.clientX - nodeDragRef.current.startX;
      const dy = event.clientY - nodeDragRef.current.startY;
      if (!nodeDragRef.current.hasMoved && Math.hypot(dx, dy) < 4) return;
      nodeDragRef.current.hasMoved = true;
      const delta = screenDeltaToGraph(dx, dy);
      const svgDx = delta.x / zoom;
      const svgDy = delta.y / zoom;
      const newX = Math.max(50, Math.min(WIDTH - 50, nodeDragRef.current.origX + svgDx));
      const newY = Math.max(40, Math.min(HEIGHT - 40, nodeDragRef.current.origY + svgDy));
      setCustomPositions((prev) => {
        const next = new Map(prev);
        next.set(nodeDragRef.current!.id, { x: newX, y: newY });
        return next;
      });
      return;
    }

    if (!isDraggingCanvasRef.current) return;
    const dx = event.clientX - canvasDragStartRef.current.x;
    const dy = event.clientY - canvasDragStartRef.current.y;
    const delta = screenDeltaToGraph(dx, dy);
    setPan({
      x: canvasDragStartRef.current.panX + delta.x,
      y: canvasDragStartRef.current.panY + delta.y,
    });
  }

  function handleCanvasPointerUp(event: React.PointerEvent<SVGSVGElement>) {
    isDraggingCanvasRef.current = false;
    nodeDragRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Ignore
    }
  }

  function handleNodePointerDown(event: React.PointerEvent<SVGGElement>, node: PositionedNode) {
    event.stopPropagation();
    nodeDragRef.current = {
      id: node.id,
      startX: event.clientX,
      startY: event.clientY,
      origX: node.x,
      origY: node.y,
      hasMoved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleNodePointerUp(event: React.PointerEvent<SVGGElement>, node: PositionedNode) {
    event.stopPropagation();
    const hasMoved = nodeDragRef.current?.hasMoved;
    nodeDragRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Ignore
    }
    if (!hasMoved) {
      setSelectedNodeId((prev) => (prev === node.id ? null : node.id));
      setSelectedEdgeId(null);
      if (onClearConnection) onClearConnection();
    }
  }

  function handleEdgeClick(event: React.MouseEvent, edge: GraphEdge) {
    event.stopPropagation();
    setSelectedEdgeId((prev) => (prev === edge.id ? null : edge.id));
    setSelectedNodeId(null);
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const delta = event.deltaY > 0 ? 0.9 : 1.1;
    zoomBy(delta);
  }

  function handleMinimapClick(event: React.MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const clickY = event.clientY - rect.top;
    const normX = Math.max(0, Math.min(1, clickX / rect.width));
    const normY = Math.max(0, Math.min(1, clickY / rect.height));
    const targetSvgX = normX * WIDTH;
    const targetSvgY = normY * HEIGHT;

    setPan({
      x: CENTER_X - targetSvgX * zoom,
      y: CENTER_Y - targetSvgY * zoom,
    });
  }

  function resetView() {
    setPan({ x: 0, y: 0 });
    setZoom(1);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setHoveredNodeId(null);
    setSearchQuery("");
    setFilterBridgesOnly(false);
    setCustomPositions(new Map());
    setActiveTopicClusterId(null);
    setActivePath(null);
    setIsPathFinderOpen(false);
    setPathTargetId("");
    setPathError(null);
    setLabelDensity("all");
    setDossier(null);
    if (onClearConnection) onClearConnection();
  }

  function handleExportJSON() {
    const blob = new Blob([JSON.stringify(graph, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "nodesh-knowledge-graph.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  function handleExportPNG() {
    if (!svgRef.current) return;
    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svgRef.current);
    const canvas = document.createElement("canvas");
    canvas.width = WIDTH * 2;
    canvas.height = HEIGHT * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      ctx.fillStyle = "#f2efe9";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      const pngUrl = canvas.toDataURL("image/png");
      const downloadLink = document.createElement("a");
      downloadLink.href = pngUrl;
      downloadLink.download = "nodesh-knowledge-graph.png";
      downloadLink.click();
    };
    img.src = url;
  }

  const sortedNodes = useMemo(() => {
    return [...nodes].sort((a, b) => {
      if (activePath) {
        const aPath = pathNodeIds.has(a.id) ? 1 : 0;
        const bPath = pathNodeIds.has(b.id) ? 1 : 0;
        if (aPath !== bPath) return aPath - bPath;
      }
      const aIsActive = a.id === activeFocusId;
      const bIsActive = b.id === activeFocusId;
      if (aIsActive) return 1;
      if (bIsActive) return -1;
      const aNeighbor = neighborInfo.neighborIds.has(a.id);
      const bNeighbor = neighborInfo.neighborIds.has(b.id);
      if (aNeighbor && !bNeighbor) return 1;
      if (!aNeighbor && bNeighbor) return -1;
      return 0;
    });
  }, [nodes, activePath, pathNodeIds, activeFocusId, neighborInfo.neighborIds]);

  if (graph.nodes.length === 0) {
    return (
      <div className="graph-empty-state">
        <p className="empty-title">Knowledge graph empty</p>
        <span className="empty-subtitle">Upload files in the document navigator to construct your knowledge map.</span>
      </div>
    );
  }

  const isInspectorOpen = Boolean(selectedNode || selectedEdge);

  return (
    <div className={`graph-layout-container${isInspectorOpen ? " with-inspector" : ""}`}>
      {/* CENTRAL DOMINANT GRAPH SURFACE */}
      <div className="graph-surface-area">
        {/* QUIET COLLAPSIBLE TOOLBAR */}
        {isToolbarOpen && (
          <div className="graph-quiet-toolbar">
            <div className="toolbar-controls-row">
              {/* Quick Concept Search */}
              <div className="toolbar-search">
                <svg
                  className="search-icon"
                  fill="none"
                  height="13"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                  width="13"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" x2="16.65" y1="21" y2="16.65" />
                </svg>
                <input
                  className="toolbar-search-input"
                  aria-label="Search concepts"
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  placeholder="Search concepts... (/)"
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                />
                {searchQuery && (
                  <button
                    className="toolbar-clear-btn"
                    onClick={() => setSearchQuery("")}
                    title="Clear search"
                    type="button"
                  >
                    ×
                  </button>
                )}
              </div>

              {/* Min strength slider */}
              <div className="strength-control">
                <label htmlFor="strength-filter">
                  Min strength: <strong>{effectiveMinimumStrength}</strong>
                </label>
                <input
                  id="strength-filter"
                  max={Math.ceil(maxStrength)}
                  min="1"
                  onChange={(event) => setMinimumStrength(Number(event.target.value))}
                  type="range"
                  value={effectiveMinimumStrength}
                />
                <span className="strength-count-text">
                  {visibleEdges.length} of {graph.edges.length}
                </span>
              </div>

              {/* Filter Presets */}
              <div className="quiet-filter-group">
                {presets && (
                  <>
                    <button
                      className={`quiet-chip${effectiveMinimumStrength === presets.all && !filterBridgesOnly ? " quiet-chip-active" : ""}`}
                      onClick={() => {
                        setMinimumStrength(presets.all);
                        setFilterBridgesOnly(false);
                      }}
                      type="button"
                    >
                      All
                    </button>
                    <button
                      className={`quiet-chip${effectiveMinimumStrength === presets.key && !filterBridgesOnly ? " quiet-chip-active" : ""}`}
                      onClick={() => {
                        setMinimumStrength(presets.key);
                        setFilterBridgesOnly(false);
                      }}
                      type="button"
                    >
                      Key
                    </button>
                    {presets.top > presets.key && (
                      <button
                        className={`quiet-chip${effectiveMinimumStrength === presets.top && !filterBridgesOnly ? " quiet-chip-active" : ""}`}
                        onClick={() => {
                          setMinimumStrength(presets.top);
                          setFilterBridgesOnly(false);
                        }}
                        type="button"
                      >
                        Top
                      </button>
                    )}
                  </>
                )}
                {bridgeNodeIds.size > 0 && (
                  <button
                    className={`quiet-chip${filterBridgesOnly ? " quiet-chip-active" : ""}`}
                    onClick={() => setFilterBridgesOnly((prev) => !prev)}
                    title="Highlight concepts bridging different knowledge clusters"
                    type="button"
                  >
                    Bridges ({bridgeNodeIds.size})
                  </button>
                )}
              </div>

              {/* Label Density Controls */}
              <div aria-label="Label density" className="density-toggle" role="group">
                <span className="density-caption">Labels:</span>
                <button
                  className={`quiet-chip${labelDensity === "all" ? " quiet-chip-active" : ""}`}
                  onClick={() => setLabelDensity("all")}
                  title="Display labels on all concepts"
                  type="button"
                >
                  All
                </button>
                <button
                  className={`quiet-chip${labelDensity === "hubs" ? " quiet-chip-active" : ""}`}
                  onClick={() => setLabelDensity("hubs")}
                  title="Display labels on key hubs and bridge concepts only"
                  type="button"
                >
                  Hubs
                </button>
                <button
                  className={`quiet-chip${labelDensity === "hover" ? " quiet-chip-active" : ""}`}
                  onClick={() => setLabelDensity("hover")}
                  title="Display labels only on hover or selection"
                  type="button"
                >
                  Hover
                </button>
              </div>

              {/* Secondary Actions */}
              <label className="mobile-layout-control">
                Layout
                <select aria-label="Graph layout" value={layoutMode} onChange={(event) => setLayoutMode(event.target.value as "force" | "concentric")}>
                  <option value="force">Organic</option>
                  <option value="concentric">Concentric</option>
                </select>
              </label>
              <div className="toolbar-actions-group">
                <button className="btn-quiet-action" onClick={resetView} title="Reset camera pan and zoom" type="button">
                  Reset
                </button>
                <button className="btn-quiet-action" onClick={handleExportPNG} title="Download canvas PNG image" type="button">
                  PNG
                </button>
                <button className="btn-quiet-action" onClick={handleExportJSON} title="Download graph JSON file" type="button">
                  JSON
                </button>
              </div>
            </div>

            {/* Subdued Topic Clusters Legend Bar (Only shown when > 1 cluster) */}
            {topicClusters.length > 1 && (
              <div aria-label="Topic cluster filters" className="topic-legend-strip" role="navigation">
                <span className="topic-legend-caption">Topics:</span>
                <div className="topic-chips-scroll">
                  <button
                    className={`topic-pill${activeTopicClusterId === null ? " topic-pill-active" : ""}`}
                    onClick={() => setActiveTopicClusterId(null)}
                    type="button"
                  >
                    All ({nodes.length})
                  </button>
                  {topicClusters.map((cluster) => {
                    const isClusterActive = activeTopicClusterId === cluster.id;
                    const theme = CLUSTER_THEMES[cluster.colorIndex % CLUSTER_THEMES.length];
                    return (
                      <button
                        className={`topic-pill${isClusterActive ? " topic-pill-active" : ""}`}
                        key={cluster.id}
                        onClick={() =>
                          setActiveTopicClusterId((prev) =>
                            prev === cluster.id ? null : cluster.id,
                          )
                        }
                        style={
                          isClusterActive
                            ? {
                                borderColor: theme.stroke,
                                backgroundColor: theme.fill,
                                color: theme.text,
                              }
                            : undefined
                        }
                        title={`Cluster: ${cluster.topConceptNames.join(", ")}`}
                        type="button"
                      >
                        <span
                          className="topic-indicator-dot"
                          style={{ backgroundColor: theme.stroke }}
                        />
                        <span className="topic-pill-name">{cluster.name}</span>
                        <span className="topic-pill-count">{cluster.nodeIds.length}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* CANVAS WORKSPACE */}
        <div className="graph-canvas-container">
          <svg
            aria-label="Interactive concept network"
            className="graph-canvas"
            onPointerDownCapture={handleTouchPointerDown}
            onPointerMoveCapture={handleTouchPointerMove}
            onPointerUpCapture={handleTouchPointerEnd}
            onPointerCancelCapture={handleTouchPointerEnd}
            onClickCapture={(event) => {
              if (suppressTouchClickRef.current) {
                event.preventDefault();
                event.stopPropagation();
              }
            }}
            onPointerDown={handleCanvasPointerDown}
            onPointerMove={handleCanvasPointerMove}
            onPointerUp={handleCanvasPointerUp}
            onPointerCancel={handleCanvasPointerUp}
            onWheel={handleWheel}
            preserveAspectRatio="xMidYMid meet"
            ref={svgRef}
            role="img"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          >
            <defs>
              <marker
                id="graph-arrow"
                markerHeight="6"
                markerUnits="strokeWidth"
                markerWidth="6"
                orient="auto"
                refX="5"
                refY="3"
              >
                <polygon fill="#a8a29e" points="0 1, 6 3, 0 5" />
              </marker>
              <marker
                id="graph-arrow-highlighted"
                markerHeight="7"
                markerUnits="strokeWidth"
                markerWidth="7"
                orient="auto"
                refX="5"
                refY="3.5"
              >
                <polygon fill="#b45309" points="0 1, 7 3.5, 0 6" />
              </marker>
              <marker
                id="graph-arrow-path"
                markerHeight="7"
                markerUnits="strokeWidth"
                markerWidth="7"
                orient="auto"
                refX="5"
                refY="3.5"
              >
                <polygon fill="#b45309" points="0 1, 7 3.5, 0 6" />
              </marker>
              <marker
                id="graph-arrow-dimmed"
                markerHeight="5"
                markerUnits="strokeWidth"
                markerWidth="5"
                orient="auto"
                refX="4"
                refY="2.5"
              >
                <polygon fill="#d6d3d1" opacity="0.4" points="0 1, 5 2.5, 0 4" />
              </marker>
            </defs>
            <rect fill="#f2efe9" height={HEIGHT} width={WIDTH} />
            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Edges layer */}
              {sortedVisibleEdges.map((edge) => {
                const source = nodeById.get(edge.source);
                const target = nodeById.get(edge.target);
                if (!source || !target) return null;

                const isPathEdge = pathEdgeIds.has(edge.id);
                const isSelectedEdge = edge.id === selectedEdgeId;
                const isConnectedToActiveNode =
                  activeFocusId !== null &&
                  (edge.source === activeFocusId || edge.target === activeFocusId);
                const isHighlighted = isPathEdge || isSelectedEdge || isConnectedToActiveNode;

                const isBridgeModeActive = filterBridgesOnly && bridgeNodeIds.size > 0;
                const isIncidentToBridge = bridgeNodeIds.has(edge.source) || bridgeNodeIds.has(edge.target);
                const isDocFiltered =
                  documentFilterMatches !== null &&
                  (!documentFilterMatches.has(edge.source) || !documentFilterMatches.has(edge.target));

                const isDimmed =
                  activePath !== null
                    ? !isPathEdge
                    : activeTopicClusterId !== null
                    ? nodeClusters.get(edge.source) !== activeTopicClusterId ||
                      nodeClusters.get(edge.target) !== activeTopicClusterId
                    : (activeFocusId !== null && !isConnectedToActiveNode) ||
                      (selectedEdgeId !== null && !isSelectedEdge) ||
                      (isSearchActive && (!searchMatches.has(edge.source) || !searchMatches.has(edge.target))) ||
                      (isBridgeModeActive && activeFocusId === null && selectedEdgeId === null && !isIncidentToBridge) ||
                      (documentFilterMatches !== null && activeFocusId === null && selectedEdgeId === null && isDocFiltered);

                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const dist = Math.hypot(dx, dy) || 1;
                const ux = dx / dist;
                const uy = dy / dist;

                const targetCentrality = betweennessScores.get(target.id) ?? 0;
                const targetRadius = Math.round(
                  13 + Math.min(13, Math.sqrt(target.total_occurrences) * 1.8 + targetCentrality * 1.2),
                );
                const sourceCentrality = betweennessScores.get(source.id) ?? 0;
                const sourceRadius = Math.round(
                  13 + Math.min(13, Math.sqrt(source.total_occurrences) * 1.8 + sourceCentrality * 1.2),
                );

                const isDirected = edge.relationship_type && edge.relationship_type !== "co_occurs_with";
                const endOffset = isDirected ? targetRadius + 6 : targetRadius;
                const startOffset = sourceRadius;

                const x1 = source.x + ux * startOffset;
                const y1 = source.y + uy * startOffset;
                const x2 = dist > endOffset + startOffset ? target.x - ux * endOffset : target.x;
                const y2 = dist > endOffset + startOffset ? target.y - uy * endOffset : target.y;

                const markerUrl = !isDirected
                  ? undefined
                  : isPathEdge
                  ? "url(#graph-arrow-path)"
                  : isHighlighted
                  ? "url(#graph-arrow-highlighted)"
                  : isDimmed
                  ? "url(#graph-arrow-dimmed)"
                  : "url(#graph-arrow)";

                const showBadge = (isSelectedEdge || (isHighlighted && isDirected)) && dist > 70;
                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                const badgeText = formatPredicate(edge.relationship_type);
                const badgeWidth = Math.max(48, badgeText.length * 6.5 + 16);

                return (
                  <React.Fragment key={edge.id}>
                    <line
                      className={`graph-edge${isPathEdge ? " graph-edge-path" : isHighlighted ? " graph-edge-highlighted" : ""}${
                        isDimmed ? " graph-edge-dimmed" : ""
                      }`}
                      markerEnd={markerUrl}
                      onClick={(e) => handleEdgeClick(e, edge)}
                      strokeDasharray={isPathEdge ? "4 3" : undefined}
                      strokeWidth={
                        isPathEdge
                          ? 2.6
                          : isHighlighted
                          ? 2.0
                          : Math.max(1, 1 + Math.min(edge.strength, 6) / 5)
                      }
                      x1={x1}
                      x2={x2}
                      y1={y1}
                      y2={y2}
                    >
                      <title>
                        {source.label} —[{formatPredicate(edge.relationship_type)}]→ {target.label} (Strength: {edge.strength}{edge.pmi ? `, PMI: ${edge.pmi}` : ""})
                      </title>
                    </line>
                    {showBadge && (
                      <g
                        className="graph-edge-badge-group"
                        pointerEvents="none"
                        transform={`translate(${midX}, ${midY})`}
                      >
                        <rect
                          className={`graph-edge-badge-bg${isHighlighted ? " is-highlighted" : ""}`}
                          height="18"
                          rx="9"
                          width={badgeWidth}
                          x={-badgeWidth / 2}
                          y="-9"
                        />
                        <text
                          className="graph-edge-badge-text"
                          textAnchor="middle"
                          y="3.5"
                        >
                          {badgeText}
                        </text>
                      </g>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Nodes layer */}
              {sortedNodes.map((node) => {
                const isPathNode = pathNodeIds.has(node.id);
                const pathStepIndex = activePath ? activePath.nodeIds.indexOf(node.id) : -1;
                const isSelected = node.id === selectedNodeId;
                const isHovered = node.id === hoveredNodeId;
                const isActive = isSelected || isHovered;
                const isNeighbor = neighborInfo.neighborIds.has(node.id);
                const isConnectedToSelectedEdge =
                  selectedEdge && (selectedEdge.source === node.id || selectedEdge.target === node.id);

                const isSearchMatch = isSearchActive && searchMatches.has(node.id);
                const isBridgeModeActive = filterBridgesOnly && bridgeNodeIds.size > 0;
                const isDocFiltered =
                  documentFilterMatches !== null && !documentFilterMatches.has(node.id);

                const isDimmed =
                  activePath !== null
                    ? !isPathNode
                    : activeTopicClusterId !== null
                    ? nodeClusters.get(node.id) !== activeTopicClusterId
                    : (activeFocusId !== null && !isActive && !isNeighbor) ||
                      (selectedEdgeId !== null && !isConnectedToSelectedEdge) ||
                      (isSearchActive && !isSearchMatch) ||
                      (isBridgeModeActive && activeFocusId === null && selectedEdgeId === null && !bridgeNodeIds.has(node.id)) ||
                      (documentFilterMatches !== null && activeFocusId === null && selectedEdgeId === null && isDocFiltered);

                // Cluster theme
                const clusterIdx = nodeClusters.get(node.id) ?? 0;
                const theme = CLUSTER_THEMES[clusterIdx % CLUSTER_THEMES.length];

                // Size nodes meaningfully by centrality + occurrence score
                const centralityScore = betweennessScores.get(node.id) ?? 0;
                const radius = Math.round(
                  13 + Math.min(13, Math.sqrt(node.total_occurrences) * 1.8 + centralityScore * 1.2),
                );

                const isExpanded = isActive || isSelected || isSearchMatch || Boolean(isConnectedToSelectedEdge) || isPathNode;
                const displayLabel = truncateLabel(node.label, isExpanded);

                const nodeDegree = nodeDegrees.get(node.id) ?? 0;
                const isHub = nodeDegree >= 2 || bridgeNodeIds.has(node.id);
                const shouldShowLabel =
                  labelDensity === "all" ||
                  (labelDensity === "hubs" && isHub) ||
                  isActive ||
                  isSelected ||
                  isPathNode ||
                  isSearchMatch ||
                  Boolean(isConnectedToSelectedEdge);

                return (
                  <g
                    className={`graph-node${isPathNode ? " graph-node-path" : ""}${
                      isSelected || isConnectedToSelectedEdge ? " graph-node-selected" : ""
                    }${isNeighbor ? " graph-node-neighbor" : ""}${isDimmed ? " graph-node-dimmed" : ""}`}
                    key={node.id}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        setSelectedNodeId(node.id === selectedNodeId ? null : node.id);
                      }
                    }}
                    onPointerDown={(event) => handleNodePointerDown(event, node)}
                    onPointerEnter={() => setHoveredNodeId(node.id)}
                    onPointerLeave={() => setHoveredNodeId(null)}
                    onPointerUp={(event) => handleNodePointerUp(event, node)}
                    role="button"
                    tabIndex={0}
                  >
                    {/* Bridge Concept Subtle Ring */}
                    {bridgeNodeIds.has(node.id) && (
                      <circle
                        className="graph-node-bridge-ring"
                        cx={node.x}
                        cy={node.y}
                        r={radius + 3.5}
                      />
                    )}

                    {/* Path Node Selection Ring */}
                    {isPathNode && (
                      <circle
                        className="graph-node-path-ring"
                        cx={node.x}
                        cy={node.y}
                        r={radius + 3.5}
                      />
                    )}

                    {/* Node Circle */}
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={radius}
                      style={{
                        stroke: isPathNode
                          ? "#24458f"
                          : isSelected || isConnectedToSelectedEdge
                          ? "#24458f"
                          : isNeighbor
                          ? theme.stroke
                          : theme.stroke,
                        strokeWidth: isSelected || isConnectedToSelectedEdge ? 2.4 : isPathNode ? 2 : 1.5,
                        fill: isSelected || isConnectedToSelectedEdge
                          ? "#dce6f7"
                          : isNeighbor
                          ? "#eef3fa"
                          : theme.fill,
                      }}
                    >
                      <title>
                        {node.label} ({node.total_occurrences} mentions{bridgeNodeIds.has(node.id) ? " · Bridge" : ""}{node.tfidf_score ? `, TF-IDF: ${node.tfidf_score}` : ""})
                      </title>
                    </circle>

                    {/* Occurrence count badge inside circle */}
                    <text className="graph-node-count" x={node.x} y={node.y}>
                      {node.total_occurrences}
                    </text>

                    {/* Visually attached concept label directly beneath node */}
                    {shouldShowLabel && (
                      <text
                        className={`graph-node-label${isActive || isConnectedToSelectedEdge ? " graph-node-label-active" : ""}${
                          isPathNode ? " graph-node-label-path" : ""
                        }`}
                        x={node.x}
                        y={node.y + radius + 13}
                      >
                        {displayLabel}
                      </text>
                    )}

                    {/* Path Step Number Badge */}
                    {activePath && isPathNode && pathStepIndex !== -1 && (
                      <g
                        className="graph-node-step-badge"
                        transform={`translate(${node.x + radius - 2}, ${node.y - radius + 2})`}
                      >
                        <circle fill="#24458f" r={7.5} stroke="#ffffff" strokeWidth={1.2} />
                        <text
                          dominantBaseline="central"
                          fill="#ffffff"
                          fontSize="8.5"
                          fontWeight="700"
                          textAnchor="middle"
                        >
                          {pathStepIndex + 1}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          {/* Canvas Radar Minimap */}
          <div aria-label="Graph zoom" className="graph-zoom-controls" role="group">
            <button aria-label="Zoom out" onClick={() => zoomBy(1 / 1.25)} type="button">−</button>
            <button aria-label="Reset graph view" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} type="button">Fit</button>
            <button aria-label="Zoom in" onClick={() => zoomBy(1.25)} type="button">+</button>
          </div>
          <div className="graph-minimap-panel">
            <div className="minimap-header-row">
              <span className="minimap-caption">Radar</span>
              <button
                className="minimap-toggle"
                onClick={() => setIsMinimapVisible((prev) => !prev)}
                title={isMinimapVisible ? "Collapse minimap" : "Expand minimap"}
                type="button"
              >
                {isMinimapVisible ? "−" : "Map"}
              </button>
            </div>
            {isMinimapVisible && (
              <svg
                className="minimap-svg"
                onClick={handleMinimapClick}
                preserveAspectRatio="xMidYMid meet"
                viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              >
                <rect fill="#eae6dc" height={HEIGHT} width={WIDTH} />
                {visibleEdges.map((edge) => {
                  const s = nodeById.get(edge.source);
                  const t = nodeById.get(edge.target);
                  if (!s || !t) return null;
                  return (
                    <line
                      key={edge.id}
                      stroke="#d0cbc0"
                      strokeWidth={1.2}
                      x1={s.x}
                      x2={t.x}
                      y1={s.y}
                      y2={t.y}
                    />
                  );
                })}
                {nodes.map((node) => {
                  const clusterIdx = nodeClusters.get(node.id) ?? 0;
                  const theme = CLUSTER_THEMES[clusterIdx % CLUSTER_THEMES.length];
                  return (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      fill={theme.stroke}
                      key={node.id}
                      r={node.id === selectedNodeId ? 5.5 : 3.2}
                    />
                  );
                })}
                <rect
                  className="minimap-viewport-box"
                  fill="rgba(36, 69, 143, 0.12)"
                  height={Math.min(HEIGHT, HEIGHT / zoom)}
                  rx={3}
                  stroke="#24458f"
                  strokeWidth={2}
                  width={Math.min(WIDTH, WIDTH / zoom)}
                  x={-pan.x / zoom}
                  y={-pan.y / zoom}
                />
              </svg>
            )}
          </div>

          {/* Active Connection Path Explorer Drawer (Docked at canvas bottom) */}
          {activePath && (
            <div className="canvas-path-bar">
              <div className="path-bar-header">
                <div className="path-bar-title">
                  <span className="path-bar-badge">Degrees of separation</span>
                  <strong>{nodeById.get(activePath.nodeIds[0])?.label ?? activePath.nodeIds[0]}</strong>
                  <span className="path-step-arrow">➔</span>
                  <strong>{nodeById.get(activePath.nodeIds[activePath.nodeIds.length - 1])?.label ?? activePath.nodeIds[activePath.nodeIds.length - 1]}</strong>
                  <span className="path-bar-meta">
                    {activePath.totalHops} hop{activePath.totalHops === 1 ? "" : "s"} ({activePath.nodeIds.length} concepts)
                  </span>
                </div>
                <button
                  className="path-bar-close"
                  onClick={() => {
                    setActivePath(null);
                    setPathError(null);
                  }}
                  title="Clear path highlight"
                  type="button"
                >
                  ×
                </button>
              </div>

              <div className="path-steps-row">
                {activePath.nodeIds.map((nodeId, idx) => {
                  const node = nodeById.get(nodeId);
                  const step = idx < activePath.steps.length ? activePath.steps[idx] : null;
                  return (
                    <React.Fragment key={nodeId}>
                      <button
                        className="path-concept-chip"
                        onClick={() => {
                          setSelectedNodeId(nodeId);
                          setSelectedEdgeId(null);
                        }}
                        title={`Inspect concept: ${node?.label ?? nodeId}`}
                        type="button"
                      >
                        <span className="step-num">{idx + 1}</span>
                        <span className="step-name">{node?.label ?? nodeId}</span>
                      </button>
                      {step && (
                        <div className="path-link-connector">
                          <span className={`predicate-pill ${getPredicateClass(step.relationshipType)}`}>
                            {formatPredicate(step.relationshipType)}
                          </span>
                          <button
                            className="btn-step-inspect"
                            onClick={() => {
                              setSelectedEdgeId(step.edgeId);
                              setSelectedNodeId(null);
                            }}
                            title="Inspect document snippets for this link"
                            type="button"
                          >
                            Evidence ({step.strength})
                          </button>
                          <span className="path-step-arrow">➔</span>
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* CONTEXTUAL RIGHT-SIDE INSPECTOR DRAWER */}
      {isInspectorOpen && (
        <aside aria-label="Inspector" className="context-inspector">
          {/* Selected Edge Inspector */}
          {selectedEdge && (
            <div className="inspector-content">
              <div className="inspector-header">
                <div className="inspector-tag-group">
                  <span className="inspector-kicker">Connection</span>
                  <span className="inspector-pill">Strength {selectedEdge.strength}</span>
                  {selectedEdge.pmi !== undefined && selectedEdge.pmi > 0 && (
                    <span className="inspector-pill">PMI {selectedEdge.pmi}</span>
                  )}
                </div>
                <button
                  aria-label="Close inspector"
                  className="inspector-close-btn"
                  onClick={() => {
                    setSelectedEdgeId(null);
                    if (onClearConnection) onClearConnection();
                  }}
                  type="button"
                >
                  ×
                </button>
              </div>

              <div className="inspector-title-area">
                <div className="spo-card">
                  <div className="spo-entity-box spo-subject">
                    <span className="spo-role-tag">Subject</span>
                    <h3 className="spo-entity-name">
                      {nodeById.get(selectedEdge.source)?.label}
                    </h3>
                  </div>

                  <div className="spo-relation-bridge">
                    <div className="spo-arrow-line" />
                    <span className={`predicate-pill ${getPredicateClass(selectedEdge.relationship_type)} spo-pill`}>
                      {formatPredicate(selectedEdge.relationship_type)}
                    </span>
                    <span className="spo-arrow-head">▶</span>
                  </div>

                  <div className="spo-entity-box spo-object">
                    <span className="spo-role-tag">Object</span>
                    <h3 className="spo-entity-name">
                      {nodeById.get(selectedEdge.target)?.label}
                    </h3>
                  </div>
                </div>
              </div>

              <div className="inspector-section">
                <h4 className="inspector-section-label">Document Evidence</h4>
                {isLoadingEvidence ? (
                  <div className="skeleton skeleton-evidence" />
                ) : !evidence || evidence.length === 0 ? (
                  <p className="inspector-empty-text">No direct context snippet recorded for this connection.</p>
                ) : (
                  <div className="evidence-stack">
                    {evidence.map((ev, idx) => (
                      <div className="evidence-card" key={idx}>
                        <div className="evidence-header-row">
                          <span className="doc-source-tag">{ev.original_filename}</span>
                          <span className="mention-stat-text">
                            {ev.source_occurrences} × {ev.target_occurrences} co-mentions
                          </span>
                        </div>
                        {ev.snippet ? (
                          <blockquote className="evidence-quote">
                            &ldquo;
                            {highlightKeywords(
                              ev.snippet,
                              nodeById.get(selectedEdge.source)?.label ?? "",
                              nodeById.get(selectedEdge.target)?.label ?? "",
                            )}
                            &rdquo;
                          </blockquote>
                        ) : (
                          <p className="evidence-empty-note">Co-occurs within the document structure.</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Selected Node Inspector */}
          {selectedNode && !selectedEdge && (
            <div className="inspector-content">
              <div className="inspector-header">
                <div className="inspector-tag-group">
                  <span className="inspector-kicker">Concept</span>
                  {bridgeNodeIds.has(selectedNode.id) && (
                    <span
                      className="bridge-tag"
                      title="High betweenness centrality: acts as a bridge connecting disparate topical clusters"
                    >
                      Bridge
                    </span>
                  )}
                </div>
                <button
                  aria-label="Close inspector"
                  className="inspector-close-btn"
                  onClick={() => setSelectedNodeId(null)}
                  type="button"
                >
                  ×
                </button>
              </div>

              <h3 className="inspector-title">{selectedNode.label}</h3>
              <p className="inspector-meta-line">
                {selectedNode.document_count} document{selectedNode.document_count === 1 ? "" : "s"} · {selectedNode.total_occurrences} mentions
                {selectedNode.tfidf_score ? ` · TF-IDF ${selectedNode.tfidf_score}` : ""}
              </p>

              {/* Concept Dossier (TextRank Extractive Summary) */}
              <div className="inspector-section">
                <div className="dossier-headline">
                  <h4 className="inspector-section-label">Summary Dossier</h4>
                  {dossier?.source_documents && dossier.source_documents.length > 0 && (
                    <span className="dossier-file-sources">
                      from {dossier.source_documents.join(", ")}
                    </span>
                  )}
                </div>
                {isLoadingDossier ? (
                  <div className="skeleton skeleton-evidence" />
                ) : dossier?.summary ? (
                  <blockquote className="dossier-quote-text">
                    &ldquo;{dossier.summary}&rdquo;
                  </blockquote>
                ) : (
                  <p className="inspector-empty-text">
                    Referenced in document context without distinct multi-sentence narrative.
                  </p>
                )}
              </div>

              {/* Connected Concepts */}
              {neighborInfo.neighbors.length > 0 && (
                <div className="inspector-section">
                  <h4 className="inspector-section-label">Connected Concepts ({neighborInfo.neighbors.length})</h4>
                  <div className="neighbor-chips-grid">
                    {neighborInfo.neighbors.map((neighbor) => (
                      <button
                        className="neighbor-action-chip"
                        key={neighbor.id}
                        onClick={() => {
                          setSelectedEdgeId(neighbor.edgeId);
                          setSelectedNodeId(null);
                        }}
                        title={`Click to view connection evidence! Strength: ${neighbor.strength}${
                          neighbor.predicate ? `, Predicate: ${formatPredicate(neighbor.predicate)}` : ""
                        }`}
                        type="button"
                      >
                        <span className="neighbor-chip-label">
                          {neighbor.direction === "outgoing" && (
                            <span className="neighbor-chip-dir" title="Subject pointing to Object">→</span>
                          )}
                          {neighbor.direction === "incoming" && (
                            <span className="neighbor-chip-dir" title="Object pointed from Subject">←</span>
                          )}
                          {neighbor.label}
                        </span>
                        <small className="neighbor-chip-meta">
                          {neighbor.predicate && neighbor.predicate !== "co_occurs_with" ? `${formatPredicate(neighbor.predicate)} · ` : ""}
                          {neighbor.strength}
                        </small>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Connection Path Finder ("Degrees of Separation") */}
              <div className="inspector-section">
                <div className="collapsible-section-header">
                  <h4 className="inspector-section-label">Degrees of Separation</h4>
                  <button
                    className="btn-text-toggle"
                    onClick={() => {
                      setIsPathFinderOpen((prev) => !prev);
                      setPathError(null);
                    }}
                    type="button"
                  >
                    {isPathFinderOpen ? "Hide" : "Find connection…"}
                  </button>
                </div>
                {isPathFinderOpen && (
                  <div className="path-finder-box">
                    <div className="path-finder-controls">
                      <span className="path-from-label">Path to:</span>
                      <select
                        className="path-select-input"
                        onChange={(e) => {
                          setPathTargetId(e.target.value);
                          setPathError(null);
                        }}
                        value={pathTargetId}
                      >
                        <option value="">Select target concept...</option>
                        {nodes
                          .filter((n) => n.id !== selectedNode.id)
                          .sort((a, b) => a.label.localeCompare(b.label))
                          .map((n) => (
                            <option key={n.id} value={n.id}>
                              {n.label} ({n.total_occurrences})
                            </option>
                          ))}
                      </select>
                      <button
                        className="btn-find-path"
                        disabled={!pathTargetId}
                        onClick={() => {
                          if (!pathTargetId) return;
                          const path = findShortestPath(
                            graph.nodes,
                            visibleEdges,
                            selectedNode.id,
                            pathTargetId,
                          );
                          if (!path) {
                            setPathError(
                              `No connection path found. Try lowering Min Strength to reveal weaker links.`,
                            );
                            setActivePath(null);
                          } else {
                            setActivePath(path);
                            setPathError(null);
                          }
                        }}
                        type="button"
                      >
                        Find
                      </button>
                    </div>
                    {pathError && <p className="path-error-text">{pathError}</p>}
                  </div>
                )}
              </div>

              {/* Suggested Alias Merging */}
              {(() => {
                const nodeSuggestions = mergeSuggestions.filter(
                  (s) =>
                    s.source_concept_id === selectedNode.id ||
                    s.target_concept_id === selectedNode.id,
                );
                if (nodeSuggestions.length === 0) return null;
                const topSuggestion = nodeSuggestions[0];
                const isSource = topSuggestion.source_concept_id === selectedNode.id;
                const partnerName = isSource ? topSuggestion.target_name : topSuggestion.source_name;
                const targetName = isSource ? topSuggestion.target_name : selectedNode.label;
                const sourceName = isSource ? selectedNode.label : topSuggestion.source_name;
                const targetId = isSource ? topSuggestion.target_concept_id : selectedNode.id;
                const sourceId = isSource ? selectedNode.id : topSuggestion.source_concept_id;

                return (
                  <div className="inspector-section">
                    <div className="alias-card">
                      <div className="alias-header">
                        <span className="alias-badge">Suggested alias</span>
                        <span className="alias-match">
                          {Math.round(topSuggestion.similarity * 100)}% match
                        </span>
                      </div>
                      <p className="alias-desc">
                        {topSuggestion.reason}: &ldquo;{partnerName}&rdquo;
                      </p>
                      <button
                        className="btn-merge-action"
                        disabled={isMerging}
                        onClick={() => handleMerge(sourceId, targetId, sourceName, targetName)}
                        type="button"
                      >
                        {isMerging ? "Merging…" : `Merge into "${targetName}"`}
                      </button>
                    </div>
                  </div>
                );
              })()}

              {/* Manual Merge Option */}
              <div className="inspector-section">
                <div className="collapsible-section-header">
                  <h4 className="inspector-section-label">Manual Alias Merge</h4>
                  <button
                    className="btn-text-toggle"
                    onClick={() => setIsManualMergeOpen((prev) => !prev)}
                    type="button"
                  >
                    {isManualMergeOpen ? "Hide" : "Merge with…"}
                  </button>
                </div>
                {isManualMergeOpen && (
                  <div className="path-finder-box">
                    <div className="path-finder-controls">
                      <select
                        className="path-select-input"
                        onChange={(e) => setManualTargetId(e.target.value)}
                        value={manualTargetId}
                      >
                        <option value="">Select target concept...</option>
                        {nodes
                          .filter((n) => n.id !== selectedNode.id)
                          .map((n) => (
                            <option key={n.id} value={n.id}>
                              {n.label} ({n.total_occurrences})
                            </option>
                          ))}
                      </select>
                      <button
                        className="btn-find-path"
                        disabled={!manualTargetId || isMerging}
                        onClick={() => {
                          const targetNode = nodeById.get(manualTargetId);
                          if (targetNode) {
                            handleMerge(selectedNode.id, targetNode.id, selectedNode.label, targetNode.label);
                          }
                        }}
                        type="button"
                      >
                        Merge
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>
      )}
    </div>
  );
}
