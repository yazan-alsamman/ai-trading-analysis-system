import { useSyncExternalStore } from 'react';
import { z } from 'zod';
import { localId } from '@/lib/cn';
import { readStored, writeStored } from '@/lib/storage';

/**
 * Notification centre store. Holds the latest 50 notifications in this
 * browser. In demo mode they come from the client-side alert monitor; with a
 * backend they would be delivered by the notification service (SF7).
 */
const NotificationSchema = z.object({
  id: z.string(),
  kind: z.enum(['price_alert', 'opportunity', 'system']),
  title: z.string(),
  body: z.string(),
  createdAt: z.number(),
  read: z.boolean(),
  provenance: z.enum(['demo', 'live']),
  href: z.string().optional(),
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

export const notificationStore = {
  list: () => items,
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  add(n: Omit<AppNotification, 'id' | 'createdAt' | 'read'>): AppNotification {
    const created: AppNotification = { ...n, id: localId('ntf'), createdAt: Date.now(), read: false };
    commit([created, ...items]);
    return created;
  },
  markAllRead: () => commit(items.map((n) => ({ ...n, read: true }))),
  markRead: (id: string) => commit(items.map((n) => (n.id === id ? { ...n, read: true } : n))),
  clear: () => commit([]),
};

export function useNotifications() {
  const list = useSyncExternalStore(notificationStore.subscribe, notificationStore.list, notificationStore.list);
  return { items: list, unread: list.filter((n) => !n.read).length };
}
