import { ChevronLeft, ChevronRight, FlaskConical, GitCompare, Plus, Trash2, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { metricNumber, type BacktestSummary } from '@/domain/backtests';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatDateTime, formatNumber, formatPct } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { formatWindow, isActiveStatus, useStrategyNames } from './backtestFormat';
import { BacktestDisclaimer, ProgressBar, StatusBadge } from './backtestParts';
import { CompareDialog } from './CompareDialog';
import { NewBacktestForm } from './NewBacktestForm';

const PAGE_SIZE = 20;
/** POST /backtests/compare accepts 2–6 ids. */
const MAX_COMPARE = 6;

const signedTone = (v: number | null) => (v === null ? '' : v > 0 ? 'text-up' : v < 0 ? 'text-down' : '');

export function BacktestsPage() {
  usePageTitle('Backtests');
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const names = useStrategyNames();
  const [offset, setOffset] = useState(0);
  const list = useResource(`backtests:${offset}`, (signal) => services.backtests.list({ limit: PAGE_SIZE, offset }, { signal }));
  const [creating, setCreating] = useState(false);
  const [removing, setRemoving] = useState<BacktestSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);

  // Progress pushed on the user's WebSocket topic; a finished run is re-read for its headline metrics.
  const { setData, reload } = list;
  const loaded = useRef(false);
  loaded.current = list.data !== undefined;
  useEffect(
    () =>
      services.backtests.subscribe((event) => {
        if (!isActiveStatus(event.status)) reload();
        // Before the first load there is nothing to patch (setData would replace the loading state).
        else if (loaded.current)
          setData((prev) => ({
            items: (prev?.items ?? []).map((b) => (b.id === event.backtestId ? { ...b, status: event.status, progress: event.progress, error: event.error ?? b.error } : b)),
            total: prev?.total ?? 0,
          }));
      }),
    [services, setData, reload],
  );

  const onCreated = async (id: string) => {
    setCreating(false);
    notify('Backtest queued. Progress updates live.', 'success');
    if (offset !== 0) {
      setOffset(0);
      return;
    }
    try {
      const created = await services.backtests.get(id);
      setData((prev) => ({ items: [created, ...(prev?.items ?? []).filter((b) => b.id !== id)].slice(0, PAGE_SIZE), total: (prev?.total ?? 0) + 1 }));
    } catch {
      reload();
    }
  };

  const confirmRemove = async () => {
    if (!removing) return;
    const cancelling = isActiveStatus(removing.status);
    setBusy(true);
    try {
      await services.backtests.remove(removing.id);
      if (cancelling) {
        setData((prev) => ({ items: (prev?.items ?? []).map((b) => (b.id === removing.id ? { ...b, status: 'cancelled' as const } : b)), total: prev?.total ?? 0 }));
        notify('Backtest cancelled.', 'info');
      } else {
        setData((prev) => ({ items: (prev?.items ?? []).filter((b) => b.id !== removing.id), total: Math.max(0, (prev?.total ?? 1) - 1) }));
        setSelected((s) => s.filter((id) => id !== removing.id));
        notify('Backtest deleted.', 'info');
      }
      setRemoving(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  const toggleSelected = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length >= MAX_COMPARE ? s : [...s, id]));

  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const canCreate = names.res.status === 'success';

  return (
    <Page>
      <PageHeader
        title="Backtests"
        meta={<SourceTag kind="historical" />}
        description="Replay a strategy over historical candles from the backend, with fees and slippage, and review its metrics, equity curve and trades."
        actions={
          <>
            <Button icon={GitCompare} disabled={selected.length < 2} onClick={() => setComparing(true)}>
              Compare{selected.length > 0 ? ` (${selected.length})` : ''}
            </Button>
            <Button variant="primary" icon={Plus} disabled={!canCreate} onClick={() => setCreating(true)}>
              New backtest
            </Button>
          </>
        }
      />
      {names.res.status === 'error' && <ErrorState error={names.res.error} onRetry={names.res.reload} title="Could not load the strategy catalog" compact />}

      <Panel
        title="Your backtests"
        meta={list.data && <span>{formatNumber(total)} total</span>}
        actions={
          selected.length > 0 && (
            <Button size="sm" variant="ghost" icon={X} onClick={() => setSelected([])}>
              Clear selection
            </Button>
          )
        }
        flush
      >
        {list.status === 'loading' ? (
          <Loading label="Loading backtests">
            <SkeletonRows rows={5} className="p-4" />
          </Loading>
        ) : list.status === 'error' && !list.data ? (
          <ErrorState error={list.error} onRetry={list.reload} compact />
        ) : items.length === 0 ? (
          <EmptyState
            icon={FlaskConical}
            title="No backtests yet"
            description="Run a strategy over a historical window to see how it would have behaved."
            action={
              canCreate && (
                <Button size="sm" icon={Plus} onClick={() => setCreating(true)}>
                  New backtest
                </Button>
              )
            }
          />
        ) : (
          <>
            <TableRegion label="Backtests">
              <thead>
                <tr>
                  <Th className="w-10">
                    <span className="sr-only">Select to compare</span>
                  </Th>
                  <Th>Status</Th>
                  <Th>Strategy</Th>
                  <Th>Instrument</Th>
                  <Th>Window</Th>
                  <Th numeric>Return</Th>
                  <Th numeric>Max DD</Th>
                  <Th numeric>Trades</Th>
                  <Th numeric>Win rate</Th>
                  <Th>Created</Th>
                  <Th>
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </thead>
              <tbody>
                {items.map((b) => {
                  const ret = metricNumber(b.headline, 'total_return_pct');
                  const dd = metricNumber(b.headline, 'max_drawdown_pct');
                  const active = isActiveStatus(b.status);
                  const name = names.label(b.strategyKey);
                  const isSelected = selected.includes(b.id);
                  return (
                    <tr key={b.id} className={cn(isSelected && 'bg-selected')}>
                      <Td>
                        <input
                          type="checkbox"
                          className="size-4 cursor-pointer accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={`Compare ${name} on ${b.instrument.symbol}`}
                          checked={isSelected}
                          disabled={b.status !== 'completed' || (!isSelected && selected.length >= MAX_COMPARE)}
                          onChange={() => toggleSelected(b.id)}
                        />
                      </Td>
                      <Td>
                        <div className="flex min-w-24 flex-col gap-1">
                          <StatusBadge status={b.status} />
                          {active && <ProgressBar value={b.progress} label={`${name}: ${b.progress}% done`} />}
                        </div>
                      </Td>
                      <Td>
                        <Link to={`/backtests/${b.id}`} className="font-medium text-fg underline-offset-2 hover:text-accent hover:underline">
                          {name}
                        </Link>
                      </Td>
                      <Td>
                        {b.instrument.symbol} <span className="text-fg-3">· {b.timeframe}</span>
                      </Td>
                      <Td className="text-fg-2">{formatWindow(b.start, b.end, timeZone)}</Td>
                      <Td numeric className={signedTone(ret)}>
                        {formatPct(ret)}
                      </Td>
                      <Td numeric>{formatPct(dd)}</Td>
                      <Td numeric>{formatNumber(metricNumber(b.headline, 'trades'))}</Td>
                      <Td numeric>{formatPct(metricNumber(b.headline, 'win_rate_pct'), 1)}</Td>
                      <Td className="text-fg-2">{formatDateTime(b.createdAt, timeZone)}</Td>
                      <Td>
                        <IconButton
                          icon={active ? X : Trash2}
                          size="sm"
                          label={active ? `Cancel ${name}` : `Delete ${name}`}
                          tooltipSide="left"
                          onClick={() => setRemoving(b)}
                        />
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </TableRegion>
            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-sm text-fg-2">
                <span className="num">
                  {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {formatNumber(total)}
                </span>
                <div className="flex gap-1.5">
                  <Button size="sm" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                    Newer
                  </Button>
                  <Button size="sm" trailingIcon={ChevronRight} disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                    Older
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
        <div className="border-t border-line px-4 py-2.5">
          <BacktestDisclaimer />
          {selected.length > 0 && <p className="mt-1.5 text-xs text-fg-3">Select 2–{MAX_COMPARE} completed backtests to compare them.</p>}
        </div>
      </Panel>

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New backtest"
        description="The backtest is queued on the server and runs in the background. Each run counts toward your daily quota."
        size="lg"
      >
        <NewBacktestForm catalog={names.catalog} custom={names.custom} onCreated={onCreated} onCancel={() => setCreating(false)} />
      </Dialog>

      <CompareDialog ids={selected} open={comparing} onClose={() => setComparing(false)} label={names.label} />

      <ConfirmDialog
        open={removing !== null}
        title={removing && isActiveStatus(removing.status) ? 'Cancel backtest?' : 'Delete backtest?'}
        description={
          removing && isActiveStatus(removing.status)
            ? 'The run stops and nothing is stored. It stays in your list as cancelled.'
            : 'The backtest, its metrics and its trades are permanently deleted.'
        }
        confirmLabel={removing && isActiveStatus(removing.status) ? 'Cancel backtest' : 'Delete backtest'}
        onConfirm={confirmRemove}
        onCancel={() => setRemoving(null)}
        busy={busy}
      />
    </Page>
  );
}
