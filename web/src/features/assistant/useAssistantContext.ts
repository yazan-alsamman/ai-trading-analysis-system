import { useMemo, useState } from 'react';
import { z } from 'zod';
import { usePreferences, useServices } from '@/app/contexts';
import type { AssistantContext } from '@/domain/assistant';
import type { InstrumentSymbol } from '@/domain/instruments';
import type { Timeframe } from '@/domain/market';
import { useResource } from '@/hooks/useResource';
import { readStored, writeStored } from '@/lib/storage';

const SHARE_KEY = 'ata.assistant.shareRisk.v1';

/**
 * Whether the user's risk profile is included in the assistant context.
 * Default ON in demo mode (nothing leaves the browser), OFF in API mode
 * (the context would be sent to the backend).
 */
export function useShareRisk(): [boolean, (v: boolean) => void] {
  const { source } = useServices();
  const [share, setShare] = useState(() => readStored(SHARE_KEY, z.boolean(), source === 'demo'));
  return [
    share,
    (v: boolean) => {
      setShare(v);
      writeStored(SHARE_KEY, v);
    },
  ];
}

/** Load exactly the data the assistant will be allowed to use for one instrument/timeframe. */
export function useAssistantContext(symbol: InstrumentSymbol, timeframe: Timeframe, shareRisk: boolean) {
  const services = useServices();
  const { prefs } = usePreferences();
  const opportunity = useResource(`assistant-opp:${symbol}:${timeframe}`, (signal) => services.opportunities.getLatest(symbol, timeframe, { signal }));
  const confluence = useResource(`assistant-conf:${symbol}`, (signal) => services.opportunities.list({ symbol }, { signal }));
  const price = useResource(`assistant-price:${symbol}:${timeframe}`, (signal) => services.market.getCandles(symbol, timeframe, { signal, limit: 2 }));

  const context = useMemo<AssistantContext>(() => {
    const last = price.data?.candles[price.data.candles.length - 1];
    return {
      symbol,
      timeframe,
      lastPrice: last?.close ?? null,
      priceProvenance: price.data?.provenance ?? null,
      feedStatus: null,
      opportunity: opportunity.data ?? null,
      confluence: confluence.data ?? [],
      riskProfile: shareRisk ? prefs.riskProfile : null,
    };
  }, [symbol, timeframe, price.data, opportunity.data, confluence.data, shareRisk, prefs.riskProfile]);

  const loading = opportunity.status === 'loading' || confluence.status === 'loading' || price.status === 'loading';
  const failed = [opportunity, confluence, price].filter((r) => r.status === 'error' && !r.data).length;
  return { context, loading, failed, reload: () => [opportunity, confluence, price].forEach((r) => r.reload()) };
}
