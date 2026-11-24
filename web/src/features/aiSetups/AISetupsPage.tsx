import { ChevronLeft, ChevronRight, Radio } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { SETUP_STATE_LABELS, type AISetup } from '@/domain/aiSetups';
import { formatAmount } from '@/features/backtests/backtestFormat';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatRelative } from '@/lib/format';
import { FollowsPanel } from './FollowsPanel';
import { SetupDialog } from './SetupDialog';
import { formatR, formatSetupPrice, instrumentLabel, STATE_TONE } from './setupFormat';

const TRADES_PAGE = 20;

/**
 * AI setups (backend: B7–B11, docs/ai-contract.md). There is no list of every
 * setup: a user sees the setups the server told them about (their `ai_setup`
 * notifications) and, while this page is open, live state changes on the
 * instruments they follow.
 */
export function AISetupsPage() {
  usePageTitle('AI setups');
  const services = useServices();
  const { timeZone } = usePreferences();
  const instruments = useResource('instruments:all', (signal) => services.instruments.list({ signal }));
  const follows = useResource('ai:follows', (signal) => services.aiSetups.follows({ signal }));
  const recent = useResource('ai:recent', (signal) => services.aiSetups.recent({ signal }));
  const [live, setLive] = useState<Map<string, AISetup>>(() => new Map());
  const [open, setOpen] = useState<AISetup | null>(null);
  const [tradesOffset, setTradesOffset] = useState(0);
  // P&L is in the account currency of the server risk profile (realized R × money at risk).
  const risk = useResource('risk:profile', (signal) => services.riskProfile.get({ signal }));
  const trades = useResource(`ai:trades:${tradesOffset}`, (signal) => services.aiSetups.trades({ limit: TRADES_PAGE, offset: tradesOffset }, { signal }));

  // Live state changes for every followed instrument (the server sends no snapshot).
  const followedIds = useMemo(() => [...new Set((follows.data ?? []).map((f) => f.instrumentId))].sort().join(','), [follows.data]);
  const instrumentList = instruments.data;
  useEffect(() => {
    if (!followedIds || !instrumentList) return;
    const offs = followedIds.split(',').map((id) => {
      const inst = instrumentList.find((i) => i.id === id);
      return services.aiSetups.subscribe({ id, symbol: inst?.symbol ?? 'Unknown instrument', pricePrecision: inst?.pricePrecision ?? null }, (ev) =>
        setLive((prev) => new Map(prev).set(ev.setup.setupId, ev.setup)),
      );
    });
    return () => offs.forEach((off) => off());
  }, [followedIds, instrumentList, services]);

  const setups = useMemo(() => {
    const byId = new Map<string, AISetup>();
    for (const s of recent.data ?? []) byId.set(s.setupId, s);
    for (const s of live.values()) {
      const cur = byId.get(s.setupId);
      // A live frame carries the ai-service setup; keep the instrument/profile known from the notification.
      byId.set(s.setupId, cur && cur.updatedAt > s.updatedAt ? cur : { ...s, instrument: cur?.instrument ?? s.instrument, profile: s.profile ?? cur?.profile ?? null });
    }
    return [...byId.values()].sort((a, b) => b.updatedAt - a.updatedAt);
  }, [recent.data, live]);

  return (
    <Page>
      <PageHeader
        title="AI setups"
        meta={<SourceTag kind="live" />}
        description="Trade setups (entry, stop, target) proposed by the AI engine's rules. Version 1 has no trained model: probability, expected value and grade are not provided. Analysis only: the platform never places trades."
      />

      <FollowsPanel follows={follows} instruments={instruments} />

      <Panel
        title="Setups you were told about"
        meta={
          <span className="inline-flex items-center gap-1.5">
            {followedIds ? (
              <>
                <Radio aria-hidden className="size-3.5 text-up" /> Live for followed instruments
              </>
            ) : (
              'Follow an instrument to receive setups'
            )}
          </span>
        }
        flush
      >
        {recent.status === 'loading' ? (
          <Loading label="Loading setups">
            <SkeletonRows rows={3} className="p-4" />
          </Loading>
        ) : recent.status === 'error' && !recent.data ? (
          <ErrorState error={recent.error} onRetry={recent.reload} compact />
        ) : setups.length === 0 ? (
          <EmptyState
            title="No setups yet"
            description="When the AI engine arms a setup on an instrument you follow, it appears here and in your notifications. Outcomes are sent for setups you record as taken."
          />
        ) : (
          <TableRegion label="AI setups">
            <thead>
              <tr>
                <Th>Instrument</Th>
                <Th>Side</Th>
                <Th>State</Th>
                <Th numeric>Entry</Th>
                <Th numeric>Stop</Th>
                <Th numeric>Target</Th>
                <Th numeric>R:R</Th>
                <Th>Valid until</Th>
                <Th>Updated</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {setups.map((s) => {
                const p = s.instrument?.pricePrecision;
                return (
                  <tr key={s.setupId}>
                    <Td>
                      {s.instrument?.symbol ?? 'Unknown instrument'}
                      {s.profile && <span className="ml-1.5 text-xs text-fg-3">{s.profile}</span>}
                    </Td>
                    <Td>
                      <Badge tone={s.direction === 'buy' ? 'up' : 'down'}>{s.direction === 'buy' ? 'Buy' : 'Sell'}</Badge>
                    </Td>
                    <Td>
                      <Badge tone={STATE_TONE[s.state]}>{SETUP_STATE_LABELS[s.state]}</Badge>
                      {s.realizedR !== null && <span className="num ml-1.5 text-xs">{formatR(s.realizedR)}</span>}
                      {s.late && <span className="ml-1.5 text-xs text-fg-3">(late notice)</span>}
                    </Td>
                    <Td numeric>{formatSetupPrice(s.entry, p)}</Td>
                    <Td numeric>{formatSetupPrice(s.sl, p)}</Td>
                    <Td numeric>{formatSetupPrice(s.tp, p)}</Td>
                    <Td numeric>{s.rMultiple === null ? '—' : formatNumber(s.rMultiple, 2)}</Td>
                    <Td className="text-fg-2">{s.validUntil ? formatDateTime(s.validUntil, timeZone) : '—'}</Td>
                    <Td className="text-fg-2" title={formatDateTime(s.updatedAt, timeZone)}>
                      {formatRelative(s.updatedAt)}
                    </Td>
                    <Td>
                      <Button size="sm" onClick={() => setOpen(s)}>
                        Details
                      </Button>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </TableRegion>
        )}
      </Panel>

      <Panel title="Setups you took" meta={trades.data && <span>{trades.data.total} total</span>} flush>
        {trades.status === 'loading' ? (
          <Loading label="Loading your taken setups">
            <SkeletonRows rows={2} className="p-4" />
          </Loading>
        ) : trades.status === 'error' && !trades.data ? (
          <ErrorState error={trades.error} onRetry={trades.reload} compact />
        ) : !trades.data?.items.length ? (
          <EmptyState compact title="Nothing recorded" description="Open a setup and choose “I took this trade” to track its outcome here." />
        ) : (
          <>
            <TableRegion label="Setups you took">
              <thead>
                <tr>
                  <Th>Instrument</Th>
                  <Th>Side</Th>
                  <Th>State</Th>
                  <Th numeric>Entry</Th>
                  <Th numeric>Stop</Th>
                  <Th numeric>Target</Th>
                  <Th numeric>Lots</Th>
                  <Th numeric>Your entry</Th>
                  <Th numeric>Result</Th>
                  <Th numeric>P&amp;L</Th>
                  <Th>Taken</Th>
                </tr>
              </thead>
              <tbody>
                {trades.data.items.map((t) => {
                  const p = instruments.data?.find((i) => i.id === t.instrumentId)?.pricePrecision;
                  return (
                    <tr key={t.setupId}>
                      <Td>{instrumentLabel(t.instrumentId, instruments.data)}</Td>
                      <Td>
                        <Badge tone={t.direction === 'buy' ? 'up' : 'down'}>{t.direction === 'buy' ? 'Buy' : 'Sell'}</Badge>
                      </Td>
                      <Td>
                        <Badge tone={STATE_TONE[t.state]}>{SETUP_STATE_LABELS[t.state]}</Badge>
                        {t.closeReason && <span className="ml-1.5 text-xs text-fg-3">{t.closeReason}</span>}
                      </Td>
                      <Td numeric>{formatSetupPrice(t.entry, p)}</Td>
                      <Td numeric>{formatSetupPrice(t.sl, p)}</Td>
                      <Td numeric>{formatSetupPrice(t.tp, p)}</Td>
                      <Td numeric>{t.lots === null ? '—' : formatNumber(t.lots, 2)}</Td>
                      <Td numeric>{formatSetupPrice(t.entryPrice, p)}</Td>
                      <Td numeric>{formatR(t.realizedR)}</Td>
                      <Td numeric>{t.pnl === null ? '—' : risk.data ? formatAmount(t.pnl, risk.data.currency) : formatNumber(t.pnl, 2)}</Td>
                      <Td className="text-fg-2">{formatDateTime(t.takenAt, timeZone)}</Td>
                    </tr>
                  );
                })}
              </tbody>
            </TableRegion>
            {trades.data.total > TRADES_PAGE && (
              <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-2">
                <Button size="sm" icon={ChevronLeft} disabled={tradesOffset === 0} onClick={() => setTradesOffset((o) => Math.max(0, o - TRADES_PAGE))}>
                  Previous
                </Button>
                <Button size="sm" trailingIcon={ChevronRight} disabled={tradesOffset + TRADES_PAGE >= trades.data.total} onClick={() => setTradesOffset((o) => o + TRADES_PAGE)}>
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </Panel>

      {open && <SetupDialog key={open.setupId} setup={open} onClose={() => setOpen(null)} onTakenChange={trades.reload} />}
    </Page>
  );
}
