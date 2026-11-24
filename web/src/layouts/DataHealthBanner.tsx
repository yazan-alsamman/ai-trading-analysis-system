import { TriangleAlert, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useServices } from '@/app/contexts';
import { IconButton } from '@/components/ui/Button';
import { useResource } from '@/hooks/useResource';

const POLL_MS = 5 * 60_000;
const HIDDEN_KEY = 'ata.data-health-hidden.v1';
const STATUS_LABEL = { degraded: 'degraded', no_data: 'no data', ok: 'ok', closed: 'market closed' } as const;

function readHidden(): boolean {
  try {
    return window.sessionStorage.getItem(HIDDEN_KEY) === '1';
  } catch {
    return false;
  }
}

function lagText(seconds: number | null): string | null {
  if (seconds === null) return null;
  if (seconds < 120) return `${Math.round(seconds)} s behind`;
  if (seconds < 7200) return `${Math.round(seconds / 60)} min behind`;
  return `${Math.round(seconds / 3600)} h behind`;
}

/**
 * Backend mode: the server's data-quality report (GET /health/data,
 * docs/data-quality.md), checked every 5 minutes. Silent while every
 * monitored instrument is fine (or its market is closed); otherwise it says
 * which prices may be delayed or missing.
 */
export function DataHealthBanner() {
  const services = useServices();
  const [hidden, setHidden] = useState(readHidden);
  const res = useResource('data-health', (signal) => services.marketContext.dataHealth({ signal }));
  const reload = res.reload;
  useEffect(() => {
    const id = setInterval(reload, POLL_MS);
    return () => clearInterval(id);
  }, [reload]);

  const health = res.data;
  if (hidden || !health || (health.status !== 'degraded' && health.status !== 'no_data')) return null;
  const affected = health.instruments.filter((i) => i.status === 'degraded' || i.status === 'no_data');

  const dismiss = () => {
    setHidden(true);
    try {
      window.sessionStorage.setItem(HIDDEN_KEY, '1');
    } catch {
      /* storage unavailable: hidden for this page view only */
    }
  };

  return (
    <div role="status" className="flex items-start gap-2.5 border-b border-warning/40 bg-warning-soft px-4 py-2 text-sm text-fg sm:px-6">
      <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Market data check: prices may be delayed or incomplete.</p>
        {affected.length > 0 && (
          <ul className="mt-0.5 flex flex-col gap-0.5 text-xs text-fg-2">
            {affected.map((i) => {
              const failed = i.failedChecks.find((c) => !c.ok);
              const lag = lagText(i.lagSeconds);
              return (
                <li key={`${i.instrument}:${i.timeframe}`}>
                  <span className="font-medium text-fg">{i.instrument}</span> {i.timeframe}: {STATUS_LABEL[i.status]}
                  {lag && ` · ${lag}`}
                  {failed && ` · ${failed.detail}`}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <IconButton icon={X} size="sm" label="Hide the data check notice for this session" onClick={dismiss} tooltipSide="left" />
    </div>
  );
}
