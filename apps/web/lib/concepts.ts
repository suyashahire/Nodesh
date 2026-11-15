export type WorkspaceConcept = {
  id: string;
  name: string;
  document_count: number;
  total_occurrences: number;
  tfidf_score?: number;
  source_documents?: string[];
  created_at: string;
  updated_at: string;
};

type FetchFunction = typeof fetch;

function conceptsUrl(apiBaseUrl: string, workspaceId: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/v1/workspaces/${workspaceId}/concepts`;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Concept request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function listConcepts({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<WorkspaceConcept[]> {
  return readJson(await fetchImplementation(conceptsUrl(apiBaseUrl, workspaceId)));
}

export async function extractConcepts({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<{ documents_analyzed: number; concepts: WorkspaceConcept[] }> {
  return readJson(
    await fetchImplementation(`${conceptsUrl(apiBaseUrl, workspaceId)}/extract`, {
      method: "POST",
    }),
  );
}

export type ConceptMergeSuggestion = {
  source_concept_id: string;
  source_name: string;
  target_concept_id: string;
  target_name: string;
  similarity: number;
  reason: string;
};

export type ConceptMergeResult = {
  merged_into_concept_id: string;
  merged_concept_name: string;
  source_occurrences_merged: number;
  new_total_occurrences: number;
};

export async function getMergeSuggestions({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<ConceptMergeSuggestion[]> {
  return readJson(
    await fetchImplementation(`${conceptsUrl(apiBaseUrl, workspaceId)}/merge-suggestions`),
  );
}

export async function mergeConcepts({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
  sourceConceptId,
  targetConceptId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
  sourceConceptId: string;
  targetConceptId: string;
}): Promise<ConceptMergeResult> {
  return readJson(
    await fetchImplementation(`${conceptsUrl(apiBaseUrl, workspaceId)}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_concept_id: sourceConceptId,
        target_concept_id: targetConceptId,
      }),
    }),
  );
}

export type ConceptDossier = {
  concept_id: string;
  concept_name: string;
  summary: string;
  key_sentences: string[];
  source_documents: string[];
};

export async function getConceptDossier({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
  conceptId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
  conceptId: string;
}): Promise<ConceptDossier> {
  return readJson(
    await fetchImplementation(`${conceptsUrl(apiBaseUrl, workspaceId)}/${conceptId}/dossier`),
  );
}
