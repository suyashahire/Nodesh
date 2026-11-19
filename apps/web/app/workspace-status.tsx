"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

import { analyzeWorkspace } from "../lib/analyze";
import {
  deleteDocument,
  getDocumentComparison,
  listDocuments,
  type StoredDocument,
  uploadDocument,
  type WorkspaceDocumentComparison,
} from "../lib/documents";
import {
  listConcepts,
  type WorkspaceConcept,
} from "../lib/concepts";
import {
  formatPredicate,
  getPredicateClass,
  listRelationships,
  type ConceptRelationship,
} from "../lib/relationships";
import { KnowledgeGraphView } from "./knowledge-graph";
import {
  findBridgeConceptIds,
  getKnowledgeGraph,
  type KnowledgeGraph,
} from "../lib/graph";
import {
  deleteWorkspace,
  getWorkspaceStats,
  resumeOrCreateWorkspace,
  type Workspace,
  type WorkspaceStats,
} from "../lib/workspace";

type WorkspaceState =
  | { kind: "loading" }
  | { kind: "ready"; workspace: Workspace }
  | { kind: "error" };

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function relativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffSec = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000));
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDays = Math.floor(diffHour / 24);
  return `${diffDays}d ago`;
}

function getFileFormat(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "txt";
}

export function WorkspaceStatus() {
  const [state, setState] = useState<WorkspaceState>({ kind: "loading" });
  const [documents, setDocuments] = useState<StoredDocument[] | null>(null);
  const [concepts, setConcepts] = useState<WorkspaceConcept[] | null>(null);
  const [relationships, setRelationships] = useState<ConceptRelationship[] | null>(null);
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [stats, setStats] = useState<WorkspaceStats | null>(null);
  const [comparison, setComparison] = useState<WorkspaceDocumentComparison | null>(null);
  const [isComparisonOpen, setIsComparisonOpen] = useState(false);
  const [activeDocFilter, setActiveDocFilter] = useState<{ id: string; name: string } | "shared" | null>(null);

  const [layoutMode, setLayoutMode] = useState<"force" | "concentric">("force");
  const [isToolbarOpen, setIsToolbarOpen] = useState(true);
  const [isDocumentsOpen, setIsDocumentsOpen] = useState(false);

  useEffect(() => {
    if (window.matchMedia?.("(max-width: 900px)").matches) setIsToolbarOpen(false);
  }, []);

  useEffect(() => {
    if (!isDocumentsOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setIsDocumentsOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isDocumentsOpen]);

  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isDeletingWorkspace, setIsDeletingWorkspace] = useState(false);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  // Bridge concept detection
  const bridgeNodeIds = useMemo(() => {
    if (!graph || graph.nodes.length === 0 || graph.edges.length === 0) {
      return new Set<string>();
    }
    return findBridgeConceptIds(graph.nodes, graph.edges);
  }, [graph]);

  // Load or create workspace
  useEffect(() => {
    let active = true;

    resumeOrCreateWorkspace({
      apiBaseUrl,
      fetchImplementation: window.fetch.bind(window),
      storage: window.localStorage,
    })
      .then((workspace) => {
        if (active) setState({ kind: "ready", workspace });
      })
      .catch(() => {
        if (active) setState({ kind: "error" });
      });

    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  // Load initial workspace data
  useEffect(() => {
    if (state.kind !== "ready") return;
    const wsId = state.workspace.id;
    let active = true;

    Promise.all([
      listDocuments({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }),
      listConcepts({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }),
      listRelationships({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }),
      getKnowledgeGraph({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }),
      getWorkspaceStats({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }).catch(() => null),
      getDocumentComparison({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }).catch(() => null),
    ])
      .then(([docs, concs, rels, grph, st, comp]) => {
        if (!active) return;
        setDocuments(docs);
        setConcepts(concs);
        setRelationships(rels);
        setGraph(grph);
        if (st) setStats(st);
        if (comp) setComparison(comp);
      })
      .catch(() => {
        if (active) setAnalysisError("Could not load workspace data.");
      });

    return () => {
      active = false;
    };
  }, [apiBaseUrl, state]);

  async function refreshStats(wsId: string) {
    try {
      const st = await getWorkspaceStats({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      });
      setStats(st);
      const comp = await getDocumentComparison({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      }).catch(() => null);
      if (comp) setComparison(comp);
    } catch {
      // Non-critical
    }
  }

  async function refreshWorkspaceData(wsId: string) {
    try {
      const [docs, concs, rels, grph, st, comp] = await Promise.all([
        listDocuments({ apiBaseUrl, fetchImplementation: window.fetch.bind(window), workspaceId: wsId }),
        listConcepts({ apiBaseUrl, fetchImplementation: window.fetch.bind(window), workspaceId: wsId }),
        listRelationships({ apiBaseUrl, fetchImplementation: window.fetch.bind(window), workspaceId: wsId }),
        getKnowledgeGraph({ apiBaseUrl, fetchImplementation: window.fetch.bind(window), workspaceId: wsId }),
        getWorkspaceStats({ apiBaseUrl, fetchImplementation: window.fetch.bind(window), workspaceId: wsId }).catch(() => null),
        getDocumentComparison({ apiBaseUrl, fetchImplementation: window.fetch.bind(window), workspaceId: wsId }).catch(() => null),
      ]);
      setDocuments(docs);
      setConcepts(concs);
      setRelationships(rels);
      setGraph(grph);
      if (st) setStats(st);
      if (comp) setComparison(comp);
    } catch {
      // Non-critical
    }
  }

  // Automatic full analysis pipeline
  async function triggerAnalysis(wsId: string) {
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await analyzeWorkspace({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
      });
      setConcepts(result.concepts);
      setRelationships(result.relationships);
      setGraph(result.graph);
      await refreshStats(wsId);
    } catch {
      setAnalysisError("Automatic analysis failed. Try re-analyzing.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  // Document upload
  async function handleFileUpload(file: File) {
    if (state.kind !== "ready") return;
    const wsId = state.workspace.id;

    // Strict Client-Side Pre-Flight Validation
    const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB
    const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"];
    const lastDot = file.name.lastIndexOf(".");
    const ext = lastDot >= 0 ? file.name.slice(lastDot).toLowerCase() : "";

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(`Unsupported format '${ext || "unknown"}'. Allowed formats are PDF, DOCX, TXT, MD, and CSV.`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      const mbSize = (file.size / (1024 * 1024)).toFixed(1);
      setUploadError(`File is too large (${mbSize}MB). Maximum allowed document size is 10MB.`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (documents && documents.length >= 25) {
      setUploadError("Workspace document limit reached (maximum 25 documents). Please remove an existing document first.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    try {
      const doc = await uploadDocument({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        file,
        workspaceId: wsId,
      });
      setDocuments((prev) => [doc, ...(prev ?? [])]);
      setIsDocumentsOpen(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await triggerAnalysis(wsId);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Upload failed. Please ensure file is PDF, DOCX, TXT, MD, or CSV under 10MB.";
      setUploadError(message);
    } finally {
      setIsUploading(false);
    }
  }

  // Document delete
  async function handleDeleteDocument(docId: string, event: React.MouseEvent) {
    event.stopPropagation();
    if (state.kind !== "ready" || deletingDocId) return;
    const wsId = state.workspace.id;

    setDeletingDocId(docId);
    try {
      await deleteDocument({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: wsId,
        documentId: docId,
      });
      const remainingDocs = (documents ?? []).filter((d) => d.id !== docId);
      setDocuments(remainingDocs);
      if (remainingDocs.length === 0) {
        setConcepts([]);
        setRelationships([]);
        setGraph({ nodes: [], edges: [] });
        setComparison(null);
        setActiveDocFilter(null);
      }
      await triggerAnalysis(wsId);
    } catch {
      setUploadError("Could not delete document. Please try again.");
    } finally {
      setDeletingDocId(null);
    }
  }

  // Workspace deletion
  async function handleWorkspaceDeletion() {
    if (state.kind !== "ready") return;
    if (!window.confirm("Delete this workspace, its documents, and its graph permanently?")) return;

    setIsDeletingWorkspace(true);
    try {
      await deleteWorkspace({
        apiBaseUrl,
        fetchImplementation: window.fetch.bind(window),
        workspaceId: state.workspace.id,
      });
      window.localStorage.removeItem("nodesh.workspace-id");
      window.location.reload();
    } catch {
      setUploadError("Workspace deletion failed. Please try again.");
      setIsDeletingWorkspace(false);
    }
  }

  if (state.kind === "loading") {
    return (
      <div className="workspace-loading-state">
        <div className="skeleton-header skeleton" />
        <div className="skeleton-grid">
          <div className="skeleton-sidebar skeleton" />
          <div className="skeleton-main skeleton" />
        </div>
        <p className="status">Preparing your private workspace…</p>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="workspace-error-state">
        <p className="status status-error">Workspace is unavailable. Please check your connection and refresh.</p>
      </div>
    );
  }

  const ws = state.workspace;
  const docCount = documents?.length ?? 0;
  const conceptCount = graph?.nodes.length ?? 0;
  const edgeCount = graph?.edges.length ?? 0;

  return (
    <div className="app-shell">
      {/* Hidden Global File Input */}
      <input
        accept=".pdf,.docx,.txt,.md,.csv,application/pdf,text/plain,text/markdown,text/csv,application/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        id="document-upload"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileUpload(file);
        }}
        ref={fileInputRef}
        style={{ display: "none" }}
        type="file"
      />

      {/* COMPACT TOP BAR */}
      <header className="app-topbar">
        <div className="topbar-left">
          <span className="app-wordmark">Nodesh</span>
          <span className="topbar-divider" />
          <span className="topbar-meta workspace-id" title={`Workspace ID: ${ws.id}`}>
            Workspace {ws.id.slice(0, 8)}
          </span>
          <span className="topbar-bullet workspace-id">·</span>
          <span className="topbar-meta">
            {docCount} document{docCount === 1 ? "" : "s"}
          </span>
          <span className="topbar-bullet">·</span>
          <span className="topbar-meta">
            {conceptCount} concepts
          </span>
          <span className="topbar-bullet">·</span>
          <span className="topbar-meta">
            {edgeCount} connections
          </span>
          {isAnalyzing && <span className="topbar-status-pulse">Analyzing…</span>}
        </div>

        <div className="topbar-right">
          <button
            aria-controls="document-navigator"
            aria-expanded={isDocumentsOpen}
            className="btn-topbar-secondary mobile-documents-toggle"
            onClick={() => setIsDocumentsOpen((open) => !open)}
            type="button"
          >
            Documents <span className="count-pill">{docCount}</span>
          </button>
          {/* Graph Layout Mode Switcher */}
          <div aria-label="Graph layout mode" className="topbar-mode-toggle" role="group">
            <button
              className={`mode-btn${layoutMode === "force" ? " mode-btn-active" : ""}`}
              onClick={() => setLayoutMode("force")}
              title="Organic force-directed layout"
              type="button"
            >
              Organic
            </button>
            <button
              className={`mode-btn${layoutMode === "concentric" ? " mode-btn-active" : ""}`}
              onClick={() => setLayoutMode("concentric")}
              title="Concentric radial hub layout"
              type="button"
            >
              Concentric
            </button>
          </div>

          {/* Controls Toggle */}
          <button
            aria-expanded={isToolbarOpen}
            className={`btn-topbar-secondary${isToolbarOpen ? " btn-topbar-secondary-active" : ""}`}
            onClick={() => setIsToolbarOpen((prev) => !prev)}
            title="Toggle secondary graph controls and filters"
            type="button"
          >
            {isToolbarOpen ? "Hide controls" : "Controls"}
          </button>

          {/* Primary Action */}
          <button
            className="btn-primary-action"
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
            type="button"
          >
            {isUploading ? "Uploading…" : "+ Add document"}
          </button>
        </div>
      </header>

      {!isDocumentsOpen && (uploadError || analysisError) && (
        <p className="mobile-workspace-error" role="alert">{uploadError || analysisError}</p>
      )}

      {/* MAIN APPLICATION WORKSPACE */}
      <div className="app-body">
        {isDocumentsOpen && (
          <button
            aria-label="Close documents"
            className="mobile-documents-backdrop"
            onClick={() => setIsDocumentsOpen(false)}
            type="button"
          />
        )}
        {/* FOCUSED DOCUMENT NAVIGATOR (Left Column) */}
        <nav aria-label="Document navigator" className={`doc-navigator${isDocumentsOpen ? " doc-navigator-open" : ""}`} id="document-navigator">
          <div className="navigator-header">
            <div className="navigator-title-row">
              <span className="navigator-title">Documents</span>
              <span className="count-pill">{docCount}</span>
            </div>
            <button
              aria-label="Close document navigator"
              className="inspector-close mobile-documents-close"
              onClick={() => setIsDocumentsOpen(false)}
              type="button"
            >×</button>
            {documents && documents.length >= 2 && (
              <button
                className="btn-nav-compare"
                onClick={() => setIsComparisonOpen(true)}
                title="Compare concepts across documents"
                type="button"
              >
                Compare
              </button>
            )}
          </div>

          {uploadError && <p className="nav-error-banner">{uploadError}</p>}

          {/* When documents exist: clean, quiet list without giant upload box */}
          {documents === null ? (
            <div className="skeleton-doc skeleton" />
          ) : documents.length === 0 ? (
            <div
              className={`doc-empty-state${isDragOver ? " doc-empty-state-active" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDragLeave={() => setIsDragOver(false)}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragOver(false);
                const file = e.dataTransfer.files?.[0];
                if (file) handleFileUpload(file);
              }}
              role="button"
              tabIndex={0}
            >
              <div className="empty-state-icon">
                <svg fill="none" height="24" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" width="24">
                  <path d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="empty-state-title">No documents added</p>
              <p className="empty-state-desc">
                Drop PDF, DOCX, TXT, MD, or CSV files here to begin mapping concepts.
              </p>
              <span className="empty-state-btn">Browse files</span>
            </div>
          ) : (
            <div className="navigator-content">
              {/* Document List */}
              <ul className="doc-list">
                {documents.map((doc) => {
                  const isFiltered =
                    activeDocFilter !== null &&
                    typeof activeDocFilter === "object" &&
                    activeDocFilter.id === doc.id;
                  return (
                    <li
                      className={`doc-item${isFiltered ? " doc-item-filtered" : ""}`}
                      key={doc.id}
                      onClick={() => {
                        setActiveDocFilter((prev) =>
                          prev !== null && typeof prev === "object" && prev.id === doc.id
                            ? null
                            : { id: doc.id, name: doc.original_filename },
                        );
                        setIsDocumentsOpen(false);
                      }}
                      role="button"
                      tabIndex={0}
                      title="Click to isolate concepts from this document"
                    >
                      <div className="doc-item-body">
                        <div className="doc-item-title-row">
                          <span className={`doc-format-tag doc-format-${getFileFormat(doc.original_filename)}`}>
                            {getFileFormat(doc.original_filename).toUpperCase()}
                          </span>
                          <span className="doc-item-name">{doc.original_filename}</span>
                        </div>
                        <div className="doc-item-meta">
                          <span>{humanSize(doc.size_bytes)}</span>
                          <span className="meta-bullet">·</span>
                          <span>{relativeTime(doc.created_at)}</span>
                        </div>
                      </div>
                      <button
                        aria-label={`Delete ${doc.original_filename}`}
                        className="btn-doc-delete"
                        disabled={deletingDocId === doc.id}
                        onClick={(e) => handleDeleteDocument(doc.id, e)}
                        title="Delete document"
                        type="button"
                      >
                        {deletingDocId === doc.id ? "…" : "×"}
                      </button>
                    </li>
                  );
                })}
              </ul>

              {/* Document Filtering Bar */}
              {documents.length >= 2 && (
                <div className="doc-filter-bar">
                  <span className="doc-filter-label">Filter canvas:</span>
                  <div className="doc-filter-chips">
                    <button
                      className={`doc-chip${activeDocFilter === null ? " doc-chip-active" : ""}`}
                      onClick={() => setActiveDocFilter(null)}
                      type="button"
                    >
                      All
                    </button>
                    {comparison && comparison.shared_concepts && comparison.shared_concepts.length > 0 && (
                      <button
                        className={`doc-chip${activeDocFilter === "shared" ? " doc-chip-active" : ""}`}
                        onClick={() => setActiveDocFilter((prev) => (prev === "shared" ? null : "shared"))}
                        title="Highlight concepts shared across multiple documents"
                        type="button"
                      >
                        Shared ({comparison.shared_concepts.length})
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Compact drop target strip at bottom of list */}
              <div
                className={`compact-drop-strip${isDragOver ? " compact-drop-strip-active" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragLeave={() => setIsDragOver(false)}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleFileUpload(file);
                }}
                role="button"
                tabIndex={0}
              >
                <span>{isUploading ? "Extracting concepts…" : "+ Drop or click to add files"}</span>
              </div>
            </div>
          )}

          {/* Quiet Workspace Footer */}
          <div className="navigator-footer">
            {analysisError && <p className="nav-error-banner">{analysisError}</p>}
            <button
              className="btn-quiet-action"
              disabled={documents === null || documents.length === 0 || isAnalyzing}
              onClick={() => triggerAnalysis(ws.id)}
              type="button"
            >
              {isAnalyzing ? "Re-analyzing…" : "Re-analyze workspace"}
            </button>
            <button
              className="btn-quiet-danger"
              disabled={isDeletingWorkspace}
              onClick={handleWorkspaceDeletion}
              type="button"
            >
              {isDeletingWorkspace ? "Deleting…" : "Delete workspace"}
            </button>
          </div>
        </nav>

        {/* DOMINANT GRAPH CANVAS WITH CONTEXTUAL INSPECTOR */}
        <main aria-label="Knowledge graph surface" className="graph-surface-panel">
          {graph === null ? (
            <div className="graph-loading-state">
              <div className="skeleton-graph skeleton" />
            </div>
          ) : (
            <KnowledgeGraphView
              activeDocumentFilter={activeDocFilter}
              apiBaseUrl={apiBaseUrl}
              concepts={concepts ?? []}
              graph={graph}
              isToolbarOpen={isToolbarOpen}
              layoutMode={layoutMode}
              onClearConnection={() => setSelectedConnectionId(null)}
              onClearDocumentFilter={() => setActiveDocFilter(null)}
              onLayoutModeChange={(m) => setLayoutMode(m)}
              onToggleToolbar={() => setIsToolbarOpen((prev) => !prev)}
              onWorkspaceRefresh={() => refreshWorkspaceData(ws.id)}
              selectedConnectionId={selectedConnectionId}
              workspaceId={ws.id}
            />
          )}
        </main>
      </div>

      {/* Multi-Document Comparison Modal */}
      {isComparisonOpen && comparison && (
        <div className="modal-backdrop" onClick={() => setIsComparisonOpen(false)}>
          <div className="comparison-modal" onClick={(e) => e.stopPropagation()}>
            <div className="comparison-modal-header">
              <h3>Document Comparison</h3>
              <button
                className="inspector-close"
                onClick={() => setIsComparisonOpen(false)}
                type="button"
              >
                ×
              </button>
            </div>

            <div className="comparison-modal-body">
              {/* Pairwise Overlap Breakdown */}
              {comparison.pairwise_overlap && comparison.pairwise_overlap.length > 0 && (
                <div className="comparison-section">
                  <h4>Document Pair Similarity (Jaccard Overlap)</h4>
                  <div className="overlap-cards">
                    {comparison.pairwise_overlap.map((pair, idx) => (
                      <div className="overlap-card" key={idx}>
                        <div className="overlap-card-title">
                          <span>
                            {pair.doc_a_name} ↔ {pair.doc_b_name}
                          </span>
                          <span className="overlap-jaccard">
                            {Math.round(pair.jaccard_similarity * 100)}% match
                          </span>
                        </div>
                        <span className="overlap-shared-list">
                          {pair.shared_concept_count} shared concept
                          {pair.shared_concept_count === 1 ? "" : "s"}:{" "}
                          {pair.shared_concepts.slice(0, 4).join(", ")}
                          {pair.shared_concepts.length > 4 ? "…" : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Shared Concepts */}
              <div className="comparison-section">
                <h4>
                  Shared Concepts Across Documents ({comparison.shared_concepts?.length ?? 0})
                </h4>
                {!comparison.shared_concepts || comparison.shared_concepts.length === 0 ? (
                  <p className="document-empty">No shared concepts found across documents yet.</p>
                ) : (
                  <div className="shared-concept-tags">
                    {comparison.shared_concepts.map((sc) => (
                      <span
                        className="shared-concept-tag"
                        key={sc.id}
                        title={`Appears in: ${sc.document_names.join(", ")} (${sc.total_occurrences} mentions)`}
                      >
                        {sc.name} <small>({sc.document_count} docs)</small>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Unique concepts per document */}
              {comparison.documents && comparison.documents.length > 0 && (
                <div className="comparison-section">
                  <h4>Distinct Concepts by Document</h4>
                  <div className="overlap-cards">
                    {comparison.documents.map((doc) => (
                      <div className="doc-breakdown-card" key={doc.document_id}>
                        <span className="doc-breakdown-title">{doc.filename}</span>
                        <small className="mention-stat">
                          {doc.total_concepts} total concepts · {doc.unique_concept_count} unique to this document
                        </small>
                        <div className="shared-concept-tags" style={{ marginTop: "0.3rem" }}>
                          {doc.unique_concepts.length === 0 ? (
                            <span className="document-empty" style={{ fontSize: "0.7rem" }}>
                              All concepts in this document are shared with others.
                            </span>
                          ) : (
                            doc.unique_concepts.map((cName, idx) => (
                              <span className="unique-tag" key={idx}>
                                {cName}
                              </span>
                            ))
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
