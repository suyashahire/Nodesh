import type { WorkspaceConcept } from "./concepts";
import type { ConceptRelationship } from "./relationships";
import type { KnowledgeGraph } from "./graph";

export type AnalysisResult = {
  documents_analyzed: number;
  concepts: WorkspaceConcept[];
  relationships: ConceptRelationship[];
  graph: KnowledgeGraph;
};

export async function analyzeWorkspace({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: typeof fetch;
  workspaceId: string;
}): Promise<AnalysisResult> {
  const response = await fetchImplementation(
    `${apiBaseUrl.replace(/\/$/, "")}/api/v1/workspaces/${workspaceId}/analyze`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`Analyze request failed with status ${response.status}`);
  }
  return response.json() as Promise<AnalysisResult>;
}
