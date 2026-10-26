import type { Candle, FeedStatus } from '@/domain/market';

/**
 * Client for the backend's market hub (`/ws/market`, docs/websocket.md).
 *
 *  - ONE connection, opened on the first subscription and closed shortly after the last.
 *  - Browsers cannot set headers on a WebSocket, so the access token goes in the
 *    `token` query parameter (the backend's documented mechanism).
 *  - Subscriptions are re-sent after every reconnect; `{"op":"ping"}` every 30 s.
 *  - Close 4401 (bad/expired token): refresh the token, then reconnect. If the
 *    session cannot be refreshed, subscribers get `error` and nothing retries.
 *  - Other closes: exponential back-off (1 s … 30 s).
 */

type WebSocketCtor = new (url: string) => WebSocket;

export interface MarketSocketOptions {
  url: string;
  getToken: () => Promise<string | undefined>;
  refreshToken: () => Promise<string | undefined>;
  WebSocketImpl?: WebSocketCtor;
  pingMs?: number;
  idleCloseMs?: number;
}

interface Listener {
  onCandle: (c: Candle) => void;
  onStatus: (s: FeedStatus) => void;
}

export interface MarketSocket {
  subscribeCandles(instrumentId: string, timeframe: string, listener: Listener): () => void;
  /** Server pushes on the user's own topic (notifications, price alerts…). */
  onUserEvent(type: string, handler: (msg: Record<string, unknown>) => void): () => void;
  /**
   * Any other instrument topic (e.g. `ai_setups`): `topicKey` is the topic name the
   * server puts in its frames (`ai:setups:<id>`). Re-sent after every reconnect.
   */
  subscribeTopic(topic: string, instrumentId: string, topicKey: string, handler: (msg: Record<string, unknown>) => void): () => void;
  /** Number of open topic subscriptions (diagnostics and tests). */
  topicCount(): number;
}

const topicKey = (id: string, tf: string) => `candles:${id}:${tf}`;

export function createMarketSocket(opts: MarketSocketOptions): MarketSocket {
  const Impl: WebSocketCtor | undefined = opts.WebSocketImpl ?? (typeof WebSocket !== 'undefined' ? WebSocket : undefined);
  const pingMs = opts.pingMs ?? 30_000;
  const idleCloseMs = opts.idleCloseMs ?? 5_000;
  const topics = new Map<string, { id: string; tf: string; listeners: Set<Listener> }>();
  const userHandlers = new Map<string, Set<(msg: Record<string, unknown>) => void>>();
  const extraTopics = new Map<string, { sub: Record<string, string>; handlers: Set<(msg: Record<string, unknown>) => void> }>();
  let socket: WebSocket | null = null;
  let ping: ReturnType<typeof setInterval> | undefined;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let idle: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;

  const emitStatus = (status: FeedStatus, key?: string) => {
    for (const [k, t] of topics) if (!key || k === key) t.listeners.forEach((l) => l.onStatus(status));
  };
  const send = (msg: object) => {
    if (socket?.readyState === 1) socket.send(JSON.stringify(msg));
  };
  const subscribeMsg = (id: string, tf: string) => ({ op: 'subscribe', topic: 'candles', instrument_id: id, timeframe: tf });

  const wanted = () => topics.size > 0 || userHandlers.size > 0 || extraTopics.size > 0;

  async function connect() {
    if (socket || !Impl || !wanted()) return;
    const token = await opts.getToken().catch(() => undefined);
    if (!token) {
      // Signed out: nothing to stream. A later subscription (after sign-in) connects again.
      emitStatus('error');
      return;
    }
    if (socket || !wanted()) return;
    emitStatus('connecting');
    const ws = new Impl(`${opts.url}?token=${encodeURIComponent(token)}`);
    socket = ws;
    ws.onopen = () => {
      attempt = 0;
      for (const t of topics.values()) send(subscribeMsg(t.id, t.tf));
      for (const t of extraTopics.values()) send({ op: 'subscribe', ...t.sub });
      ping = setInterval(() => send({ op: 'ping' }), pingMs);
    };
    ws.onmessage = (ev) => {
      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(String(ev.data)) as Record<string, unknown>;
      } catch {
        return;
      }
      const type = msg.type;
      const topic = typeof msg.topic === 'string' ? msg.topic : '';
      if ((type === 'candle' || type === 'snapshot') && topics.has(topic)) {
        const c = msg.candle as Candle | null | undefined;
        const t = topics.get(topic);
        t?.listeners.forEach((l) => l.onStatus('live'));
        if (c && typeof c.time === 'number') t?.listeners.forEach((l) => l.onCandle(c));
      } else if (topic && extraTopics.has(topic) && type !== 'subscribed') {
        extraTopics.get(topic)?.handlers.forEach((h) => h(msg));
      } else if (type === 'subscribed' && topics.has(topic)) {
        emitStatus('live', topic);
      } else if (type === 'error' && msg.code === 'unknown_instrument') {
        emitStatus('error', topic || undefined);
      } else if (typeof type === 'string') {
        userHandlers.get(type)?.forEach((h) => h(msg));
      }
    };
    ws.onclose = (ev) => {
      if (ping) clearInterval(ping);
      ping = undefined;
      socket = null;
      if (!wanted()) return;
      if (ev.code === 4401) {
        emitStatus('connecting');
        opts.refreshToken().then(
          (fresh) => {
            if (fresh) void connect();
            else emitStatus('error'); // session over: no retry loop
          },
          () => schedule(),
        );
        return;
      }
      schedule();
    };
    ws.onerror = () => {
      /* onclose follows and handles the retry */
    };
  }

  function schedule() {
    if (retry || !wanted()) return;
    emitStatus('connecting');
    const delay = Math.min(30_000, 1_000 * 2 ** attempt++);
    retry = setTimeout(() => {
      retry = undefined;
      void connect();
    }, delay);
  }

  function maybeClose() {
    if (idle) clearTimeout(idle);
    idle = setTimeout(() => {
      idle = undefined;
      if (wanted()) return;
      if (retry) clearTimeout(retry);
      retry = undefined;
      socket?.close(1000);
      socket = null;
    }, idleCloseMs);
  }

  return {
    subscribeCandles(instrumentId, timeframe, listener) {
      const key = topicKey(instrumentId, timeframe);
      let t = topics.get(key);
      if (!t) {
        t = { id: instrumentId, tf: timeframe, listeners: new Set() };
        topics.set(key, t);
        send(subscribeMsg(instrumentId, timeframe));
      }
      t.listeners.add(listener);
      if (!Impl) listener.onStatus('error');
      else if (socket?.readyState === 1) listener.onStatus('live');
      else void connect();
      return () => {
        const cur = topics.get(key);
        if (!cur) return;
        cur.listeners.delete(listener);
        if (cur.listeners.size === 0) {
          topics.delete(key);
          send({ op: 'unsubscribe', topic: 'candles', instrument_id: instrumentId, timeframe });
          maybeClose();
        }
      };
    },
    onUserEvent(type, handler) {
      let set = userHandlers.get(type);
      if (!set) userHandlers.set(type, (set = new Set()));
      set.add(handler);
      void connect();
      return () => {
        set.delete(handler);
        if (set.size === 0) userHandlers.delete(type);
        maybeClose();
      };
    },
    subscribeTopic(topic, instrumentId, key, handler) {
      let t = extraTopics.get(key);
      if (!t) {
        t = { sub: { topic, instrument_id: instrumentId }, handlers: new Set() };
        extraTopics.set(key, t);
        send({ op: 'subscribe', ...t.sub });
      }
      t.handlers.add(handler);
      void connect();
      return () => {
        const cur = extraTopics.get(key);
        if (!cur) return;
        cur.handlers.delete(handler);
        if (cur.handlers.size === 0) {
          extraTopics.delete(key);
          send({ op: 'unsubscribe', ...cur.sub });
          maybeClose();
        }
      };
    },
    topicCount: () => topics.size + extraTopics.size,
  };
}
