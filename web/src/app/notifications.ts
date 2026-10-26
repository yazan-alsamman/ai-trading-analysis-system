import { useSyncExternalStore } from 'react';
import { z } from 'zod';
import { localId } from '@/lib/cn';
import { readStored, writeStored } from '@/lib/storage';

/**
 * Notification centre store. Holds the latest 50 notifications.
 *  - Demo mode: produced in this browser by the client-side alert monitor.
 *  - Backend mode: a mirror of the server inbox (/me/notifications), kept in
 *    sync by features/notifications/ServerInboxSync.tsx; marking read goes to
 *    the server through `remoteHandlers`.
 */
const NotificationSchema = z.object({
  id: z.string(),
  kind: z.enum(['price_alert', 'opportunity', 'signal', 'system']),
  title: z.string(),
  body: z.string(),
  createdAt: z.number(),
  read: z.boolean(),
  provenance: z.enum(['demo', 'live']),
  href: z.string().optional(),
  /** Mirrored from the server inbox. */
  remote: z.boolean().optional(),
});
export type AppNotification = z.infer<typeof NotificationSchema>;

const KEY = 'ata.notifications.v1';
const MAX = 50;

let items: AppNotification[] = readStored(KEY, z.array(NotificationSchema), []);
/** Backend mode: the server's unread count, which can exceed the 50 mirrored items. */
let remoteUnread: number | null = null;
let snapshot: { items: AppNotification[]; remoteUnread: number | null } = { items, remoteUnread };
const listeners = new Set<() => void>();

function emit() {
  snapshot = { items, remoteUnread };
  listeners.forEach((l) => l());
}

function commit(next: AppNotification[]) {
  items = next.slice(0, MAX);
  writeStored(KEY, items);
  emit();
}

/** Set by the server sync in backend mode, so read state and deletions are saved on the server. */
let remoteHandlers: { markRead: (id: string) => void; markAllRead: () => void; remove?: (id: string) => void } | null = null;
export function setRemoteNotificationHandlers(h: typeof remoteHandlers) {
  remoteHandlers = h;
}

export const notificationStore = {
  list: () => items,
  /** Replace the server-mirrored items (local ones are kept). */
  replaceRemote(remote: AppNotification[]) {
    if (remote.length === 0) remoteUnread = null;
    commit([...remote, ...items.filter((n) => !n.remote)].sort((a, b) => b.createdAt - a.createdAt));
  },
  /** The server's unread count (backend mode); `null` falls back to counting the mirrored items. */
  setRemoteUnread(count: number | null) {
    remoteUnread = count;
    emit();
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  add(n: Omit<AppNotification, 'id' | 'createdAt' | 'read'>): AppNotification {
    const created: AppNotification = { ...n, id: localId('ntf'), createdAt: Date.now(), read: false };
    commit([created, ...items]);
    return created;
  },
  markAllRead: () => {
    if (items.some((n) => n.remote && !n.read) || remoteUnread) remoteHandlers?.markAllRead();
    if (remoteUnread !== null) remoteUnread = 0;
    commit(items.map((n) => ({ ...n, read: true })));
  },
  markRead: (id: string) => {
    if (items.some((n) => n.id === id && n.remote && !n.read)) {
      remoteHandlers?.markRead(id);
      if (remoteUnread) remoteUnread -= 1;
    }
    commit(items.map((n) => (n.id === id ? { ...n, read: true } : n)));
  },
  /** Deletes one notification (on the server too, for mirrored ones). */
  remove: (id: string) => {
    const target = items.find((n) => n.id === id);
    if (!target) return;
    if (target.remote) {
      remoteHandlers?.remove?.(id);
      if (!target.read && remoteUnread) remoteUnread -= 1;
    }
    commit(items.filter((n) => n.id !== id));
  },
  /** Clears local items; the server inbox (backend mode) is authoritative and stays. */
  clear: () => commit(items.filter((n) => n.remote)),
};

const getSnapshot = () => snapshot;

export function useNotifications() {
  const { items: list, remoteUnread: serverUnread } = useSyncExternalStore(notificationStore.subscribe, getSnapshot, getSnapshot);
  const localUnread = list.filter((n) => !n.read && !n.remote).length;
  const mirroredUnread = list.filter((n) => !n.read && n.remote).length;
  // The server count covers notifications beyond the 50 mirrored here; never show fewer than are listed.
  return { items: list, unread: localUnread + Math.max(mirroredUnread, serverUnread ?? 0) };
}
