import { CopyPlus, Link2Off } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { Field, FormError, Input } from '@/components/ui/Form';
import { Page, PageHeader, Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { ROLE_LABELS, type UserRole } from '@/domain/user';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDateTime } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';

interface PanelSummary {
  id: string;
  instrumentId: string | null;
  timeframe: string | null;
  chartType: string | null;
  indicators: string[];
  strategies: number;
  drawings: number;
}

/** Reads the panels of a state document (docs/workspace-state.schema.json) without inventing fields. */
function panelsOf(state: Record<string, unknown>): PanelSummary[] {
  const panels = Array.isArray(state.panels) ? (state.panels as unknown[]) : [];
  return panels.flatMap((raw, i) => {
    if (!raw || typeof raw !== 'object') return [];
    const p = raw as Record<string, unknown>;
    const list = (v: unknown) => (Array.isArray(v) ? v : []);
    return [
      {
        id: typeof p.id === 'string' ? p.id : `p${i + 1}`,
        instrumentId: typeof p.instrument_id === 'string' ? p.instrument_id : null,
        timeframe: typeof p.timeframe === 'string' ? p.timeframe : null,
        chartType: typeof p.chart_type === 'string' ? p.chart_type : null,
        indicators: list(p.indicators).flatMap((ind) => {
          if (!ind || typeof ind !== 'object') return [];
          const o = ind as { name?: unknown; params?: unknown };
          if (typeof o.name !== 'string') return [];
          const params = o.params && typeof o.params === 'object' ? Object.values(o.params as Record<string, unknown>).join(', ') : '';
          return [params ? `${o.name.toUpperCase()} (${params})` : o.name.toUpperCase()];
        }),
        strategies: list(p.strategies).length,
        drawings: list(p.drawings).length,
      },
    ];
  });
}

const layoutOf = (state: Record<string, unknown>): string | null => {
  const l = state.layout;
  return l && typeof l === 'object' && typeof (l as { type?: unknown }).type === 'string' ? (l as { type: string }).type : null;
};

/** A workspace someone shared by link (GET /workspaces/shared/{slug}): read-only, with a copy into your own workspaces. */
export function SharedWorkspacePage() {
  usePageTitle('Shared workspace');
  const { slug = '' } = useParams();
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const res = useResource(`shared-ws:${slug}`, (signal) => services.workspacesSync.shared(slug, { signal }));
  const instruments = useResource('instrument-directory', (signal) => services.instruments.list({ signal }));
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const symbol = (id: string | null) => (id ? (instruments.data?.find((i) => i.id === id)?.symbol ?? 'Unavailable instrument') : 'No instrument');

  const importIt = async () => {
    const trimmed = name.trim();
    if (trimmed.length > 60) return setError('Use at most 60 characters.');
    setBusy(true);
    setError(null);
    try {
      const ws = await services.workspacesSync.importShared(slug, trimmed || undefined);
      setCopied(ws.name);
      notify(`Copied as “${ws.name}” to your server workspaces.`, 'success');
    } catch (e) {
      setError(isApiError(e) && e.kind === 'conflict' ? 'You already have a workspace with this name. Choose another name.' : userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (res.status === 'loading')
    return (
      <Page width="reading">
        <Loading label="Loading the shared workspace">
          <SkeletonRows rows={4} />
        </Loading>
      </Page>
    );
  if (res.status === 'error' && isApiError(res.error) && res.error.kind === 'not_found')
    return (
      <Page width="reading">
        <EmptyState
          icon={Link2Off}
          title="This link is no longer shared"
          description="The owner stopped sharing this workspace, or the link is mistyped."
          action={
            <Link to="/settings#server-workspaces" className={buttonClasses({ size: 'sm' })}>
              Your workspaces
            </Link>
          }
        />
      </Page>
    );
  if (res.status === 'error' || !res.data)
    return (
      <Page width="reading">
        <ErrorState error={res.error} onRetry={res.reload} />
      </Page>
    );

  const ws = res.data;
  const panels = panelsOf(ws.state);
  const layout = layoutOf(ws.state);
  const role = ws.owner.role as UserRole;
  return (
    <Page width="reading">
      <PageHeader
        title={ws.name}
        meta={<Badge tone="info">Shared, read-only</Badge>}
        description={
          <>
            Shared by {ws.owner.name} ({ROLE_LABELS[role] ?? ws.owner.role}) · updated {formatDateTime(ws.updatedAt, timeZone)}
          </>
        }
      />

      <Panel title="Charts" meta={<span>{layout ? `Layout ${layout}` : `${panels.length} chart${panels.length === 1 ? '' : 's'}`}</span>} flush>
        {panels.length === 0 ? (
          <EmptyState compact title="No chart panels" />
        ) : (
          <ul className="divide-y divide-line">
            {panels.map((p) => (
              <li key={p.id} className="flex flex-col gap-1 px-4 py-3">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                  {symbol(p.instrumentId)}
                  {p.timeframe && <Badge>{p.timeframe}</Badge>}
                  {p.chartType && <Badge>{p.chartType.replace(/_/g, ' ')}</Badge>}
                </p>
                <p className="text-xs text-fg-3">
                  {p.indicators.length ? `Indicators: ${p.indicators.join(' · ')}` : 'No indicators'}
                  {p.strategies > 0 && ` · ${p.strategies} strategy overlay${p.strategies === 1 ? '' : 's'}`}
                  {p.drawings > 0 && ` · ${p.drawings} drawing${p.drawings === 1 ? '' : 's'}`}
                </p>
              </li>
            ))}
          </ul>
        )}
        {ws.unavailableInstrumentIds.length > 0 && (
          <p className="border-t border-line px-4 py-2.5 text-xs text-warning">
            {ws.unavailableInstrumentIds.length} instrument{ws.unavailableInstrumentIds.length === 1 ? ' is' : 's are'} no longer available on this server; those charts stay empty.
          </p>
        )}
      </Panel>

      <Panel title="Copy to my workspaces">
        {copied ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-fg">Copied as “{copied}”. Later changes by the owner do not change your copy.</p>
            <Link to="/settings#server-workspaces" className={buttonClasses({ size: 'sm', variant: 'primary' })}>
              Open your server workspaces
            </Link>
          </div>
        ) : (
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void importIt();
            }}
          >
            <Field label="Name for your copy" optional hint={`Empty: “${ws.name}”`} className="w-full sm:w-72">
              {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />}
            </Field>
            <Button type="submit" variant="primary" icon={CopyPlus} loading={busy}>
              Copy to my workspaces
            </Button>
          </form>
        )}
        <div className="mt-3">
          <FormError message={error} />
        </div>
        <p className="mt-3 text-xs text-fg-3">Your workspace limit applies. The copy is saved on your account; open it in this browser from Settings → Server workspaces → Load.</p>
      </Panel>
    </Page>
  );
}
