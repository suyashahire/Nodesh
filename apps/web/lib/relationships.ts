export type ConceptRelationship = {
  id: string;
  source_concept_id: string;
  source_name: string;
  target_concept_id: string;
  target_name: string;
  relationship_type: string;
  document_count: number;
  strength: number;
  created_at: string;
  updated_at: string;
};

type FetchFunction = typeof fetch;

function relationshipsUrl(apiBaseUrl: string, workspaceId: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/v1/workspaces/${workspaceId}/relationships`;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Relationship request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function listRelationships({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<ConceptRelationship[]> {
  return readJson(await fetchImplementation(relationshipsUrl(apiBaseUrl, workspaceId)));
}

export async function extractRelationships({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<{ documents_analyzed: number; relationships: ConceptRelationship[] }> {
  return readJson(
    await fetchImplementation(`${relationshipsUrl(apiBaseUrl, workspaceId)}/extract`, {
      method: "POST",
    }),
  );
}

export type RelationshipEvidence = {
  document_id: string;
  original_filename: string;
  source_occurrences: number;
  target_occurrences: number;
  snippet: string;
};

export function formatPredicate(predicate?: string): string {
  if (!predicate) return "related to";
  switch (predicate) {
    case "built_with":
      return "built with";
    case "uses":
      return "uses";
    case "applied_to":
      return "applied to";
    case "trained_for":
      return "trained for";
    case "affiliated_with":
      return "affiliated with";
    case "integrated_with":
      return "integrated with";
    case "part_of":
      return "part of";
    case "co_occurs_with":
      return "related to";
    default:
      return predicate.replace(/_/g, " ");
  }
}

export function getPredicateClass(predicate?: string): string {
  if (!predicate) return "predicate-co_occurs_with";
  const valid = [
    "built_with",
    "uses",
    "applied_to",
    "trained_for",
    "affiliated_with",
    "integrated_with",
    "part_of",
    "co_occurs_with",
  ];
  return valid.includes(predicate) ? `predicate-${predicate}` : "predicate-co_occurs_with";
}

export async function getRelationshipEvidence({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
  relationshipId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
  relationshipId: string;
}): Promise<RelationshipEvidence[]> {
  return readJson(
    await fetchImplementation(
      `${relationshipsUrl(apiBaseUrl, workspaceId)}/${relationshipId}/evidence`,
    ),
  );
}
