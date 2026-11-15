export type StoredDocument = {
  id: string;
  workspace_id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  extraction_status: string;
  extracted_characters: number;
  created_at: string;
};

type FetchFunction = typeof fetch;

function documentsUrl(apiBaseUrl: string, workspaceId: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/v1/workspaces/${workspaceId}/documents`;
}

async function readDocuments(response: Response): Promise<StoredDocument[]> {
  if (!response.ok) {
    throw new Error(`Document request failed with status ${response.status}`);
  }
  return response.json() as Promise<StoredDocument[]>;
}

export async function listDocuments({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<StoredDocument[]> {
  return readDocuments(await fetchImplementation(documentsUrl(apiBaseUrl, workspaceId)));
}

export async function uploadDocument({
  apiBaseUrl,
  fetchImplementation,
  file,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  file: File;
  workspaceId: string;
}): Promise<StoredDocument> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetchImplementation(documentsUrl(apiBaseUrl, workspaceId), {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Document request failed with status ${response.status}`);
  }
  return response.json() as Promise<StoredDocument>;
}

export async function deleteDocument({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
  documentId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
  documentId: string;
}): Promise<void> {
  const response = await fetchImplementation(
    `${documentsUrl(apiBaseUrl, workspaceId)}/${documentId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new Error(`Document deletion failed with status ${response.status}`);
  }
}

export type SharedConceptOverview = {
  id: string;
  name: string;
  document_count: number;
  total_occurrences: number;
  document_ids: string[];
  document_names: string[];
};

export type DocumentConceptOverview = {
  document_id: string;
  filename: string;
  total_concepts: number;
  unique_concept_count: number;
  unique_concepts: string[];
};

export type DocumentPairOverlap = {
  doc_a_id: string;
  doc_a_name: string;
  doc_b_id: string;
  doc_b_name: string;
  shared_concept_count: number;
  jaccard_similarity: number;
  shared_concepts: string[];
};

export type WorkspaceDocumentComparison = {
  workspace_id: string;
  total_documents: number;
  documents: DocumentConceptOverview[];
  shared_concepts: SharedConceptOverview[];
  pairwise_overlap: DocumentPairOverlap[];
};

export async function getDocumentComparison({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<WorkspaceDocumentComparison> {
  const response = await fetchImplementation(
    `${documentsUrl(apiBaseUrl, workspaceId)}/comparison`,
  );
  if (!response.ok) {
    throw new Error(`Document comparison failed with status ${response.status}`);
  }
  return response.json() as Promise<WorkspaceDocumentComparison>;
}

