import { CheckCircle2, Plus, RotateCw } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Field, FormError, Input, Select, Textarea } from '@/components/ui/Form';
import { JsonView } from '@/components/ui/JsonView';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { AdminAISetup, AdminInstrument, AIModel, JsonObject } from '@/domain/admin';
import { SETUP_STATES, type SetupState } from '@/domain/aiSetups';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatDateTime, formatNumber, formatPct } from '@/lib/format';
import { userMessage } from '@/services/errors';

const STATE_TONE: Record<SetupState, BadgeTone> = { DEVELOPING: 'neutral', ARMED: 'accent', ACTIVE: 'info', CLOSED: 'neutral', EXPIRED: 'neutral', INVALIDATED: 'warning' };
const OUTBOX_TONE: Record<string, BadgeTone> = { pending: 'info', done: 'up', skipped: 'neutral', failed: 'danger' };
const OUTBOX_PAGE = 25;

const price = (v: number | null) => (v === null ? '—' : formatNumber(v, 2));
const short = (id: string) => `${id.slice(0, 8)}…`;

function SetupDetailDialog({ setupId, symbol, onClose }: { setupId: string; symbol: string; onClose: () => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource(`admin:ai-setup:${setupId}`, (signal) => services.admin.aiSetup(setupId, { signal }));
  const d = res.data;
  return (
    <Dialog open onClose={onClose} size="lg" title={`Setup · ${symbol}`} description={setupId} footer={<Button onClick={onClose}>Close</Button>}>
      {res.status === 'loading' ? (
        <Loading label="Loading the setup">
          <SkeletonRows rows={5} />
        </Loading>
      ) : res.status === 'error' || !d ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone={STATE_TONE[d.state]}>{d.state}</Badge>
            <Badge tone={d.direction === 'buy' ? 'up' : 'down'}>{d.direction}</Badge>
            <span>
              Entry {price(d.entry)} · stop {price(d.sl)} · target {price(d.tp)} · R {d.rMultiple === null ? '—' : formatNumber(d.rMultiple, 2)}
            </span>
            <span className="text-fg-3">Taken by {d.takesCount} user(s)</span>
          </div>
          <section aria-label="State events">
            <h3 className="mb-2 text-sm font-semibold">State events</h3>
            <ol className="flex flex-col gap-1 text-sm">
              {d.events.map((e, i) => (
                <li key={i} className="flex flex-wrap gap-2">
                  <span className="text-fg-3">{formatDateTime(e.at, timeZone)}</span>
                  <span>
                    {e.from ?? 'appeared'} → <strong>{e.to}</strong>
                  </span>
                  {e.reason && <span className="text-fg-2">{e.reason}</span>}
                  {e.realizedR !== null && <span className="num">{formatNumber(e.realizedR, 2)}R</span>}
                </li>
              ))}
            </ol>
          </section>
          <section aria-label="Alerts">
            <h3 className="mb-2 text-sm font-semibold">Alerts (outbox)</h3>
            {d.outbox.length === 0 ? (
              <p className="text-sm text-fg-3">None.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {d.outbox.map((o) => (
                  <li key={o.id} className="flex flex-wrap gap-2">
                    <Badge tone={OUTBOX_TONE[o.status] ?? 'neutral'}>{o.status}</Badge>
                    <span>
                      {o.from ?? '—'} → {o.to}
                    </span>
                    <span className="text-fg-3">{o.attempts} attempt(s)</span>
                    {o.lastError && <span className="text-danger">{o.lastError}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Stored sizes">
            <h3 className="mb-2 text-sm font-semibold">Stored sizes</h3>
            {d.sizes.length === 0 ? (
              <p className="text-sm text-fg-3">None.</p>
            ) : (
              <TableRegion label="Stored sizes">
                <thead>
                  <tr>
                    <Th>User</Th>
                    <Th numeric>Lots</Th>
                    <Th>Feasible</Th>
                    <Th>Source</Th>
                    <Th>Computed</Th>
                  </tr>
                </thead>
                <tbody>
                  {d.sizes.map((s) => (
                    <tr key={s.userId}>
                      <Td className="num" title={s.userId}>
                        {short(s.userId)}
                      </Td>
                      <Td numeric>{formatNumber(s.lots, 2)}</Td>
                      <Td>{s.feasible ? 'Yes' : 'No'}</Td>
                      <Td>{s.source}</Td>
                      <Td className="text-fg-2">{formatDateTime(s.computedAt, timeZone)}</Td>
                    </tr>
                  ))}
                </tbody>
              </TableRegion>
            )}
          </section>
          <details>
            <summary className="cursor-pointer text-sm font-semibold">Evidence</summary>
            <div className="mt-2">
              <JsonView value={d.evidence} />
            </div>
          </details>
          <details>
            <summary className="cursor-pointer text-sm font-semibold">Last payload from the AI engine</summary>
            <div className="mt-2">
              <JsonView value={d.lastPayload} />
            </div>
          </details>
        </div>
      )}
    </Dialog>
  );
}

function SetupsPanel({ instruments }: { instruments: AdminInstrument[] | undefined }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const [state, setState] = useState<SetupState | ''>('');
  const [instrumentId, setInstrumentId] = useState('');
  const [open, setOpen] = useState<AdminAISetup | null>(null);
  const res = useResource(`admin:ai-setups:${state}:${instrumentId}`, (signal) =>
    services.admin.aiSetups({ limit: 50, ...(state ? { state } : {}), ...(instrumentId ? { instrumentId } : {}) }, { signal }),
  );
  const symbolOf = (id: string) => instruments?.find((i) => i.id === id)?.symbol ?? short(id);

  return (
    <Panel
      title="Setups"
      meta={<span>Newest 50. Version 1 runs the setup rules only: probability, EV and grade stay empty until a model is active.</span>}
      flush
    >
      <div className="flex flex-wrap gap-3 border-b border-line px-4 py-3">
        <Field label="State" className="w-full sm:w-44">
          {({ id }) => (
            <Select id={id} value={state} onChange={(e) => setState(e.target.value as SetupState | '')}>
              <option value="">All states</option>
              {SETUP_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Instrument" className="w-full sm:w-52">
          {({ id }) => (
            <Select id={id} value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)}>
              <option value="">All instruments</option>
              {(instruments ?? []).map((i) => (
                <option key={i.id} value={i.id}>
                  {i.symbol} · {i.source}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      {res.status === 'loading' ? (
        <Loading label="Loading setups">
          <SkeletonRows rows={4} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact title="No setups" description="The AI engine has not proposed a setup matching these filters." />
      ) : (
        <TableRegion label="AI setups (admin)">
          <thead>
            <tr>
              <Th>Instrument</Th>
              <Th>Profile</Th>
              <Th>Side</Th>
              <Th>State</Th>
              <Th numeric>Entry</Th>
              <Th numeric>Stop</Th>
              <Th numeric>Target</Th>
              <Th numeric>R</Th>
              <Th numeric>Probability</Th>
              <Th>Versions</Th>
              <Th>Updated</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {res.data.map((s) => (
              <tr key={s.setupId}>
                <Td>{symbolOf(s.instrumentId)}</Td>
                <Td>{s.profile}</Td>
                <Td>
                  <Badge tone={s.direction === 'buy' ? 'up' : 'down'}>{s.direction}</Badge>
                </Td>
                <Td>
                  <Badge tone={STATE_TONE[s.state]}>{s.state}</Badge>
                  {s.realizedR !== null && <span className="num ml-1.5 text-xs">{formatNumber(s.realizedR, 2)}R</span>}
                </Td>
                <Td numeric>{price(s.entry)}</Td>
                <Td numeric>{price(s.sl)}</Td>
                <Td numeric>{price(s.tp)}</Td>
                <Td numeric>{s.rMultiple === null ? '—' : formatNumber(s.rMultiple, 2)}</Td>
                <Td numeric title={s.probability === null ? 'No model: rules only' : undefined}>
                  {s.probability === null ? '— (rules only)' : formatPct(s.probability * 100, 0)}
                </Td>
                <Td className="text-xs text-fg-2">
                  {s.strategyVersion ?? '—'} / {s.modelVersion ?? 'no model'}
                </Td>
                <Td className="text-fg-2">{formatDateTime(s.updatedAt, timeZone)}</Td>
                <Td>
                  <Button size="sm" onClick={() => setOpen(s)}>
                    Details
                  </Button>
                </Td>
              </tr>
            ))}
          </tbody>
        </TableRegion>
      )}
      {open && <SetupDetailDialog setupId={open.setupId} symbol={symbolOf(open.instrumentId)} onClose={() => setOpen(null)} />}
    </Panel>
  );
}

function OutboxPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState<number | null>(null);
  const res = useResource(`admin:ai-outbox:${status}:${offset}`, (signal) => services.admin.aiOutbox({ limit: OUTBOX_PAGE, offset, ...(status ? { status } : {}) }, { signal }));

  const retry = async (id: number) => {
    setBusy(id);
    try {
      const row = await services.admin.retryOutbox(id);
      res.setData((p) => ({ total: p?.total ?? 0, items: (p?.items ?? []).map((x) => (x.id === id ? row : x)) }));
      notify('Alert queued again.', 'success');
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel title="Alert outbox" meta={<span>AI setup alerts with their delivery attempts</span>} flush>
      <div className="border-b border-line px-4 py-3">
        <Field label="Status" className="w-full sm:w-44">
          {({ id }) => (
            <Select
              id={id}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="done">Done</option>
              <option value="skipped">Skipped</option>
              <option value="failed">Failed</option>
            </Select>
          )}
        </Field>
      </div>
      {res.status === 'loading' ? (
        <Loading label="Loading the outbox">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.items.length ? (
        <EmptyState compact title="No alerts" />
      ) : (
        <>
          <TableRegion label="Alert outbox">
            <thead>
              <tr>
                <Th>Setup</Th>
                <Th>Change</Th>
                <Th>Status</Th>
                <Th numeric>Attempts</Th>
                <Th>Last error</Th>
                <Th>Created</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((o) => (
                <tr key={o.id}>
                  <Td className="max-w-56 truncate" title={o.setupId}>
                    {o.setupId}
                  </Td>
                  <Td>
                    {o.from ?? '—'} → {o.to}
                  </Td>
                  <Td>
                    <Badge tone={OUTBOX_TONE[o.status] ?? 'neutral'}>{o.status}</Badge>
                  </Td>
                  <Td numeric>{o.attempts}</Td>
                  <Td className="max-w-64 truncate text-fg-2" title={o.lastError ?? undefined}>
                    {o.lastError ?? '—'}
                  </Td>
                  <Td className="text-fg-2">{formatDateTime(o.createdAt, timeZone)}</Td>
                  <Td>
                    {o.status === 'failed' && (
                      <Button size="sm" icon={RotateCw} loading={busy === o.id} onClick={() => void retry(o.id)}>
                        Retry
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
          {res.data.total > OUTBOX_PAGE && (
            <div className="flex justify-end gap-2 border-t border-line px-4 py-2">
              <Button size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - OUTBOX_PAGE))}>
                Previous
              </Button>
              <Button size="sm" disabled={offset + OUTBOX_PAGE >= res.data.total} onClick={() => setOffset((o) => o + OUTBOX_PAGE)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}

function RegisterModelDialog({ onClose, onSaved }: { onClose: () => void; onSaved: (m: AIModel) => void }) {
  const services = useServices();
  const [f, setF] = useState({ modelId: '', from: '', to: '', dataHash: '', metrics: '{}', notes: '' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((cur) => ({ ...cur, [k]: v }));
  const save = async () => {
    let metrics: JsonObject;
    try {
      const parsed: unknown = JSON.parse(f.metrics || '{}');
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('not an object');
      metrics = parsed as JsonObject;
    } catch {
      return setError('Metrics must be a JSON object, e.g. {"auc": 0.61}.');
    }
    if (!f.modelId.trim() || f.modelId.length > 128) return setError('Model id: 1–128 characters.');
    if (f.dataHash.length > 128) return setError('Data hash: at most 128 characters.');
    if (f.notes.length > 2000) return setError('Notes: at most 2,000 characters.');
    setBusy(true);
    setError(null);
    try {
      onSaved(
        await services.admin.registerModel({
          modelId: f.modelId.trim(),
          trainingFrom: f.from ? `${f.from}T00:00:00Z` : null,
          trainingTo: f.to ? `${f.to}T00:00:00Z` : null,
          dataHash: f.dataHash.trim() || null,
          metrics,
          notes: f.notes.trim() || null,
        }),
      );
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open
      onClose={onClose}
      title="Register a model"
      description="Registered inactive. Registering a known id updates its description."
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="model-form" loading={busy}>
            Register
          </Button>
        </>
      }
    >
      <form
        id="model-form"
        className="grid gap-3 sm:grid-cols-2"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <Field label="Model id" className="sm:col-span-2">
          {({ id }) => <Input id={id} value={f.modelId} onChange={(e) => set('modelId')(e.target.value)} />}
        </Field>
        <Field label="Training from" optional>
          {({ id }) => <Input id={id} type="date" value={f.from} onChange={(e) => set('from')(e.target.value)} />}
        </Field>
        <Field label="Training to" optional>
          {({ id }) => <Input id={id} type="date" value={f.to} onChange={(e) => set('to')(e.target.value)} />}
        </Field>
        <Field label="Data hash" optional className="sm:col-span-2">
          {({ id }) => <Input id={id} value={f.dataHash} onChange={(e) => set('dataHash')(e.target.value)} />}
        </Field>
        <Field label="Metrics (JSON object)" className="sm:col-span-2">
          {({ id }) => <Textarea id={id} rows={4} className="font-mono text-xs" value={f.metrics} onChange={(e) => set('metrics')(e.target.value)} />}
        </Field>
        <Field label="Notes" optional className="sm:col-span-2">
          {({ id }) => <Textarea id={id} rows={2} value={f.notes} onChange={(e) => set('notes')(e.target.value)} />}
        </Field>
        <div className="sm:col-span-2">
          <FormError message={error} />
        </div>
      </form>
    </Dialog>
  );
}

function ModelsPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const res = useResource('admin:ai-models', (signal) => services.admin.aiModels({ signal }));
  const [registering, setRegistering] = useState(false);
  const [activating, setActivating] = useState<AIModel | null>(null);
  const [busy, setBusy] = useState(false);

  const activate = async () => {
    if (!activating) return;
    setBusy(true);
    try {
      const m = await services.admin.activateModel(activating.modelId);
      res.setData((list) => (list ?? []).map((x) => (x.modelId === m.modelId ? m : { ...x, isActive: false })));
      notify(`${m.modelId} is now the active model.`, 'success');
      setActivating(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="Models"
      meta={<span>The registry; at most one model is active</span>}
      actions={
        <Button size="sm" icon={Plus} onClick={() => setRegistering(true)}>
          Register model
        </Button>
      }
    >
      {res.status === 'loading' ? (
        <Loading label="Loading models">
          <SkeletonRows rows={2} />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact title="No model registered" description="The AI engine runs its setup rules alone (version 1)." />
      ) : (
        <ul className="flex flex-col gap-3">
          {res.data.map((m) => (
            <li key={m.modelId} className="rounded-md border border-line p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-fg">{m.modelId}</span>
                {m.isActive ? (
                  <Badge tone="up">
                    <CheckCircle2 aria-hidden className="size-3" /> Active
                  </Badge>
                ) : (
                  <Badge>Inactive</Badge>
                )}
                <span className="text-xs text-fg-3">Registered {formatDateTime(m.createdAt, timeZone)}</span>
                {!m.isActive && (
                  <Button size="sm" className="ml-auto" onClick={() => setActivating(m)}>
                    Activate
                  </Button>
                )}
              </div>
              <p className="mt-1 text-xs text-fg-2">
                Training {m.trainingFrom ? formatDate(m.trainingFrom, 'UTC') : '—'} – {m.trainingTo ? formatDate(m.trainingTo, 'UTC') : '—'} · data hash {m.dataHash ?? '—'}
              </p>
              {m.notes && <p className="mt-1 text-sm text-fg">{m.notes}</p>}
              {Object.keys(m.metrics).length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-fg-2">Metrics</summary>
                  <div className="mt-2">
                    <JsonView value={m.metrics} />
                  </div>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}
      {registering && (
        <RegisterModelDialog
          onClose={() => setRegistering(false)}
          onSaved={(m) => {
            res.setData((list) => [m, ...(list ?? []).filter((x) => x.modelId !== m.modelId)]);
            notify(`${m.modelId} registered (inactive).`, 'success');
            setRegistering(false);
          }}
        />
      )}
      <ConfirmDialog
        open={activating !== null}
        title="Activate this model?"
        description={`“${activating?.modelId ?? ''}” becomes the only active model. The AI engine uses it for new evaluations.`}
        confirmLabel="Activate"
        destructive={false}
        busy={busy}
        onConfirm={() => void activate()}
        onCancel={() => setActivating(null)}
      />
    </Panel>
  );
}

/** Admin › AI engine: setups with their history, the alert outbox and the model registry. */
export function AdminAIEnginePage() {
  const services = useServices();
  const instruments = useResource('admin:instruments', (signal) => services.admin.instruments({ signal }));
  return (
    <div className="flex flex-col gap-5">
      <SetupsPanel instruments={instruments.data} />
      <OutboxPanel />
      <ModelsPanel />
    </div>
  );
}
