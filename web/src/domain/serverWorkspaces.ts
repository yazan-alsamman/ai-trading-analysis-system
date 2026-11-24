/**
 * Workspaces saved on the server (docs/workspaces.md), shared with the mobile
 * app. Every state change carries the version it edited; a stale version is
 * refused with 409 so a newer change made on another device is never
 * overwritten silently.
 */

export interface ServerWorkspaceSummary {
  id: string;
  name: string;
  position: number;
  isDefault: boolean;
  version: number;
  panelCount: number;
  isShared: boolean;
  updatedAt: number;
}

/** The workspace state document (schema_version 1). Kept as the server's JSON. */
export type WorkspaceStateDoc = Record<string, unknown>;

export interface ServerWorkspace extends ServerWorkspaceSummary {
  state: WorkspaceStateDoc;
  unavailableInstrumentIds: string[];
  shareSlug: string | null;
}

/** 409 from a PUT: someone else saved first. */
export interface WorkspaceConflict {
  currentVersion: number | null;
  updatedAt: number | null;
}

export interface WorkspaceUpdatedEvent {
  workspaceId: string | null;
  version: number | null;
  action: string;
}

/** Sharing a server workspace (analysts, experts and admins): a read-only link. */
export interface WorkspaceShare {
  isShared: boolean;
  slug: string | null;
}

/** A workspace someone shared (GET /workspaces/shared/{slug}): no ids, the owner's name and role only. */
export interface SharedWorkspace {
  name: string;
  owner: { name: string; role: string };
  state: WorkspaceStateDoc;
  unavailableInstrumentIds: string[];
  updatedAt: number;
}
