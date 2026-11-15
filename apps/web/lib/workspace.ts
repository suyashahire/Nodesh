export const WORKSPACE_STORAGE_KEY = "nodesh.workspace-id";

export type Workspace = {
  id: string;
  created_at: string;
  last_active_at: string;
};

export type WorkspaceStorage = Pick<Storage, "getItem" | "removeItem" | "setItem">;
type FetchFunction = typeof fetch;

function workspaceUrl(apiBaseUrl: string, workspaceId?: string): string {
  const baseUrl = apiBaseUrl.replace(/\/$/, "");
  return workspaceId ? `${baseUrl}/api/v1/workspaces/${workspaceId}` : `${baseUrl}/api/v1/workspaces`;
}

async function readWorkspace(response: Response): Promise<Workspace> {
  if (!response.ok) {
    throw new Error(`Workspace request failed with status ${response.status}`);
  }
  return response.json() as Promise<Workspace>;
}

export async function resumeOrCreateWorkspace({
  apiBaseUrl,
  fetchImplementation,
  storage,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  storage: WorkspaceStorage;
}): Promise<Workspace> {
  const storedWorkspaceId = storage.getItem(WORKSPACE_STORAGE_KEY);

  if (storedWorkspaceId) {
    const resumeResponse = await fetchImplementation(workspaceUrl(apiBaseUrl, storedWorkspaceId));
    if (resumeResponse.ok) {
      return readWorkspace(resumeResponse);
    }
    if (resumeResponse.status !== 404) {
      return readWorkspace(resumeResponse);
    }
    storage.removeItem(WORKSPACE_STORAGE_KEY);
  }

  const createdWorkspace = await readWorkspace(
    await fetchImplementation(workspaceUrl(apiBaseUrl), { method: "POST" }),
  );
  storage.setItem(WORKSPACE_STORAGE_KEY, createdWorkspace.id);
  return createdWorkspace;
}

export async function deleteWorkspace({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<void> {
  const response = await fetchImplementation(workspaceUrl(apiBaseUrl, workspaceId), {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Workspace deletion failed with status ${response.status}`);
  }
}

export type WorkspaceStats = {
  document_count: number;
  concept_count: number;
  relationship_count: number;
  total_characters: number;
};

export async function getWorkspaceStats({
  apiBaseUrl,
  fetchImplementation,
  workspaceId,
}: {
  apiBaseUrl: string;
  fetchImplementation: FetchFunction;
  workspaceId: string;
}): Promise<WorkspaceStats> {
  const response = await fetchImplementation(
    `${workspaceUrl(apiBaseUrl, workspaceId)}/stats`,
  );
  if (!response.ok) {
    throw new Error(`Workspace stats request failed with status ${response.status}`);
  }
  return response.json() as Promise<WorkspaceStats>;
}

