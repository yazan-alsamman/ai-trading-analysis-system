import { useEffect } from 'react';
import { useAuth, useServices, useToast } from '@/app/contexts';
import { notificationStore, setRemoteNotificationHandlers } from '@/app/notifications';
import { isAbort } from '@/services/errors';

const POLL_MS = 120_000;

/**
 * Backend mode: mirrors the server notification inbox (/me/notifications) into
 * the notification centre, reloads on WebSocket pushes (with a slow polling
 * fallback), and sends read state back to the server. On sign-out the mirrored
 * items are removed so one account's notifications never show to the next.
 */
export function ServerInboxSync() {
  const services = useServices();
  const { session } = useAuth();
  const { notify } = useToast();
  const signedIn = services.source === 'api' && !!session && !session.isDemo;
  const userId = session?.user.id;

  useEffect(() => {
    if (!signedIn) {
      notificationStore.replaceRemote([]);
      return;
    }
    let ctrl: AbortController | null = null;
    const load = () => {
      ctrl?.abort();
      const c = (ctrl = new AbortController());
      services.inbox
        .list({ signal: c.signal })
        .then((items) => notificationStore.replaceRemote(items))
        .catch((e: unknown) => {
          if (!isAbort(e)) console.warn('Notification inbox unavailable', e);
        });
    };
    setRemoteNotificationHandlers({
      markRead: (id) => void services.inbox.markRead(id).catch(() => undefined),
      markAllRead: () => void services.inbox.markAllRead().catch(() => undefined),
    });
    load();
    const off = services.inbox.subscribe((n) => {
      if (n) notify(n.title, 'info');
      load();
    });
    const timer = setInterval(load, POLL_MS);
    return () => {
      ctrl?.abort();
      off();
      clearInterval(timer);
      setRemoteNotificationHandlers(null);
    };
  }, [services, signedIn, userId, notify]);

  return null;
}
