import { ChevronLeft, ChevronRight, History } from 'lucide-react';
import { Fragment, useMemo, useState } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { CALENDAR_CURRENCIES, IMPACT_LABELS, type CalendarEvent, type EventImpact } from '@/domain/calendar';
import { useNow } from '@/hooks/useEnvironment';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatClock, formatDate, formatDateTime, MISSING, timeZoneLabel } from '@/lib/format';

const DAY = 86_400_000;
const IMPACT_TONE: Record<EventImpact, BadgeTone> = { high: 'danger', medium: 'warning', low: 'neutral', holiday: 'info' };
/** The currencies of the instruments the platform covers, selected by default. */
const DEFAULT_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY'];

/** "in 5 min", "in 3 h 20 min", "in 2 days". */
function until(ms: number): string {
  const min = Math.max(1, Math.round(ms / 60_000));
  if (min < 60) return `in ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `in ${h} h${min % 60 ? ` ${min % 60} min` : ''}`;
  return `in ${Math.round(h / 24)} days`;
}

/** Monday 00:00 UTC of the week containing `t`. */
function weekStart(t: number): number {
  const d = new Date(t);
  const day = (d.getUTCDay() + 6) % 7;
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - day);
}

function HistoryDialog({ event, onClose }: { event: CalendarEvent; onClose: () => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource(`calendar:history:${event.key}`, (signal) => services.calendar.history(event.key, { signal }));
  return (
    <Dialog
      open
      onClose={onClose}
      title={`${event.currency} · ${event.title}`}
      description="Every version the platform stored, oldest first: what was known, and when. The AI engine only sees the version known at the time it evaluates."
      footer={<Button onClick={onClose}>Close</Button>}
    >
      {res.status === 'loading' ? (
        <Loading label="Loading versions">
          <SkeletonRows rows={3} />
        </Loading>
      ) : res.status === 'error' ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : (
        <TableRegion label="Event versions">
          <thead>
            <tr>
              <Th>Known since</Th>
              <Th numeric>Actual</Th>
              <Th numeric>Forecast</Th>
              <Th numeric>Previous</Th>
              <Th>Scheduled</Th>
            </tr>
          </thead>
          <tbody>
            {(res.data ?? []).map((v) => (
              <tr key={v.fetchedAt}>
                <Td>{formatDateTime(v.fetchedAt, timeZone)}</Td>
                <Td numeric>{v.actual ?? MISSING}</Td>
                <Td numeric>{v.forecast ?? MISSING}</Td>
                <Td numeric>{v.previous ?? MISSING}</Td>
                <Td className="text-fg-2">{v.scheduledAt ? formatDateTime(v.scheduledAt, timeZone) : (v.timeLabel ?? v.scheduledDate)}</Td>
              </tr>
            ))}
          </tbody>
        </TableRegion>
      )}
    </Dialog>
  );
}

/** Economic calendar (backend B6, docs/economic-calendar.md). */
export function CalendarPage() {
  usePageTitle('Economic calendar');
  const services = useServices();
  const { timeZone } = usePreferences();
  const now = useNow(60_000);
  const [week, setWeek] = useState(() => weekStart(Date.now()));
  const [currencies, setCurrencies] = useState<string[]>(DEFAULT_CURRENCIES);
  const [minImpact, setMinImpact] = useState<EventImpact>('medium');
  const [history, setHistory] = useState<CalendarEvent | null>(null);
  const key = `calendar:${week}:${currencies.join(',')}:${minImpact}`;
  const res = useResource(key, (signal) => services.calendar.events({ start: week, end: week + 7 * DAY, currencies, minImpact }, { signal }));

  const days = useMemo(() => {
    const groups = new Map<string, CalendarEvent[]>();
    for (const e of [...(res.data?.events ?? [])].sort((a, b) => (a.scheduledAt ?? Date.parse(a.scheduledDate)) - (b.scheduledAt ?? Date.parse(b.scheduledDate)))) {
      const list = groups.get(e.scheduledDate) ?? [];
      list.push(e);
      groups.set(e.scheduledDate, list);
    }
    return [...groups.entries()];
  }, [res.data]);
  const nextHigh = (res.data?.events ?? []).filter((e) => e.impact === 'high' && e.scheduledAt !== null && e.scheduledAt > now).sort((a, b) => (a.scheduledAt ?? 0) - (b.scheduledAt ?? 0))[0];

  const toggle = (c: string) => setCurrencies((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));

  return (
    <Page>
      <PageHeader
        title="Economic calendar"
        meta={<SourceTag kind="live" label="Backend calendar" detail="Scheduled macro events stored by the backend (ForexFactory), with every revision kept." />}
        description="Scheduled macro events by currency and impact. The AI engine proposes no setup within 30 minutes of a high-impact event."
      />

      {nextHigh?.scheduledAt && (
        <p role="status" className="rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-fg">
          Next high-impact event: <strong className="font-medium">{nextHigh.currency} · {nextHigh.title}</strong> at {formatDateTime(nextHigh.scheduledAt, timeZone)} ({until(nextHigh.scheduledAt - now)}).
        </p>
      )}

      <Panel
        title="Events"
        meta={res.data && <span>As of {formatDateTime(res.data.asOf, timeZone)} · times in {timeZoneLabel(timeZone)}</span>}
        actions={
          <div className="flex items-center gap-1">
            <IconButton icon={ChevronLeft} size="sm" label="Previous week" onClick={() => setWeek((w) => w - 7 * DAY)} />
            <Button size="sm" variant="ghost" onClick={() => setWeek(weekStart(Date.now()))}>
              This week
            </Button>
            <IconButton icon={ChevronRight} size="sm" label="Next week" onClick={() => setWeek((w) => w + 7 * DAY)} tooltipSide="left" />
          </div>
        }
        flush
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line px-4 py-3">
          <p className="text-sm font-medium text-fg">
            {formatDate(week, 'UTC')} – {formatDate(week + 6 * DAY, 'UTC')}
          </p>
          <fieldset className="flex flex-wrap items-center gap-1.5">
            <legend className="sr-only">Currencies</legend>
            {CALENDAR_CURRENCIES.map((c) => {
              const on = currencies.includes(c);
              return (
                <button
                  key={c}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(c)}
                  className={cn(
                    'h-7 rounded-md border px-2 text-xs font-medium transition-colors',
                    on ? 'border-accent bg-accent-soft text-accent' : 'border-line text-fg-2 hover:bg-hover hover:text-fg',
                  )}
                >
                  {c}
                </button>
              );
            })}
          </fieldset>
          <SegmentedControl
            label="Minimum impact"
            value={minImpact}
            onChange={setMinImpact}
            options={[
              { value: 'low', label: 'All' },
              { value: 'medium', label: 'Medium+' },
              { value: 'high', label: 'High' },
            ]}
          />
        </div>

        {currencies.length === 0 ? (
          <EmptyState compact title="No currency selected" description="Select at least one currency to see its events." />
        ) : res.status === 'loading' ? (
          <Loading label="Loading events">
            <SkeletonRows rows={6} className="p-4" />
          </Loading>
        ) : res.status === 'error' && !res.data ? (
          <ErrorState error={res.error} onRetry={res.reload} compact />
        ) : days.length === 0 ? (
          <EmptyState title="No events" description="No scheduled event matches these filters this week." />
        ) : (
          <TableRegion label="Economic events">
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>Currency</Th>
                <Th>Impact</Th>
                <Th>Event</Th>
                <Th numeric>Actual</Th>
                <Th numeric>Forecast</Th>
                <Th numeric>Previous</Th>
                <Th>
                  <span className="sr-only">History</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {days.map(([day, events]) => (
                <Fragment key={day}>
                  <tr>
                    <th scope="colgroup" colSpan={8} className="bg-inset px-3 py-1.5 text-left text-xs font-medium text-fg-2">
                      {formatDate(Date.parse(`${day}T12:00:00Z`), 'UTC')}
                    </th>
                  </tr>
                  {events.map((e) => {
                    const past = e.scheduledAt !== null && e.scheduledAt < now;
                    return (
                      <tr key={e.key} className={cn(past && 'text-fg-2')}>
                        <Td className="num">{e.scheduledAt ? formatClock(e.scheduledAt, timeZone, false) : (e.timeLabel ?? 'All day')}</Td>
                        <Td>{e.currency}</Td>
                        <Td>
                          <Badge tone={IMPACT_TONE[e.impact]}>{IMPACT_LABELS[e.impact]}</Badge>
                        </Td>
                        <Td className="whitespace-normal">{e.title}</Td>
                        <Td numeric className="font-medium">
                          {e.actual ?? MISSING}
                        </Td>
                        <Td numeric>{e.forecast ?? MISSING}</Td>
                        <Td numeric>{e.previous ?? MISSING}</Td>
                        <Td>
                          <IconButton icon={History} size="sm" label={`Revisions of ${e.currency} ${e.title}`} onClick={() => setHistory(e)} tooltipSide="left" />
                        </Td>
                      </tr>
                    );
                  })}
                </Fragment>
              ))}
            </tbody>
          </TableRegion>
        )}
      </Panel>

      {history && <HistoryDialog event={history} onClose={() => setHistory(null)} />}
    </Page>
  );
}
