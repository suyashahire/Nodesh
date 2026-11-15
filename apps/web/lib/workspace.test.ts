import { describe, expect, it, vi } from "vitest";

import {
  deleteWorkspace,
  getWorkspaceStats,
  resumeOrCreateWorkspace,
  WORKSPACE_STORAGE_KEY,
} from "./workspace";

const workspace = {
  id: "e817dfd3-caf5-4c82-9d90-161c69b517e3",
  created_at: "2026-11-14T00:00:00Z",
  last_active_at: "2026-11-14T00:00:00Z",
};

function createStorage(initialValue: string | null = null) {
  let storedValue = initialValue;
  return {
    getItem: vi.fn(() => storedValue),
    removeItem: vi.fn(() => {
      storedValue = null;
    }),
    setItem: vi.fn((_key: string, value: string) => {
      storedValue = value;
    }),
  };
}

describe("resumeOrCreateWorkspace", () => {
  it("resumes a workspace persisted by the browser", async () => {
    const storage = createStorage(workspace.id);
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(workspace), { status: 200 }),
    );

    await expect(
      resumeOrCreateWorkspace({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        storage,
      }),
    ).resolves.toEqual(workspace);

    expect(fetchImplementation).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/workspaces/${workspace.id}`,
    );
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("replaces a stale workspace with a new one", async () => {
    const storage = createStorage("stale-id");
    const fetchImplementation = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(workspace), { status: 201 }));

    await expect(
      resumeOrCreateWorkspace({
        apiBaseUrl: "http://localhost:8000",
        fetchImplementation,
        storage,
      }),
    ).resolves.toEqual(workspace);

    expect(storage.removeItem).toHaveBeenCalledWith(WORKSPACE_STORAGE_KEY);
    expect(storage.setItem).toHaveBeenCalledWith(WORKSPACE_STORAGE_KEY, workspace.id);
    expect(fetchImplementation).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/v1/workspaces",
      { method: "POST" },
    );
  });
});

describe("deleteWorkspace", () => {
  it("permanently deletes the current anonymous workspace", async () => {
    const fetchImplementation = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      deleteWorkspace({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: workspace.id,
      }),
    ).resolves.toBeUndefined();

    expect(fetchImplementation).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/workspaces/${workspace.id}`,
      { method: "DELETE" },
    );
  });
});

describe("getWorkspaceStats", () => {
  it("fetches workspace aggregate statistics", async () => {
    const mockStats = {
      document_count: 3,
      concept_count: 10,
      relationship_count: 8,
      total_characters: 2500,
    };
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockStats), { status: 200 }),
    );

    await expect(
      getWorkspaceStats({
        apiBaseUrl: "http://localhost:8000/",
        fetchImplementation,
        workspaceId: workspace.id,
      }),
    ).resolves.toEqual(mockStats);

    expect(fetchImplementation).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/workspaces/${workspace.id}/stats`,
    );
  });
});

