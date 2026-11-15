import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// @ts-expect-error vitest / jsdom act flag
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

import { KnowledgeGraphView } from "./knowledge-graph";
import type { KnowledgeGraph } from "../lib/graph";
import type { WorkspaceConcept } from "../lib/concepts";

// Mock fetch for dossiers and evidence
global.fetch = vi.fn().mockImplementation(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve([]),
  } as Response),
);

describe("KnowledgeGraphView Editorial Workspace", () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  const mockGraph: KnowledgeGraph = {
    nodes: [
      { id: "c1", label: "Neural Networks", document_count: 2, total_occurrences: 14, tfidf_score: 4.8 },
      { id: "c2", label: "Gradient Descent", document_count: 2, total_occurrences: 9, tfidf_score: 3.2 },
      { id: "c3", label: "Transformers", document_count: 1, total_occurrences: 5, tfidf_score: 2.1 },
    ],
    edges: [
      { id: "e1", source: "c1", target: "c2", relationship_type: "uses", strength: 5, document_count: 2, pmi: 2.4 },
      { id: "e2", source: "c1", target: "c3", relationship_type: "built_with", strength: 3, document_count: 1, pmi: 1.8 },
    ],
  };

  const mockConcepts: WorkspaceConcept[] = [
    { id: "c1", name: "Neural Networks", document_count: 2, total_occurrences: 14, tfidf_score: 4.8, created_at: "", updated_at: "" },
    { id: "c2", name: "Gradient Descent", document_count: 2, total_occurrences: 9, tfidf_score: 3.2, created_at: "", updated_at: "" },
    { id: "c3", name: "Transformers", document_count: 1, total_occurrences: 5, tfidf_score: 2.1, created_at: "", updated_at: "" },
  ];

  it("renders intentional empty state when graph contains no nodes", async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(
        <KnowledgeGraphView
          concepts={[]}
          graph={{ nodes: [], edges: [] }}
        />,
      );
    });

    expect(container.querySelector(".graph-empty-state")).not.toBeNull();
    expect(container.textContent).toContain("Knowledge graph empty");
    expect(container.textContent).toContain("Upload files in the document navigator");
  });

  it("renders the dominant canvas with attached labels and no inspector initially", async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(
        <KnowledgeGraphView
          concepts={mockConcepts}
          graph={mockGraph}
        />,
      );
    });

    // Dominant canvas surface
    const canvas = container.querySelector(".graph-canvas");
    expect(canvas).not.toBeNull();

    // Node circles rendered
    const nodeGroups = container.querySelectorAll(".graph-node");
    expect(nodeGroups.length).toBe(3);

    // Concept labels visually attached directly beneath nodes
    const labels = container.querySelectorAll(".graph-node-label");
    expect(labels.length).toBeGreaterThan(0);
    expect(container.textContent).toContain("Neural Networks");

    // Contextual right-side inspector should NOT be rendered when nothing is selected
    expect(container.querySelector(".context-inspector")).toBeNull();
  });

  it("opens the contextual right inspector when a node is clicked", async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(
        <KnowledgeGraphView
          concepts={mockConcepts}
          graph={mockGraph}
        />,
      );
    });

    const firstNode = container.querySelector(".graph-node") as SVGGElement;
    expect(firstNode).not.toBeNull();

    // Click to select node
    await act(async () => {
      firstNode.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    });

    // Inspector now opens
    const inspector = container.querySelector(".context-inspector");
    expect(inspector).not.toBeNull();

    // Inspector displays selected concept details and typography
    expect(inspector?.querySelector(".inspector-kicker")?.textContent).toBe("Concept");
    expect(inspector?.querySelector(".inspector-title")?.textContent).toBe("Neural Networks");
    expect(inspector?.textContent).toContain("14 mentions");
    expect(inspector?.textContent).toContain("Summary Dossier");
    expect(inspector?.textContent).toContain("Connected Concepts");
  });

  it("opens the contextual right inspector when an edge is clicked", async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(
        <KnowledgeGraphView
          concepts={mockConcepts}
          graph={mockGraph}
        />,
      );
    });

    const edge = container.querySelector(".graph-edge") as SVGLineElement;
    expect(edge).not.toBeNull();

    // Click edge
    await act(async () => {
      edge.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    // Inspector opens with connection details
    const inspector = container.querySelector(".context-inspector");
    expect(inspector).not.toBeNull();
    expect(inspector?.querySelector(".inspector-kicker")?.textContent).toBe("Connection");
    expect(inspector?.textContent).toContain("Strength 5");
    expect(inspector?.textContent).toContain("PMI 2.4");
    expect(inspector?.textContent).toContain("Document Evidence");
  });

  it("toggles the radar minimap visibility", async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(
        <KnowledgeGraphView
          concepts={mockConcepts}
          graph={mockGraph}
        />,
      );
    });

    const minimap = container.querySelector(".graph-minimap-panel");
    expect(minimap).not.toBeNull();

    const toggleBtn = minimap?.querySelector(".minimap-toggle") as HTMLButtonElement;
    expect(toggleBtn).not.toBeNull();

    // Initially minimap SVG is visible
    expect(minimap?.querySelector(".minimap-svg")).not.toBeNull();

    // Click to collapse
    await act(async () => {
      toggleBtn.click();
    });
    expect(minimap?.querySelector(".minimap-svg")).toBeNull();

    // Click to expand again
    await act(async () => {
      toggleBtn.click();
    });
    expect(minimap?.querySelector(".minimap-svg")).not.toBeNull();
  });

  it("filters concepts via quiet search in toolbar", async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(
        <KnowledgeGraphView
          concepts={mockConcepts}
          graph={mockGraph}
          isToolbarOpen={true}
        />,
      );
    });

    const searchInput = container.querySelector(".toolbar-search-input") as HTMLInputElement;
    expect(searchInput).not.toBeNull();

    await act(async () => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      )?.set;
      nativeInputValueSetter?.call(searchInput, "Transformers");
      searchInput.dispatchEvent(new Event("input", { bubbles: true }));
      searchInput.dispatchEvent(new Event("change", { bubbles: true }));
    });

    // Non-matching nodes should be dimmed
    const dimmedNodes = container.querySelectorAll(".graph-node-dimmed");
    expect(dimmedNodes.length).toBeGreaterThan(0);
  });
  it("offers touch zoom and converts screen dragging to graph coordinates", async () => {
    const root = createRoot(container);
    await act(async () => root.render(<KnowledgeGraphView graph={mockGraph} />));
    const svg = container.querySelector(".graph-canvas") as SVGSVGElement;
    const camera = svg.querySelector("g")!;
    Object.defineProperty(svg, "getBoundingClientRect", {
      value: () => ({ width: 320, height: 400, left: 0, top: 0 }),
    });
    svg.setPointerCapture = vi.fn();
    svg.releasePointerCapture = vi.fn();
    await act(async () => {
      svg.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10 }));
      svg.dispatchEvent(new MouseEvent("pointermove", { bubbles: true, clientX: 30, clientY: 20 }));
      svg.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    });
    expect(camera.getAttribute("transform")).toBe("translate(60, 30) scale(1)");
    await act(async () => (container.querySelector('[aria-label="Zoom in"]') as HTMLButtonElement).click());
    expect(camera.getAttribute("transform")).toContain("scale(1.25)");
    await act(async () => (container.querySelector('[aria-label="Reset graph view"]') as HTMLButtonElement).click());
    expect(camera.getAttribute("transform")).toBe("translate(0, 0) scale(1)");
    await act(async () => root.unmount());
  });

  it.each(["canvas", "node"])("pinches around the fingers when starting on a %s", async (startOn) => {
    const root = createRoot(container);
    await act(async () => root.render(<KnowledgeGraphView graph={mockGraph} />));
    const svg = container.querySelector(".graph-canvas") as SVGSVGElement;
    const node = svg.querySelector(".graph-node") as SVGGElement;
    const camera = svg.querySelector("g")!;
    Object.defineProperty(svg, "getBoundingClientRect", {
      value: () => ({ width: 320, height: 400, left: 0, top: 0 }),
    });
    svg.setPointerCapture = vi.fn();
    svg.releasePointerCapture = vi.fn();
    node.setPointerCapture = vi.fn();
    node.releasePointerCapture = vi.fn();
    async function touch(type: string, id: number, x: number, y: number, target: Element = svg) {
      await act(async () => {
        const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y });
        Object.defineProperties(event, { pointerId: { value: id }, pointerType: { value: "touch" } });
        target.dispatchEvent(event);
      });
    }
    function expectCamera(x: number, y: number, zoom: number) {
      const values = camera.getAttribute("transform")!.match(/-?\d+(?:\.\d+)?/g)!.map(Number);
      expect(values[0]).toBeCloseTo(x);
      expect(values[1]).toBeCloseTo(y);
      expect(values[2]).toBeCloseTo(zoom);
    }
    await touch("pointerdown", 1, 110, 200, startOn === "node" ? node : svg);
    await touch("pointerdown", 2, 210, 200);
    await touch("pointermove", 1, 85, 200);
    await touch("pointermove", 2, 235, 200);
    expectCamera(-240, -160, 1.5);
    // Moving the midpoint moves the graph without changing magnification.
    await touch("pointermove", 1, 105, 220);
    await touch("pointermove", 2, 255, 220);
    expectCamera(-180, -100, 1.5);
    // Pinch inward, including the lower zoom boundary.
    await touch("pointermove", 1, 175, 220);
    await touch("pointermove", 2, 185, 220);
    expectCamera(348, 252, 0.4);
    // Cancellation releases the gesture, with no accidental inspector selection.
    await touch("pointercancel", 1, 175, 220);
    await touch("pointerup", 2, 185, 220, node);
    await act(async () => node.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(container.querySelector(".context-inspector")).toBeNull();
    await touch("pointerdown", 3, 20, 20);
    await touch("pointermove", 3, 30, 30);
    await touch("pointerup", 3, 30, 30);
    expectCamera(378, 282, 0.4);
    await act(async () => root.unmount());
  });

});
