import { useCallback } from 'react';
import { useServices } from '@/app/contexts';
import { ACTIVE_BACKTEST_STATUSES, type BacktestStatus } from '@/domain/backtests';
import { strategyLabel, type CustomStrategySummary, type StrategyDefinition } from '@/domain/strategies';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatMoney, formatNumber, formatPct, MISSING } from '@/lib/format';

export const STATUS_LABEL: Record<BacktestStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export const isActiveStatus = (status: BacktestStatus) => ACTIVE_BACKTEST_STATUSES.includes(status);

/** Money in the backtest's quote currency; codes Intl does not know (e.g. USDT) are printed after the number. */
export function formatAmount(value: number | null, currency: string): string {
  if (value === null) return MISSING;
  try {
    return formatMoney(value, currency);
  } catch {
    return `${formatNumber(value, 2)} ${currency}`;
  }
}

export function formatMetric(kind: 'pct' | 'number' | 'money' | 'int' | 'ratio', value: number | null, currency: string): string {
  if (value === null) return MISSING;
  switch (kind) {
    case 'pct':
      return formatPct(value, 2);
    case 'money':
      return formatAmount(value, currency);
    case 'ratio':
      return formatNumber(value, 2);
    case 'int':
      return formatNumber(value, 0);
    case 'number':
      return formatNumber(value, 1);
  }
}

/** The currency of a backtest's amounts: the resolved config's, else the instrument's quote currency, else USD. */
export function backtestCurrency(config: Record<string, unknown> | null | undefined, symbol: string): string {
  if (typeof config?.currency === 'string' && config.currency) return config.currency;
  const quote = symbol.split('/')[1];
  return quote && /^[A-Z]{3,5}$/.test(quote) ? quote : 'USD';
}

export function formatWindow(start: number, end: number, timeZone: string): string {
  return `${formatDate(start, timeZone)} – ${formatDate(end, timeZone)}`;
}

/** Catalog + custom strategies, for choices and human labels. Custom strategies are optional (a failure leaves the catalog). */
export function useStrategyNames() {
  const services = useServices();
  const res = useResource('backtest-strategy-names', async (signal) => {
    const [catalog, custom] = await Promise.all([
      services.strategies.catalog({ signal }),
      services.strategies.listCustom({ signal }).catch((): CustomStrategySummary[] => []),
    ]);
    return { catalog, custom };
  });
  const data = res.data;
  const label = useCallback((key: string) => strategyLabel(key, data?.catalog ?? [], data?.custom ?? []), [data]);
  const catalog: StrategyDefinition[] = data?.catalog ?? [];
  const custom: CustomStrategySummary[] = data?.custom ?? [];
  return { res, catalog, custom, label };
}
