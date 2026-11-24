import { Badge } from '@/components/ui/Badge';
import { JsonView } from '@/components/ui/JsonView';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { useServices } from '@/app/contexts';
import { useResource } from '@/hooks/useResource';
import { formatPct, MISSING } from '@/lib/format';

const ORDER = ['conservative', 'balanced', 'aggressive'];
const label = (name: string) => name.charAt(0).toUpperCase() + name.slice(1);

const obj = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** A stop config in words (docs/risk-management.md); unknown shapes are left to the detail view. */
function stopText(v: unknown): string {
  const s = obj(v);
  if (!s) return 'None';
  if (s.type === 'atr') return `${num(s.multiplier) ?? '?'} × ATR(${num(s.length) ?? '?'})`;
  if (s.type === 'percent') return `${num(s.pct) ?? num(s.percent) ?? '?'}% from entry`;
  return typeof s.type === 'string' ? s.type.replace(/_/g, ' ') : 'Custom';
}

function targetText(v: unknown): string {
  const t = obj(v);
  if (!t) return 'None';
  if (t.type === 'r_multiple' && Array.isArray(t.levels))
    return t.levels
      .map((l) => obj(l))
      .filter((l): l is Record<string, unknown> => l !== null)
      .map((l) => `${num(l.r) ?? '?'}R (close ${num(l.close_pct) ?? '?'}%)`)
      .join(', ');
  return typeof t.type === 'string' ? t.type.replace(/_/g, ' ') : 'Custom';
}

function guardsText(v: unknown): string {
  const g = obj(v);
  if (!g) return 'None';
  const parts = [
    num(g.max_daily_loss_pct) !== null && `daily loss ≤ ${formatPct(num(g.max_daily_loss_pct))}`,
    num(g.max_drawdown_pct) !== null && `drawdown ≤ ${formatPct(num(g.max_drawdown_pct))}`,
    num(g.max_consecutive_losses) !== null && `pause after ${num(g.max_consecutive_losses)} losses`,
    (num(g.cooldown_bars) ?? 0) > 0 && `${num(g.cooldown_bars)} bars cooldown`,
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'None';
}

/**
 * Backend mode: the server's risk-config templates (GET /risk/schema), the
 * presets backtests and the server's sizing start from. Shown as the server
 * normalised them; the full configs are in the details.
 */
export function ServerRiskTemplates() {
  const services = useServices();
  const res = useResource('risk:schema', (signal) => services.marketContext.riskSchema({ signal }));

  return (
    <section aria-labelledby="server-templates-title" className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="server-templates-title" className="text-md font-semibold text-fg">
          Server risk templates
        </h2>
        <p className="text-xs text-fg-3">The presets the backend uses for backtests and server sizing</p>
      </div>
      {res.status === 'loading' ? (
        <Loading label="Loading risk templates">
          <SkeletonRows rows={3} />
        </Loading>
      ) : res.status === 'error' || !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : (
        (() => {
          const schema = res.data;
          const names = [...ORDER.filter((n) => n in schema.templates), ...Object.keys(schema.templates).filter((n) => !ORDER.includes(n))];
          return (
            <div className="flex flex-col gap-4">
              <TableRegion label="Server risk templates" className="rounded-md border border-line">
                <thead>
                  <tr>
                    <Th>Template</Th>
                    <Th numeric>Risk per trade</Th>
                    <Th>Stop</Th>
                    <Th>Take profit</Th>
                    <Th>Guards</Th>
                    <Th numeric>Fees</Th>
                  </tr>
                </thead>
                <tbody>
                  {names.map((n) => {
                    const t = schema.templates[n] ?? {};
                    const sizing = obj(t.sizing);
                    const risk = num(sizing?.risk_pct);
                    const fee = num(t.fee_bps);
                    return (
                      <tr key={n}>
                        <Td className="font-medium">
                          {label(n)} {n === schema.defaultTemplate && <Badge tone="accent">Default</Badge>}
                        </Td>
                        <Td numeric>{risk === null ? MISSING : formatPct(risk)}</Td>
                        <Td className="whitespace-normal">{stopText(t.stop)}</Td>
                        <Td className="whitespace-normal">{targetText(t.take_profit)}</Td>
                        <Td className="whitespace-normal text-fg-2">{guardsText(t.guards)}</Td>
                        <Td numeric>{fee === null ? MISSING : `${fee} bps`}</Td>
                      </tr>
                    );
                  })}
                </tbody>
              </TableRegion>
              <details className="rounded-md border border-line px-3 py-2">
                <summary className="cursor-pointer text-sm font-medium text-fg">Full template configs</summary>
                <div className="flex flex-col gap-4 pt-3">
                  {names.map((n) => (
                    <div key={n}>
                      <h3 className="mb-1.5 text-sm font-semibold text-fg">{label(n)}</h3>
                      <JsonView value={schema.templates[n]} />
                    </div>
                  ))}
                </div>
              </details>
            </div>
          );
        })()
      )}
    </section>
  );
}
