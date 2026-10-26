import { ArrowLeft, ChevronLeft, ChevronRight, Download, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Page, PageHeader, Panel, Stat } from '@/components/ui/Panel';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, Skeleton, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { METRIC_LABELS, metricNumber, type BacktestResult } from '@/domain/backtests';
import { SeriesChart, type SeriesLine } from '@/features/chart/SeriesChart';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatPct, formatR } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { backtestCurrency, formatAmount, formatMetric, formatWindow, isActiveStatus, useStrategyNames } from './backtestFormat';
import { BacktestDisclaimer, ProgressBar, StatusBadge } from './backtestParts';

const TRADES_PAGE = 50;
const signedTone = (v: number) => (v > 0 ? 'text-up' : v < 0 ? 'text-down' : '');

function downloadText(text: string, filename: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function TradesPanel({ backtest, currency }: { backtest: BacktestResult; currency: string }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [offset, setOffset] = useState(0);
  const [exporting, setExporting] = useState(false);
  const trades = useResource(`backtest-trades:${backtest.id}:${offset}`, (signal) => services.backtests.trades(backtest.id, { limit: TRADES_PAGE, offset }, { signal }));
  const precision = backtest.instrument.symbol.includes('JPY') ? 3 : 5;
  const price = (v: number) => formatNumber(v, v >= 100 ? 2 : precision);
  const total = trades.data?.total ?? 0;

  const exportCsv = async () => {
    setExporting(true);
    try {
      downloadText(await services.backtests.exportTradesCsv(backtest.id), `backtest-${backtest.id}-trades.csv`);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setExporting(false);
    }
  };

  return (
    <Panel
      title="Trades"
      meta={trades.data && <span>{formatNumber(total)} closed</span>}
      actions={
        <Button size="sm" icon={Download} loading={exporting} disabled={total === 0} onClick={exportCsv}>
          Export CSV
        </Button>
      }
      flush
    >
      {trades.status === 'loading' ? (
        <Loading label="Loading trades">
          <SkeletonRows rows={5} className="p-4" />
        </Loading>
      ) : trades.status === 'error' && !trades.data ? (
        <ErrorState error={trades.error} onRetry={trades.reload} compact />
      ) : !trades.data?.items.length ? (
        <EmptyState title="No trades" description="The strategy did not open a position in this window." compact />
      ) : (
        <>
          <TableRegion label="Backtest trades">
            <thead>
              <tr>
                <Th numeric>#</Th>
                <Th>Side</Th>
                <Th>Entry</Th>
                <Th numeric>Entry price</Th>
                <Th>Exit</Th>
                <Th numeric>Exit price</Th>
                <Th numeric>Qty</Th>
                <Th numeric>Net P&amp;L</Th>
                <Th numeric>Return</Th>
                <Th numeric>Bars</Th>
                <Th>Exit reason</Th>
                <Th numeric>R</Th>
              </tr>
            </thead>
            <tbody>
              {trades.data.items.map((t) => (
                <tr key={t.number}>
                  <Td numeric>{t.number}</Td>
                  <Td className="capitalize">{t.side}</Td>
                  <Td className="text-fg-2">{formatDateTime(t.entryTime, timeZone)}</Td>
                  <Td numeric>{price(t.entryPrice)}</Td>
                  <Td className="text-fg-2">{formatDateTime(t.exitTime, timeZone)}</Td>
                  <Td numeric>{price(t.exitPrice)}</Td>
                  <Td numeric>{formatNumber(t.quantity, 4)}</Td>
                  <Td numeric className={signedTone(t.netPnl)}>
                    {formatAmount(t.netPnl, currency)}
                  </Td>
                  <Td numeric className={signedTone(t.returnPct)}>
                    {formatPct(t.returnPct)}
                  </Td>
                  <Td numeric>{formatNumber(t.barsHeld)}</Td>
                  <Td className="text-fg-2">{t.exitReason.replace(/_/g, ' ')}</Td>
                  <Td numeric>{formatR(t.rMultiple)}</Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
          {total > TRADES_PAGE && (
            <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-sm text-fg-2">
              <span className="num">
                {offset + 1}–{Math.min(offset + TRADES_PAGE, total)} of {formatNumber(total)}
              </span>
              <div className="flex gap-1.5">
                <Button size="sm" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - TRADES_PAGE))}>
                  Previous
                </Button>
                <Button size="sm" trailingIcon={ChevronRight} disabled={offset + TRADES_PAGE >= total} onClick={() => setOffset((o) => o + TRADES_PAGE)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}

function Results({ backtest }: { backtest: BacktestResult }) {
  const currency = backtestCurrency(backtest.config, backtest.instrument.symbol);
  const lines = useMemo<SeriesLine[]>(
    () => [
      { name: 'Equity', points: backtest.equity, color: 'accent', pane: 0 },
      { name: 'Drawdown %', points: backtest.drawdown, color: 'down', pane: 1 },
    ],
    [backtest.equity, backtest.drawdown],
  );
  const metrics = METRIC_LABELS.filter((m) => metricNumber(backtest.metrics, m.key) !== null);

  return (
    <>
      <Panel title="Metrics" meta={<span>Amounts in {currency}</span>}>
        {metrics.length === 0 ? (
          <p className="text-sm text-fg-2">The server returned no metrics for this backtest.</p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
            {metrics.map((m) => (
              <Stat
                key={m.key}
                label={<span title={m.hint}>{m.label}</span>}
                value={<span className="num">{formatMetric(m.kind, metricNumber(backtest.metrics, m.key), currency)}</span>}
              />
            ))}
          </dl>
        )}
      </Panel>

      <Panel title="Equity and drawdown" meta={<span>Markers show entries and exits</span>} flush>
        {backtest.equity.length === 0 ? (
          <EmptyState title="No equity curve" description="The server returned no equity points for this backtest." compact />
        ) : (
          <SeriesChart
            label={`Equity curve and drawdown of the backtest, ${backtest.equity.length} points, with trade markers`}
            lines={lines}
            markers={backtest.markers}
            height={420}
            className="p-2"
          />
        )}
      </Panel>

      <TradesPanel backtest={backtest} currency={currency} />
    </>
  );
}

export function BacktestDetailPage() {
  const { backtestId = '' } = useParams();
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const navigate = useNavigate();
  const names = useStrategyNames();
  const res = useResource(`backtest:${backtestId}`, (signal) => services.backtests.get(backtestId, { signal }));
  const [removing, setRemoving] = useState(false);
  const [busy, setBusy] = useState(false);
  const backtest = res.data;
  const title = backtest ? names.label(backtest.strategyKey) : 'Backtest';
  usePageTitle(title);

  const { setData, reload } = res;
  const loaded = useRef(false);
  loaded.current = backtest !== undefined;
  useEffect(
    () =>
      services.backtests.subscribe((event) => {
        if (event.backtestId !== backtestId) return;
        if (!isActiveStatus(event.status)) reload();
        else if (loaded.current) setData((prev) => ({ ...(prev as BacktestResult), status: event.status, progress: event.progress }));
      }),
    [services, backtestId, setData, reload],
  );

  const active = backtest ? isActiveStatus(backtest.status) : false;

  const confirmRemove = async () => {
    if (!backtest) return;
    setBusy(true);
    try {
      await services.backtests.remove(backtest.id);
      setRemoving(false);
      if (active) {
        notify('Backtest cancelled.', 'info');
        reload();
      } else {
        notify('Backtest deleted.', 'info');
        navigate('/backtests');
      }
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  const back = (
    <Link to="/backtests" className={buttonClasses({ variant: 'ghost', size: 'sm', className: 'self-start' })}>
      <ArrowLeft aria-hidden className="size-4" />
      All backtests
    </Link>
  );

  if (res.status === 'loading')
    return (
      <Page>
        {back}
        <Loading label="Loading backtest">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-4 h-80 w-full" />
        </Loading>
      </Page>
    );

  if (!backtest)
    return (
      <Page>
        {back}
        <ErrorState error={res.error} onRetry={res.reload} title="Could not load this backtest" />
      </Page>
    );

  const params = Object.entries(backtest.params);

  return (
    <Page>
      {back}
      <PageHeader
        title={title}
        meta={
          <>
            <StatusBadge status={backtest.status} />
            <SourceTag kind="historical" />
          </>
        }
        description={
          <>
            {backtest.instrument.symbol} · {backtest.timeframe} · {formatWindow(backtest.start, backtest.end, timeZone)}
            {backtest.bars !== null && <> · {formatNumber(backtest.bars)} bars</>}
          </>
        }
        actions={
          <Button variant={active ? 'secondary' : 'danger'} icon={active ? X : Trash2} onClick={() => setRemoving(true)}>
            {active ? 'Cancel backtest' : 'Delete'}
          </Button>
        }
      />

      {params.length > 0 && (
        <p className="-mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-3">
          {params.map(([k, v]) => (
            <span key={k}>
              {k} = <span className="num text-fg-2">{String(v)}</span>
            </span>
          ))}
        </p>
      )}

      {res.status === 'error' && <ErrorState error={res.error} onRetry={res.reload} title="Could not refresh this backtest" compact />}

      {active && (
        <Panel title={backtest.status === 'queued' ? 'Waiting for a worker' : 'Running'}>
          <div className="flex flex-col gap-2">
            <ProgressBar value={backtest.progress} label={`Backtest progress: ${backtest.progress}%`} />
            <p className="text-sm text-fg-2" aria-live="polite">
              {backtest.progress}% — {backtest.progress >= 80 ? 'saving results' : backtest.progress >= 30 ? 'computing' : backtest.progress >= 5 ? 'loading candles' : 'queued'}.
              This page updates when it finishes.
            </p>
          </div>
        </Panel>
      )}

      {backtest.status === 'failed' && (
        <Panel title="Backtest failed">
          <p role="alert" className="text-sm text-danger">
            {backtest.error ?? 'The server did not give a reason.'}
          </p>
        </Panel>
      )}

      {backtest.status === 'cancelled' && (
        <Panel title="Cancelled">
          <p className="text-sm text-fg-2">This backtest was cancelled before it finished. Nothing was stored.</p>
        </Panel>
      )}

      {backtest.status === 'completed' && <Results backtest={backtest} />}

      <BacktestDisclaimer />

      <ConfirmDialog
        open={removing}
        title={active ? 'Cancel backtest?' : 'Delete backtest?'}
        description={active ? 'The run stops and nothing is stored.' : 'The backtest, its metrics and its trades are permanently deleted.'}
        confirmLabel={active ? 'Cancel backtest' : 'Delete backtest'}
        onConfirm={confirmRemove}
        onCancel={() => setRemoving(false)}
        busy={busy}
      />
    </Page>
  );
}
