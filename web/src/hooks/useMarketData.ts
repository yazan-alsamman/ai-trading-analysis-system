import { useEffect, useState } from 'react';
import { useServices } from '@/app/contexts';
import type { InstrumentSymbol } from '@/domain/instruments';
import type { Candle, CandleSeries, FeedStatus, Quote, Timeframe } from '@/domain/market';
import { config } from '@/services/config';
import { useNow, useOnlineStatus } from './useEnvironment';
import { useResource, type Resource } from './useResource';

/** Combine the stream's own status with connectivity and freshness. */
export function effectiveFeedStatus(streamStatus: FeedStatus, online: boolean, lastUpdateMs: number | undefined, nowMs: number): FeedStatus {
  if (!online) return 'offline';
  if (streamStatus === 'closed' || streamStatus === 'error' || streamStatus === 'connecting') return streamStatus;
  if (lastUpdateMs !== undefined && nowMs - lastUpdateMs > config.staleAfterMs) return 'stale';
  return streamStatus;
}

export interface LiveCandles {
  resource: Resource<CandleSeries>;
  candles: Candle[];
  feedStatus: FeedStatus;
  lastUpdateMs: number | undefined;
}

/**
 * Historical candles + live updates for one instrument/timeframe.
 * Updates are merged by candle time, so out-of-order or duplicate updates
 * cannot corrupt the series (older bars are ignored, same bar is replaced).
 */
export function useLiveCandles(symbol: InstrumentSymbol, timeframe: Timeframe): LiveCandles {
  const services = useServices();
  const key = `${symbol}:${timeframe}`;
  const resource = useResource(`candles:${key}`, (signal) => services.market.getCandles(symbol, timeframe, { signal }));
  const [live, setLive] = useState<{ key: string; candles: Candle[]; lastUpdateMs: number | undefined }>({ key: '', candles: [], lastUpdateMs: undefined });
  const [streamStatus, setStreamStatus] = useState<FeedStatus>('connecting');
  const online = useOnlineStatus();
  const now = useNow(1000);

  const loaded = resource.data;
  useEffect(() => {
    if (!loaded) return;
    setLive({ key, candles: loaded.candles, lastUpdateMs: loaded.asOf });
    setStreamStatus('connecting');
    const unsubscribe = services.market.subscribeCandles(symbol, timeframe, {
      onCandle: (candle) =>
        setLive((prev) => {
          if (prev.key !== key) return prev;
          const last = prev.candles[prev.candles.length - 1];
          if (last && candle.time < last.time) return prev; // late/out-of-order update
          const candles = last && candle.time === last.time ? [...prev.candles.slice(0, -1), candle] : [...prev.candles, candle];
          return { key, candles, lastUpdateMs: Date.now() };
        }),
      onStatus: setStreamStatus,
    });
    return unsubscribe;
  }, [loaded, key, services, symbol, timeframe]);

  const current = live.key === key ? live : { candles: loaded?.candles ?? [], lastUpdateMs: loaded?.asOf };
  return {
    resource,
    candles: current.candles,
    lastUpdateMs: current.lastUpdateMs,
    feedStatus: effectiveFeedStatus(streamStatus, online, current.lastUpdateMs, now),
  };
}

export interface LiveQuotes {
  quotes: Map<InstrumentSymbol, Quote>;
  status: 'loading' | 'success' | 'error';
  error: unknown;
  feedStatus: FeedStatus;
  reload: () => void;
}

/** Quotes for the watchlist, kept current by the quote stream. */
export function useLiveQuotes(): LiveQuotes {
  const services = useServices();
  const resource = useResource('quotes', (signal) => services.market.getQuotes({ signal }));
  const [quotes, setQuotes] = useState<Map<InstrumentSymbol, Quote>>(new Map());
  const [streamStatus, setStreamStatus] = useState<FeedStatus>('connecting');
  const [lastUpdate, setLastUpdate] = useState<number | undefined>();
  const online = useOnlineStatus();
  const now = useNow(1000);

  const initial = resource.data;
  useEffect(() => {
    if (!initial) return;
    setQuotes(new Map(initial.map((q) => [q.symbol, q])));
    setLastUpdate(Date.now());
    return services.market.subscribeQuotes({
      onQuotes: (next) => {
        setQuotes((prev) => {
          const map = new Map(prev);
          // Ignore quotes older than what we already show.
          for (const q of next) if ((map.get(q.symbol)?.time ?? 0) <= q.time) map.set(q.symbol, q);
          return map;
        });
        setLastUpdate(Date.now());
      },
      onStatus: setStreamStatus,
    });
  }, [initial, services]);

  return {
    quotes,
    status: resource.status,
    error: resource.error,
    feedStatus: effectiveFeedStatus(streamStatus, online, lastUpdate, now),
    reload: resource.reload,
  };
}
