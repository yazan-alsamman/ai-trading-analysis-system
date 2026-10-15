import { describe, expect, it } from 'vitest';
import { notificationStore } from './notifications';

describe('notification store', () => {
  it('adds unread items newest-first, marks read and clears', () => {
    notificationStore.clear();
    notificationStore.add({ kind: 'price_alert', title: 'A', body: '', provenance: 'demo' });
    const second = notificationStore.add({ kind: 'system', title: 'B', body: '', provenance: 'demo' });
    expect(notificationStore.list().map((n) => n.title)).toEqual(['B', 'A']);
    expect(notificationStore.list().every((n) => !n.read)).toBe(true);
    notificationStore.markRead(second.id);
    expect(notificationStore.list().find((n) => n.id === second.id)?.read).toBe(true);
    notificationStore.markAllRead();
    expect(notificationStore.list().every((n) => n.read)).toBe(true);
    notificationStore.clear();
    expect(notificationStore.list()).toEqual([]);
  });

  it('keeps at most 50 notifications', () => {
    notificationStore.clear();
    for (let i = 0; i < 60; i++) notificationStore.add({ kind: 'system', title: String(i), body: '', provenance: 'demo' });
    expect(notificationStore.list()).toHaveLength(50);
    expect(notificationStore.list()[0]?.title).toBe('59');
  });
});
