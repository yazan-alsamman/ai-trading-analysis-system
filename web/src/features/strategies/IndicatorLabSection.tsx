import { Play, Plus, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { Field, FormError, Input, Select } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, Skeleton, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { IndicatorDefinition } from '@/domain/marketExtras';
import { BACKEND_TIMEFRAMES, isBackendTimeframe, type BackendInstrument, type BackendTimeframe, type StrategyParams } from '@/domain/strategies';
import { SeriesChart, type SeriesLine } from '@/features/chart/SeriesChart';
import { useResource } from '@/hooks/useResource';
import { formatNumber } from '@/lib/format';
import { ParamFields } from './ParamFields';
import { defaultInstrument, paramDraft, parseParams, type ParamDraft } from './strategyUtils';

const MAX_INDICATORS = 4;
const MAX_BARS = 500;

interface IndicatorPick {
  key: number;
  def: IndicatorDefinition;
  draft: ParamDraft;
  errors: Record<string, string>;
}

interface ComputeRequest {
  instrumentId: string;
  timeframe: BackendTimeframe;
  limit: number;
  indicators: { name: string; params: StrategyParams }[];
}

const paramSummary = (d: IndicatorDefinition) =>
  d.params.length ? d.params.map((p) => `${p.title} ${p.default ?? ''}${p.min !== null || p.max !== null ? ` (${p.min ?? '…'}–${p.max ?? '…'})` : ''}`).join(' · ') : 'No parameters';

/**
 * The server's indicator library (GET /indicators) computed on the backend's
 * candles (POST /market/instruments/{id}/indicators). The workspace chart
 * computes its own few indicators in the browser; these are the server's,
 * with its warm-up history.
 */
export function IndicatorLabSection({ instruments }: { instruments: readonly BackendInstrument[] | undefined }) {
  const services = useServices();
  const catalog = useResource('indicators:catalog', (signal) => services.marketContext.indicatorCatalog({ signal }));
  const [instrumentId, setInstrumentId] = useState('');
  const [timeframe, setTimeframe] = useState<BackendTimeframe>('1h');
  const [bars, setBars] = useState('300');
  const [adding, setAdding] = useState('');
  const [picks, setPicks] = useState<IndicatorPick[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [request, setRequest] = useState<ComputeRequest | null>(null);
  const [seq, setSeq] = useState(0);

  const active = (instruments ?? []).filter((i) => i.isActive);
  const chosenInstrument = instrumentId || (instruments ? defaultInstrument(instruments) : '');
  const chosenAdd = adding || catalog.data?.[0]?.name || '';

  const add = () => {
    const def = catalog.data?.find((d) => d.name === chosenAdd);
    if (!def || picks.length >= MAX_INDICATORS) return;
    setPicks((p) => [...p, { key: seq, def, draft: paramDraft(def.params), errors: {} }]);
    setSeq((n) => n + 1);
  };

  const run = () => {
    const limit = Number(bars);
    if (!Number.isInteger(limit) || limit < 10 || limit > MAX_BARS) return setError(`Bars: a whole number from 10 to ${MAX_BARS}.`);
    if (!chosenInstrument) return setError('Choose an instrument.');
    if (picks.length === 0) return setError('Add at least one indicator.');
    let ok = true;
    const parsed = picks.map((p) => {
      const { params, errors } = parseParams(p.def.params, p.draft);
      if (Object.keys(errors).length) ok = false;
      return { pick: { ...p, errors }, params };
    });
    setPicks(parsed.map((x) => x.pick));
    if (!ok) return setError('Fix the highlighted parameters.');
    setError(null);
    setRequest({ instrumentId: chosenInstrument, timeframe, limit, indicators: parsed.map((x) => ({ name: x.pick.def.name, params: x.params })) });
  };

  return (
    <div className="flex flex-col gap-5">
      <Panel title="Compute on the server" meta={<span>Indicators from the backend’s library, on the backend’s candles</span>}>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            run();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-[1fr_140px_120px]">
            <Field label="Instrument">
              {({ id }) => (
                <Select id={id} value={chosenInstrument} onChange={(e) => setInstrumentId(e.target.value)} disabled={!active.length}>
                  {active.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.symbol}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Timeframe">
              {({ id }) => (
                <Select
                  id={id}
                  value={timeframe}
                  onChange={(e) => {
                    if (isBackendTimeframe(e.target.value)) setTimeframe(e.target.value);
                  }}
                >
                  {BACKEND_TIMEFRAMES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Bars" hint={`Up to ${MAX_BARS}`}>
              {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} type="number" min={10} max={MAX_BARS} value={bars} onChange={(e) => setBars(e.target.value)} />}
            </Field>
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <Field label="Indicator" className="w-full sm:w-72">
              {({ id }) => (
                <Select id={id} value={chosenAdd} onChange={(e) => setAdding(e.target.value)} disabled={!catalog.data?.length}>
                  {(catalog.data ?? []).map((d) => (
                    <option key={d.name} value={d.name}>
                      {d.title}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Button icon={Plus} onClick={add} disabled={!catalog.data?.length || picks.length >= MAX_INDICATORS}>
              Add indicator
            </Button>
            <span className="text-xs text-fg-3">
              {picks.length}/{MAX_INDICATORS}
            </span>
          </div>

          {picks.map((p) => (
            <fieldset key={p.key} className="rounded-md border border-line p-3">
              <legend className="flex items-center gap-2 px-1 text-sm font-medium text-fg">
                {p.def.title}
                <Badge>{p.def.placement === 'overlay' ? 'On price' : 'Own pane'}</Badge>
                <IconButton icon={X} size="sm" label={`Remove ${p.def.title}`} onClick={() => setPicks((list) => list.filter((x) => x.key !== p.key))} tooltipSide="left" />
              </legend>
              <ParamFields specs={p.def.params} draft={p.draft} errors={p.errors} onChange={(draft) => setPicks((list) => list.map((x) => (x.key === p.key ? { ...x, draft } : x)))} />
            </fieldset>
          ))}

          <FormError message={error} />
          <Button type="submit" variant="primary" icon={Play} className="self-start" disabled={!instruments}>
            Compute
          </Button>
        </form>
        {request && (
          <div className="mt-5">
            <ComputeResult request={request} instruments={instruments ?? []} />
          </div>
        )}
      </Panel>

      <Panel title="Indicator library" meta={catalog.data && <span>{catalog.data.length} indicators</span>} flush>
        {catalog.status === 'loading' ? (
          <Loading label="Loading the indicator library">
            <SkeletonRows rows={4} className="p-4" />
          </Loading>
        ) : catalog.status === 'error' && !catalog.data ? (
          <ErrorState error={catalog.error} onRetry={catalog.reload} compact />
        ) : (
          <TableRegion label="Indicator library">
            <thead>
              <tr>
                <Th>Indicator</Th>
                <Th>Category</Th>
                <Th>Placement</Th>
                <Th>Parameters (default, range)</Th>
                <Th>Outputs</Th>
                <Th numeric>Warm-up bars</Th>
              </tr>
            </thead>
            <tbody>
              {(catalog.data ?? []).map((d) => (
                <tr key={d.name}>
                  <Td className="font-medium">{d.title}</Td>
                  <Td>{d.category}</Td>
                  <Td>{d.placement === 'overlay' ? 'On price' : 'Own pane'}</Td>
                  <Td className="whitespace-normal text-fg-2">{paramSummary(d)}</Td>
                  <Td className="whitespace-normal">{d.outputs.join(', ')}</Td>
                  <Td numeric>{d.lookback === null ? '—' : formatNumber(d.lookback)}</Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
        )}
      </Panel>
    </div>
  );
}

function ComputeResult({ request, instruments }: { request: ComputeRequest; instruments: readonly BackendInstrument[] }) {
  const services = useServices();
  const instrument = instruments.find((i) => i.id === request.instrumentId);
  const res = useResource(`indicators:compute:${JSON.stringify(request)}`, async (signal) => {
    const [results, candles] = await Promise.all([
      services.marketContext.computeIndicators(request.instrumentId, { timeframe: request.timeframe, limit: request.limit, indicators: request.indicators }, { signal }),
      services.instruments.candles(request.instrumentId, request.timeframe, request.limit, { signal }),
    ]);
    return { results, candles };
  });

  const lines = useMemo<SeriesLine[]>(() => {
    let pane = 0;
    return (res.data?.results ?? []).flatMap((r) => {
      const own = r.placement === 'overlay' ? 0 : ++pane;
      const outputs = Object.entries(r.outputs);
      const label = `${r.name.toUpperCase()}${Object.keys(r.params).length ? ` ${Object.values(r.params).join(',')}` : ''}`;
      return outputs.map(([output, points]) => ({ name: outputs.length > 1 ? `${label} ${output}` : label, points, pane: own }));
    });
  }, [res.data]);
  const candles = res.data?.candles;

  if (res.status === 'loading')
    return (
      <Loading label="Computing indicators">
        <Skeleton className="h-80 w-full" />
      </Loading>
    );
  if (res.status === 'error' || !res.data) return <ErrorState error={res.error} onRetry={res.reload} title="Could not compute these indicators" compact />;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
        <SourceTag kind="historical" label="Computed by the server" detail="Indicator values computed by the backend on its stored candles, with the warm-up history loaded automatically." />
        <span>
          {instrument?.symbol ?? 'Instrument'} · {request.timeframe} · {request.limit} bars
        </span>
      </div>
      {candles && candles.length > 0 ? (
        <SeriesChart
          label={`${instrument?.symbol ?? 'Instrument'} ${request.timeframe} candles with ${request.indicators.map((i) => i.name).join(', ')} computed by the server`}
          candles={candles}
          lines={lines}
          precision={instrument?.pricePrecision ?? 2}
          height={Math.min(560, 320 + 120 * new Set(lines.map((l) => l.pane)).size)}
        />
      ) : (
        <EmptyState compact title="No candles" description="The backend has no candles for this instrument and timeframe yet." />
      )}
    </div>
  );
}
