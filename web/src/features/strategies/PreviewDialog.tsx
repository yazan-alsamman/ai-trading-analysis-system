import { Play } from 'lucide-react';
import { useMemo, useState } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, Select } from '@/components/ui/Form';
import { SourceTag } from '@/components/ui/SourceTag';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import { BACKEND_TIMEFRAMES, isBackendTimeframe, type BackendInstrument, type BackendTimeframe, type ParamSpec, type StrategyParams } from '@/domain/strategies';
import { SeriesChart, type SeriesLine } from '@/features/chart/SeriesChart';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatPercent, formatPrice } from '@/lib/format';
import { ParamFields } from './ParamFields';
import { defaultInstrument, humanize, paramDraft, parseParams, type ParamDraft } from './strategyUtils';

export interface PreviewTarget {
  key: string;
  title: string;
  /** Empty for custom strategies (their rules live in the definition). */
  params: readonly ParamSpec[];
}

const BARS = 300;

interface PreviewRequest {
  instrumentId: string;
  timeframe: BackendTimeframe;
  params: StrategyParams;
}

/** The strategy run over recent closed bars (POST /strategies/{key}/preview), drawn on those candles. */
export function PreviewDialog({ target, instruments, onClose }: { target: PreviewTarget | null; instruments: readonly BackendInstrument[]; onClose: () => void }) {
  const [lastTarget, setLastTarget] = useState(target);
  const [instrumentId, setInstrumentId] = useState(defaultInstrument(instruments));
  const [timeframe, setTimeframe] = useState<BackendTimeframe>('1h');
  const [draft, setDraft] = useState<ParamDraft>(() => paramDraft(target?.params ?? []));
  const [paramErrors, setParamErrors] = useState<Record<string, string>>({});
  const [request, setRequest] = useState<PreviewRequest | null>(() => (target ? { instrumentId: defaultInstrument(instruments), timeframe: '1h', params: {} } : null));

  if (target !== lastTarget) {
    setLastTarget(target);
    setDraft(paramDraft(target?.params ?? []));
    setParamErrors({});
    setRequest(target ? { instrumentId, timeframe, params: {} } : null);
  }

  const run = () => {
    const { params, errors } = parseParams(target?.params ?? [], draft);
    setParamErrors(errors);
    if (Object.keys(errors).length === 0) setRequest({ instrumentId, timeframe, params });
  };

  return (
    <Dialog
      open={target !== null}
      onClose={onClose}
      size="lg"
      title={target ? `Preview: ${target.title}` : 'Preview'}
      description="Rule-based signals on past closed bars of the backend's data. This is not AI output, not a forecast and not advice."
      footer={<Button onClick={onClose}>Close</Button>}
    >
      {target && (
        <div className="flex flex-col gap-4">
          <form
            noValidate
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              run();
            }}
          >
            <div className="grid gap-3 sm:grid-cols-[1fr_140px_auto] sm:items-end">
              <Field label="Instrument">
                {({ id, describedBy }) => (
                  <Select id={id} aria-describedby={describedBy} value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)}>
                    {instruments
                      .filter((i) => i.isActive)
                      .map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.symbol}
                        </option>
                      ))}
                  </Select>
                )}
              </Field>
              <Field label="Timeframe">
                {({ id, describedBy }) => (
                  <Select
                    id={id}
                    aria-describedby={describedBy}
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
              <Button type="submit" variant="primary" icon={Play}>
                Run preview
              </Button>
            </div>
            {target.params.length > 0 && (
              <details className="rounded-md border border-line px-3 py-2">
                <summary className="cursor-pointer text-sm font-medium text-fg">Parameters</summary>
                <div className="pt-3">
                  <ParamFields specs={target.params} draft={draft} errors={paramErrors} onChange={setDraft} />
                </div>
              </details>
            )}
          </form>
          {request && <PreviewResult strategyKey={target.key} request={request} instruments={instruments} />}
        </div>
      )}
    </Dialog>
  );
}

function PreviewResult({ strategyKey, request, instruments }: { strategyKey: string; request: PreviewRequest; instruments: readonly BackendInstrument[] }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const instrument = instruments.find((i) => i.id === request.instrumentId);
  const precision = instrument?.pricePrecision ?? 2;
  const res = useResource(`preview:${strategyKey}:${JSON.stringify(request)}`, async (signal) => {
    const [preview, candles] = await Promise.all([
      services.strategies.preview(strategyKey, { ...request, limit: BARS }, { signal }),
      services.instruments.candles(request.instrumentId, request.timeframe, BARS, { signal }),
    ]);
    return { preview, candles };
  });

  const lines = useMemo<SeriesLine[]>(
    () =>
      (res.data?.preview.indicators ?? []).flatMap((ind) => {
        const outputs = Object.entries(ind.outputs);
        return outputs.map(([output, points]) => ({
          name: outputs.length > 1 ? `${ind.name} ${output}` : ind.name,
          points,
          pane: ind.placement === 'overlay' ? 0 : 1,
        }));
      }),
    [res.data],
  );
  const candles = res.data?.candles;
  const markers = res.data?.preview.markers;

  if (res.status === 'loading')
    return (
      <Loading label="Running preview">
        <Skeleton className="h-80 w-full" />
      </Loading>
    );
  if (res.status === 'error' || !res.data) return <ErrorState error={res.error} onRetry={res.reload} title="Could not run the preview" compact />;
  const { preview } = res.data;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
        <SourceTag kind="historical" />
        <span>
          {instrument?.symbol ?? 'Instrument'} · {request.timeframe} · {formatNumber(preview.bars)} bars · {preview.signals.length} signals
        </span>
      </div>
      {candles && candles.length > 0 ? (
        <SeriesChart
          label={`${instrument?.symbol ?? 'Instrument'} ${request.timeframe} candles with ${preview.signals.length} strategy signals marked`}
          candles={candles}
          lines={lines}
          {...(markers ? { markers } : {})}
          precision={precision}
        />
      ) : (
        <EmptyState compact title="No candles" description="The backend has no candles for this instrument and timeframe yet." />
      )}
      {preview.signals.length === 0 ? (
        <p className="text-sm text-fg-3">The rules did not fire on these bars.</p>
      ) : (
        <TableRegion label="Preview signals" className="max-h-64 overflow-y-auto rounded-md border border-line">
          <thead>
            <tr>
              <Th>Bar (close)</Th>
              <Th>Side</Th>
              <Th numeric>Price</Th>
              <Th numeric>Strength</Th>
              <Th>Reason</Th>
            </tr>
          </thead>
          <tbody>
            {[...preview.signals].reverse().map((s) => (
              <tr key={`${s.time}-${s.side}`}>
                <Td className="num">{formatDateTime(s.time * 1000, timeZone)}</Td>
                <Td>
                  <Badge tone={s.side === 'buy' ? 'up' : 'down'}>{s.side === 'buy' ? 'Buy' : 'Sell'}</Badge>
                </Td>
                <Td numeric>{formatPrice(s.price, precision)}</Td>
                <Td numeric>{formatPercent(s.strength)}</Td>
                <Td className="text-fg-2">{humanize(s.reason)}</Td>
              </tr>
            ))}
          </tbody>
        </TableRegion>
      )}
    </div>
  );
}
