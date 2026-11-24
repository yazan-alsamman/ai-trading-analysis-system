import { ExternalLink, Link2, Pencil, Plus, Upload } from 'lucide-react';
import { useState } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input, Select, Textarea } from '@/components/ui/Form';
import { JsonView } from '@/components/ui/JsonView';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { AdminInstrument, JsonObject } from '@/domain/admin';
import { useResource } from '@/hooks/useResource';
import { formatNumber } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { MAX_CANDLES, NUMERIC_SPECS, parseCandleCsv } from './marketDataCsv';

const MARKETS = ['forex', 'commodity', 'crypto', 'stock'] as const;

type Form = Record<string, string> & { is_active: string };

function toForm(i: AdminInstrument | null): Form {
  const spec = (k: string) => {
    const v = i?.specs[k];
    return v === null || v === undefined ? '' : String(v);
  };
  return {
    symbol: i?.symbol ?? '',
    source: i?.source ?? '',
    market: i?.market ?? 'forex',
    base_asset: i?.baseAsset ?? '',
    quote_asset: i?.quoteAsset ?? '',
    price_precision: i?.pricePrecision === null || i?.pricePrecision === undefined ? '' : String(i.pricePrecision),
    quantity_precision: i?.quantityPrecision === null || i?.quantityPrecision === undefined ? '' : String(i.quantityPrecision),
    is_active: i ? String(i.isActive) : 'true',
    quote_currency: spec('quote_currency'),
    price_basis: spec('price_basis'),
    ...Object.fromEntries(NUMERIC_SPECS.map((s) => [s.key, spec(s.key)])),
  };
}

/** Form strings → the backend's JSON; `null` clears a field (edits only). */
function toBody(f: Form, initial: Form | null): { body: JsonObject; error: string | null } {
  const body: JsonObject = {};
  const changed = (k: string) => !initial || f[k] !== initial[k];
  const put = (k: string, v: unknown) => {
    if (changed(k)) body[k] = v;
  };
  if (!initial) {
    if (!f.symbol?.trim() || !f.source?.trim()) return { body, error: 'Symbol and source are required.' };
    body.symbol = f.symbol.trim();
    body.source = f.source.trim();
    body.market = f.market;
  }
  for (const k of ['base_asset', 'quote_asset', 'quote_currency', 'price_basis']) {
    const v = (f[k] ?? '').trim();
    if (v.length > 16) return { body, error: `${k.replace('_', ' ')}: at most 16 characters.` };
    if (v || initial) put(k, v || null);
  }
  for (const k of ['price_precision', 'quantity_precision']) {
    const v = (f[k] ?? '').trim();
    if (v && (!/^\d+$/.test(v) || Number(v) > 18)) return { body, error: `${k.replace('_', ' ')}: a whole number 0–18.` };
    if (v || initial) put(k, v ? Number(v) : null);
  }
  for (const s of NUMERIC_SPECS) {
    const v = (f[s.key] ?? '').trim();
    if (v) {
      const n = Number(v);
      const min = s.min ?? 0;
      if (!Number.isFinite(n) || (s.min === undefined ? n <= 0 : n < min) || (s.max !== undefined && n > s.max)) return { body, error: `${s.label}: ${s.min === undefined ? 'a number above 0' : `a number ≥ ${min}`}${s.max !== undefined ? ` and ≤ ${s.max}` : ''}.` };
      put(s.key, n);
    } else if (initial) put(s.key, null);
  }
  put('is_active', f.is_active === 'true');
  return { body, error: null };
}

function InstrumentDialog({ instrument, onClose, onSaved }: { instrument: AdminInstrument | null; onClose: () => void; onSaved: (i: AdminInstrument) => void }) {
  const services = useServices();
  const initial = instrument ? toForm(instrument) : null;
  const [f, setF] = useState<Form>(() => toForm(instrument));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((cur) => ({ ...cur, [k]: v }));

  const save = async () => {
    const { body, error: e } = toBody(f, initial);
    if (e) return setError(e);
    if (instrument && Object.keys(body).length === 0) return onClose();
    setBusy(true);
    setError(null);
    try {
      onSaved(instrument ? await services.admin.updateInstrument(instrument.id, body) : await services.admin.createInstrument(body));
    } catch (err) {
      setError(userMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const text = (k: string, label: string, hint?: string) => (
    <Field key={k} label={label} optional={k !== 'symbol' && k !== 'source'} {...(hint ? { hint } : {})}>
      {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={f[k] ?? ''} onChange={(e) => set(k, e.target.value)} />}
    </Field>
  );
  return (
    <Dialog
      open
      onClose={onClose}
      size="lg"
      title={instrument ? `Edit ${instrument.symbol}` : 'New instrument'}
      description={instrument ? 'Only the fields you change are sent. Emptying a spec clears it.' : 'Symbol, source and market cannot be changed later.'}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="instrument-form" loading={busy}>
            {instrument ? 'Save' : 'Create'}
          </Button>
        </>
      }
    >
      <form
        id="instrument-form"
        className="grid gap-3 sm:grid-cols-2"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        {!instrument && (
          <>
            {text('symbol', 'Symbol', 'e.g. AUD/USD')}
            {text('source', 'Source', 'e.g. twelvedata, binance, fxpro')}
            <Field label="Market">
              {({ id }) => (
                <Select id={id} value={f.market} onChange={(e) => set('market', e.target.value)}>
                  {MARKETS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </>
        )}
        {text('base_asset', 'Base asset')}
        {text('quote_asset', 'Quote asset')}
        {text('price_precision', 'Price precision', 'Decimals, 0–18')}
        {text('quantity_precision', 'Quantity precision', 'Decimals, 0–18')}
        {text('quote_currency', 'Quote currency', 'Currency of the P&L per price unit (default: quote asset)')}
        <Field label="Price basis" optional>
          {({ id }) => (
            <Select id={id} value={f.price_basis} onChange={(e) => set('price_basis', e.target.value)}>
              <option value="">Not set</option>
              <option value="bid">Bid</option>
              <option value="mid">Mid</option>
              <option value="last">Last</option>
            </Select>
          )}
        </Field>
        {NUMERIC_SPECS.map((s) => text(s.key, s.label, s.hint || undefined))}
        <div className="sm:col-span-2">
          <Checkbox label="Active" description="Inactive instruments are hidden from users and not streamed" checked={f.is_active === 'true'} onChange={(e) => set('is_active', String(e.target.checked))} />
        </div>
        <div className="sm:col-span-2">
          <FormError message={error} />
        </div>
      </form>
    </Dialog>
  );
}

function InstrumentsPanel({ res }: { res: ReturnType<typeof useInstruments> }) {
  const { notify } = useToast();
  const [editing, setEditing] = useState<AdminInstrument | 'new' | null>(null);
  const [specsOf, setSpecsOf] = useState<AdminInstrument | null>(null);
  return (
    <Panel
      title="Instruments"
      meta={res.data && <span>{res.data.length} total</span>}
      actions={
        <Button size="sm" icon={Plus} onClick={() => setEditing('new')}>
          New instrument
        </Button>
      }
      flush
    >
      {res.status === 'loading' ? (
        <Loading label="Loading instruments">
          <SkeletonRows rows={4} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact title="No instruments" />
      ) : (
        <TableRegion label="Instruments">
          <thead>
            <tr>
              <Th>Symbol</Th>
              <Th>Source</Th>
              <Th>Market</Th>
              <Th numeric>Price dp</Th>
              <Th numeric>Qty dp</Th>
              <Th>Status</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {res.data.map((i) => (
              <tr key={i.id}>
                <Td className="font-medium">{i.symbol}</Td>
                <Td>{i.source}</Td>
                <Td>{i.market}</Td>
                <Td numeric>{i.pricePrecision ?? '—'}</Td>
                <Td numeric>{i.quantityPrecision ?? '—'}</Td>
                <Td>
                  <Badge tone={i.isActive ? 'up' : 'neutral'}>{i.isActive ? 'Active' : 'Inactive'}</Badge>
                </Td>
                <Td>
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setSpecsOf(i)}>
                      Specs
                    </Button>
                    <IconButton icon={Pencil} size="sm" label={`Edit ${i.symbol}`} onClick={() => setEditing(i)} tooltipSide="left" />
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </TableRegion>
      )}
      {editing && (
        <InstrumentDialog
          instrument={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            res.setData((list) => (list ?? []).some((x) => x.id === saved.id) ? (list ?? []).map((x) => (x.id === saved.id ? saved : x)) : [...(list ?? []), saved]);
            notify(`${saved.symbol} saved.`, 'success');
            setEditing(null);
          }}
        />
      )}
      {specsOf && (
        <Dialog open onClose={() => setSpecsOf(null)} title={`${specsOf.symbol} specs`} description="As stored by the backend." footer={<Button onClick={() => setSpecsOf(null)}>Close</Button>}>
          <JsonView value={specsOf.specs} />
        </Dialog>
      )}
    </Panel>
  );
}

function useInstruments() {
  const services = useServices();
  return useResource('admin:instruments', (signal) => services.admin.instruments({ signal }));
}

function CandleUploadPanel({ instruments }: { instruments: AdminInstrument[] }) {
  const services = useServices();
  const [instrumentId, setInstrumentId] = useState('');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [written, setWritten] = useState<number | null>(null);
  const chosen = instrumentId || instruments[0]?.id || '';
  const parsed = text.trim() ? parseCandleCsv(text) : null;

  const upload = async () => {
    if (!parsed || parsed.errors.length || !parsed.candles.length || !chosen) return;
    setBusy(true);
    setError(null);
    setWritten(null);
    try {
      setWritten(await services.admin.uploadCandles(chosen, parsed.candles));
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Upload 1-minute candles" meta={<span>Backfill: at most {formatNumber(MAX_CANDLES)} bars per upload; higher timeframes refresh automatically</span>}>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          void upload();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Instrument">
            {({ id }) => (
              <Select id={id} value={chosen} onChange={(e) => setInstrumentId(e.target.value)}>
                {instruments.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.symbol} · {i.source}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="CSV file" optional hint="Or paste below">
            {({ id, describedBy }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                type="file"
                accept=".csv,text/csv"
                className="h-auto py-1.5"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void file.text().then(setText);
                }}
              />
            )}
          </Field>
        </div>
        <Field label="Candles (CSV)" hint="Header: ts,open,high,low,close,volume[,spread,source] — ts in ISO 8601 UTC, one bar per minute">
          {({ id, describedBy }) => (
            <Textarea id={id} aria-describedby={describedBy} rows={6} className="font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} placeholder={'ts,open,high,low,close,volume\n2026-10-26T14:31:00Z,2400.1,2400.9,2399.8,2400.5,120'} />
          )}
        </Field>
        {parsed && parsed.errors.length > 0 && (
          <ul role="alert" className="list-disc pl-5 text-xs text-danger">
            {parsed.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        )}
        {parsed && !parsed.errors.length && <p className="text-xs text-fg-2">{formatNumber(parsed.candles.length)} candles ready.</p>}
        <FormError message={error} />
        <Button type="submit" icon={Upload} loading={busy} disabled={!parsed || parsed.errors.length > 0 || !parsed.candles.length || !chosen} className="self-start">
          Upload
        </Button>
        {written !== null && (
          <p role="status" className="text-sm text-fg-2">
            {formatNumber(written)} candles written.
          </p>
        )}
      </form>
    </Panel>
  );
}

function CTraderPanel() {
  const services = useServices();
  const { notify } = useToast();
  const status = useResource('admin:ctrader', (signal) => services.admin.ctraderStatus({ signal }));
  const [connect, setConnect] = useState<JsonObject | null>(null);
  const [code, setCode] = useState('');
  const [state, setState] = useState('');
  const [account, setAccount] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JsonObject | null>(null);

  const run = async (key: string, fn: () => Promise<JsonObject>, done: string) => {
    setBusy(key);
    setError(null);
    try {
      const r = await fn();
      setResult(r);
      notify(done, 'success');
      status.reload();
      return r;
    } catch (e) {
      setError(userMessage(e));
      return null;
    } finally {
      setBusy(null);
    }
  };
  const s = status.data;
  const flag = (k: string) => s?.[k] === true;
  const authUrl = typeof connect?.authorization_url === 'string' ? connect.authorization_url : typeof connect?.url === 'string' ? connect.url : null;

  return (
    <Panel title="cTrader XAU/USD feed" meta={<span>Ships disabled until the cTrader app is approved and an account is linked</span>}>
      <div className="flex flex-col gap-5">
        {status.status === 'loading' ? (
          <Loading label="Loading feed status">
            <SkeletonRows rows={3} />
          </Loading>
        ) : status.status === 'error' ? (
          <ErrorState error={status.error} onRetry={status.reload} compact />
        ) : s ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Badge tone={flag('enabled') ? 'up' : 'neutral'}>{flag('enabled') ? 'Enabled' : 'Disabled'}</Badge>
              <Badge tone={flag('app_credentials') ? 'up' : 'warning'}>{flag('app_credentials') ? 'App credentials set' : 'No app credentials'}</Badge>
              <Badge tone={flag('linked') ? 'up' : 'neutral'}>{flag('linked') ? 'Account linked' : 'Not linked'}</Badge>
              <Badge tone={flag('connected') ? 'up' : 'neutral'}>{flag('connected') ? 'Connected' : 'Not connected'}</Badge>
              {typeof s.state === 'string' && <Badge>{s.state}</Badge>}
            </div>
            <details>
              <summary className="cursor-pointer text-sm text-fg-2">Full status</summary>
              <div className="mt-2">
                <JsonView value={s} />
              </div>
            </details>
          </>
        ) : null}

        <div className="flex flex-col gap-2 border-t border-line pt-4">
          <p className="text-sm font-medium text-fg">1. Link an account</p>
          <Button
            icon={Link2}
            className="self-start"
            loading={busy === 'connect'}
            onClick={() => void run('connect', () => services.admin.ctraderConnect(), 'Authorization link created.').then((r) => r && setConnect(r))}
          >
            Get authorization link
          </Button>
          {connect && (
            <div className="rounded-md border border-line p-3 text-sm">
              {authUrl && (
                <a href={authUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent underline-offset-2 hover:underline">
                  Open cTrader authorization <ExternalLink aria-hidden className="size-3.5" />
                  <span className="sr-only">(opens in a new tab)</span>
                </a>
              )}
              <p className="mt-2 text-xs text-fg-3">The link is valid 10 minutes (view-only scope). Register the redirect URI in the cTrader app first.</p>
              <div className="mt-2">
                <JsonView value={connect} />
              </div>
            </div>
          )}
          <form
            className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]"
            onSubmit={(e) => {
              e.preventDefault();
              if (code.trim() && state.trim()) void run('code', () => services.admin.ctraderCode(code.trim(), state.trim()), 'Code accepted.');
            }}
          >
            <Field label="Code" hint="If the redirect did not reach the server (valid one minute)">
              {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={code} onChange={(e) => setCode(e.target.value)} />}
            </Field>
            <Field label="State">
              {({ id }) => <Input id={id} value={state} onChange={(e) => setState(e.target.value)} />}
            </Field>
            <Button type="submit" className="self-end" loading={busy === 'code'} disabled={!code.trim() || !state.trim()}>
              Submit code
            </Button>
          </form>
        </div>

        <form
          className="flex flex-col gap-2 border-t border-line pt-4"
          onSubmit={(e) => {
            e.preventDefault();
            const n = Number(account);
            if (Number.isInteger(n) && n > 0) void run('account', () => services.admin.ctraderAccount(n), 'Account chosen. Restart feed-ctrader to use it.');
          }}
        >
          <p className="text-sm font-medium text-fg">2. Choose the trader account</p>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Account id" hint="One of the linked token's accounts; restart feed-ctrader afterwards" className="w-full sm:w-72">
              {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} inputMode="numeric" value={account} onChange={(e) => setAccount(e.target.value)} />}
            </Field>
            <Button type="submit" loading={busy === 'account'} disabled={!(Number.isInteger(Number(account)) && Number(account) > 0)}>
              Use this account
            </Button>
          </div>
        </form>

        <form
          className="flex flex-col gap-2 border-t border-line pt-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!from || !to) return setError('Choose both dates.');
            const days = (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000;
            if (!(days > 0)) return setError('“From” must be before “to”.');
            if (days > 400) return setError('At most 400 days per backfill.');
            void run('backfill', () => services.admin.ctraderBackfill(`${from}T00:00:00Z`, `${to}T00:00:00Z`), 'Backfill started; progress appears in the status.');
          }}
        >
          <p className="text-sm font-medium text-fg">3. Backfill M1 history</p>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="From (UTC)">
              {({ id }) => <Input id={id} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}
            </Field>
            <Field label="To (UTC)">
              {({ id }) => <Input id={id} type="date" value={to} onChange={(e) => setTo(e.target.value)} />}
            </Field>
            <Button type="submit" loading={busy === 'backfill'}>
              Start backfill
            </Button>
          </div>
          <p className="text-xs text-fg-3">Runs in the background, a day per request. Bars built live (with a spread) are never overwritten.</p>
        </form>

        <FormError message={error} />
        {result && (
          <div role="status">
            <p className="mb-2 text-sm font-medium text-fg">Last answer</p>
            <JsonView value={result} />
          </div>
        )}
      </div>
    </Panel>
  );
}

/** Admin › Market data: instruments and their specs, candle backfill, the cTrader feed. */
export function AdminMarketDataPage() {
  const res = useInstruments();
  return (
    <div className="flex flex-col gap-5">
      <InstrumentsPanel res={res} />
      {res.data && res.data.length > 0 && <CandleUploadPanel instruments={res.data} />}
      <CTraderPanel />
    </div>
  );
}
