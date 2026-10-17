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
const listeners = new Set<() => void>();

function commit(next: AppNotification[]) {
  items = next.slice(0, MAX);
  writeStored(KEY, items);
  listeners.forEach((l) => l());
}

/** Set by the server sync in backend mode, so read state is saved on the server. */
let remoteHandlers: { markRead: (id: string) => void; markAllRead: () => void } | null = null;
export function setRemoteNotificationHandlers(h: typeof remoteHandlers) {
  remoteHandlers = h;
}

export const notificationStore = {
  list: () => items,
  /** Replace the server-mirrored items (local ones are kept). */
  replaceRemote(remote: AppNotification[]) {
    commit([...remote, ...items.filter((n) => !n.remote)].sort((a, b) => b.createdAt - a.createdAt));
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
    if (items.some((n) => n.remote && !n.read)) remoteHandlers?.markAllRead();
    commit(items.map((n) => ({ ...n, read: true })));
  },
  markRead: (id: string) => {
    if (items.some((n) => n.id === id && n.remote && !n.read)) remoteHandlers?.markRead(id);
    commit(items.map((n) => (n.id === id ? { ...n, read: true } : n)));
  },
  /** Clears local items; the server inbox (backend mode) is authoritative and stays. */
  clear: () => commit(items.filter((n) => n.remote)),
};

export function useNotifications() {
  const list = useSyncExternalStore(notificationStore.subscribe, notificationStore.list, notificationStore.list);
  return { items: list, unread: list.filter((n) => !n.read).length };
}
