import { RotateCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { JsonView } from '@/components/ui/JsonView';
import { Panel, Stat } from '@/components/ui/Panel';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { JsonObject } from '@/domain/admin';
import { useResource, type Resource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, MISSING } from '@/lib/format';
import { formatDuration, list, num, rec, statusTone, sumValues, text } from './overviewData';

function Block({ res, label, children }: { res: Resource<JsonObject>; label: string; children: (data: JsonObject) => ReactNode }) {
  if (res.status === 'loading')
    return (
      <Loading label={`Loading ${label}`}>
        <SkeletonRows rows={3} />
      </Loading>
    );
  if (res.status === 'error' && !res.data) return <ErrorState error={res.error} onRetry={res.reload} compact title={`Could not load ${label}`} />;
  return res.data ? <>{children(res.data)}</> : null;
}

function RawJson({ data }: { data: JsonObject }) {
  return (
    <details className="mt-4 rounded-md border border-line p-3">
      <summary className="cursor-pointer text-sm font-medium text-fg-2">Full response</summary>
      <JsonView value={data} className="mt-3" />
    </details>
  );
}

const iso = (v: unknown) => (typeof v === 'string' ? Date.parse(v) : NaN);

/** Admin › System: readiness, the system status report, the WebSocket hub, rate limiting and notification delivery. */
export function AdminOverviewPage() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const ready = useResource('admin:ready', (signal) => services.admin.readiness({ signal }));
  const status = useResource('admin:status', (signal) => services.admin.systemStatus({ signal }));
  const realtime = useResource('admin:realtime', (signal) => services.admin.realtimeStats({ signal }));
  const limits = useResource('admin:limits', (signal) => services.admin.rateLimitStats({ signal }));
  const notif = useResource('admin:notif', (signal) => services.admin.notificationStats({ signal }));
  const refreshAll = () => [ready, status, realtime, limits, notif].forEach((r) => r.reload());
  const when = (v: unknown) => {
    const t = iso(v);
    return Number.isFinite(t) ? formatDateTime(t, timeZone) : MISSING;
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-end">
        <Button size="sm" icon={RotateCw} onClick={refreshAll}>
          Refresh all
        </Button>
      </div>

      <Panel title="Readiness" meta={<span>/health/ready: the database and Redis</span>}>
        <Block res={ready} label="readiness">
          {(d) => (
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={statusTone(d.status)}>{text(d.status)}</Badge>
              {Object.entries(rec(d.checks) ?? {}).map(([k, v]) => (
                <Badge key={k} tone={statusTone(v)}>
                  {k}: {text(v)}
                </Badge>
              ))}
              {d.data !== undefined && <span className="text-xs text-fg-3">Market data: {text(d.data)}</span>}
            </div>
          )}
        </Block>
      </Panel>

      <Panel title="System status" meta={status.data && <span>As of {when(status.data.time)}</span>}>
        <Block res={status} label="the system status">
          {(d) => {
            const db = rec(d.database);
            const conns = rec(db?.connections);
            const redis = rec(d.redis);
            const celery = rec(d.celery);
            const workers = list(celery?.workers);
            const tasks = Object.entries(rec(celery?.tasks) ?? {});
            const market = list(d.market_data);
            const quality = list(d.data_quality);
            return (
              <div className="flex flex-col gap-5">
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                  <Stat label="Version" value={text(d.version)} hint={text(d.environment)} />
                  <Stat label="Uptime" value={formatDuration(num(d.uptime_seconds))} />
                  <Stat label="Database" value={num(db?.size_mb) === null ? MISSING : `${formatNumber(num(db?.size_mb), 1)} MB`} hint={`Migration ${text(db?.migration)}`} />
                  <Stat label="DB connections" value={`${text(conns?.active)} active`} hint={`${text(conns?.idle)} idle`} />
                  <Stat label="Redis" value={text(redis?.used_memory)} hint={`${text(redis?.keys)} keys`} />
                  <Stat label="Celery" value={`${workers.length} worker${workers.length === 1 ? '' : 's'}`} hint={`${sumValues(celery?.queues) ?? MISSING} queued`} />
                </dl>

                {workers.length === 0 && <p className="text-sm text-warning">No Celery worker reported in. Signals, alerts, backtests and notifications are not processed.</p>}

                {tasks.length > 0 && (
                  <TableRegion label="Scheduled tasks">
                    <thead>
                      <tr>
                        <Th>Task</Th>
                        <Th>Last success</Th>
                        <Th numeric>Seconds ago</Th>
                        <Th>Last failure</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {tasks.map(([name, raw]) => {
                        const t = rec(raw);
                        return (
                          <tr key={name}>
                            <Td className="font-mono text-xs">{name}</Td>
                            <Td>{when(t?.last_ok)}</Td>
                            <Td numeric>{num(t?.seconds_ago) === null ? MISSING : formatNumber(num(t?.seconds_ago))}</Td>
                            <Td className={t?.last_failure ? 'text-danger' : 'text-fg-3'}>{t?.last_failure ? text(t.last_failure) : MISSING}</Td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </TableRegion>
                )}

                {market.length > 0 && (
                  <TableRegion label="Market data freshness">
                    <thead>
                      <tr>
                        <Th>Instrument</Th>
                        <Th>Source</Th>
                        <Th>Last candle</Th>
                        <Th numeric>Lag</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {market.map((m, i) => (
                        <tr key={`${text(m.symbol)}-${i}`}>
                          <Td>{text(m.symbol)}</Td>
                          <Td>{text(m.source)}</Td>
                          <Td>{when(m.last_candle)}</Td>
                          <Td numeric>{formatDuration(num(m.lag_seconds))}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </TableRegion>
                )}

                {quality.length > 0 && (
                  <TableRegion label="Data quality">
                    <thead>
                      <tr>
                        <Th>Instrument</Th>
                        <Th>Timeframe</Th>
                        <Th>Status</Th>
                        <Th>Failed checks</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {quality.map((q, i) => {
                        const failed = list(q.checks ?? q.failed_checks).filter((c) => c.ok === false);
                        return (
                          <tr key={`${text(q.instrument)}-${i}`}>
                            <Td>{text(q.instrument)}</Td>
                            <Td>{text(q.timeframe)}</Td>
                            <Td>
                              <Badge tone={statusTone(q.status)}>{text(q.status)}</Badge>
                            </Td>
                            <Td className="whitespace-normal text-xs text-fg-2">{failed.length ? failed.map((c) => `${text(c.name)}: ${text(c.detail)}`).join('; ') : MISSING}</Td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </TableRegion>
                )}
                <RawJson data={d} />
              </div>
            );
          }}
        </Block>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Realtime hub" meta={<span>This API process</span>}>
          <Block res={realtime} label="the hub statistics">
            {(d) => (
              <>
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Stat label="Clients" value={text(d.clients)} />
                  <Stat label="Topics" value={text(d.topics)} />
                  <Stat label="Subscriptions" value={text(d.subscriptions)} />
                  <Stat label="Delivered" value={num(d.messages_delivered) === null ? MISSING : formatNumber(num(d.messages_delivered))} />
                  <Stat label="Dropped clients" value={text(d.clients_dropped)} />
                  <Stat label="Queued" value={text(d.queued_messages)} />
                </dl>
                <RawJson data={d} />
              </>
            )}
          </Block>
        </Panel>

        <Panel title="Rate limiting" meta={limits.data && <span>Last {text(limits.data.window_minutes)} min</span>}>
          <Block res={limits} label="the rate-limit statistics">
            {(d) => {
              const rejected = rec(d.rejected);
              const failOpen = rec(d.fail_open);
              return (
                <>
                  <dl className="grid grid-cols-2 gap-4">
                    <Stat label="Rejected (429)" value={text(rejected?.total)} />
                    <Stat label="Let through while Redis was down" value={text(failOpen?.process_last_hour)} hint="This API process, last hour" />
                  </dl>
                  {list(rejected?.by_tier_and_group).length > 0 && (
                    <TableRegion label="Rejections by tier and route group" className="mt-4">
                      <thead>
                        <tr>
                          <Th>Tier</Th>
                          <Th>Route group</Th>
                          <Th numeric>Count</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {list(rejected?.by_tier_and_group).map((r, i) => (
                          <tr key={i}>
                            <Td>{text(r.tier)}</Td>
                            <Td>{text(r.group)}</Td>
                            <Td numeric>{text(r.count)}</Td>
                          </tr>
                        ))}
                      </tbody>
                    </TableRegion>
                  )}
                  <RawJson data={d} />
                </>
              );
            }}
          </Block>
        </Panel>
      </div>

      <Panel title="Notification delivery" meta={notif.data && <span>Since {when(notif.data.since)}</span>}>
        <Block res={notif} label="the delivery statistics">
          {(d) => {
            const channels = Object.entries(rec(d.channels) ?? {});
            return (
              <>
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Stat label="Notifications" value={text(d.notifications)} />
                  <Stat label="Queue length" value={text(d.queue_length)} />
                </dl>
                {channels.length > 0 && (
                  <TableRegion label="Deliveries per channel" className="mt-4">
                    <thead>
                      <tr>
                        <Th>Channel</Th>
                        <Th>On server</Th>
                        <Th numeric>Sent</Th>
                        <Th numeric>Pending</Th>
                        <Th numeric>Failed</Th>
                        <Th numeric>Skipped</Th>
                        <Th>Circuit</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {channels.map(([name, raw]) => {
                        const c = rec(raw);
                        const circuit = rec(c?.circuit);
                        return (
                          <tr key={name}>
                            <Td>{name}</Td>
                            <Td>{c?.enabled_on_server === true ? <Badge tone="up">Configured</Badge> : <Badge>Not configured</Badge>}</Td>
                            <Td numeric>{text(c?.sent)}</Td>
                            <Td numeric>{text(c?.pending)}</Td>
                            <Td numeric className={num(c?.failed) ? 'text-danger' : undefined}>
                              {text(c?.failed)}
                            </Td>
                            <Td numeric>{text(c?.skipped)}</Td>
                            <Td>{circuit?.open === true ? <Badge tone="danger">Open ({text(circuit.open_seconds_left)} s)</Badge> : <Badge tone="up">Closed</Badge>}</Td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </TableRegion>
                )}
                <RawJson data={d} />
              </>
            );
          }}
        </Block>
      </Panel>
    </div>
  );
}
