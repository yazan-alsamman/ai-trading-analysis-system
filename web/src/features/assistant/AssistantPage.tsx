import { AlertTriangle, Ban, CheckCircle2, RotateCw } from 'lucide-react';
import { useCallback } from 'react';
import { useSearchParams } from 'react-router';
import { usePreferences } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Field, Select } from '@/components/ui/Form';
import { PageHeader } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { INSTRUMENTS, isInstrumentSymbol, type InstrumentSymbol } from '@/domain/instruments';
import { isTimeframe, TIMEFRAMES } from '@/domain/market';
import { usePageTitle } from '@/hooks/usePageTitle';
import { AssistantPanel } from './AssistantPanel';
import { useAssistantContext, useShareRisk } from './useAssistantContext';

const CAN = [
  'Explain the model output it was given',
  'List what would invalidate it',
  'Size a plan with your saved risk profile',
  'Compare 15m, 1h and 4h analyses',
  'Define terms such as Brier score or R : R',
];
const CANNOT = ['See news, the economic calendar or order books', 'Predict prices beyond the model output', 'Place, change or close any trade', 'Remember anything outside this browser'];

export function AssistantPage() {
  usePageTitle('Assistant');
  const { activeWorkspace, timeZone } = usePreferences();
  const [params, setParams] = useSearchParams();
  const sym = params.get('symbol') ?? '';
  const tf = params.get('tf') ?? '';
  const symbol: InstrumentSymbol = isInstrumentSymbol(sym) ? sym : activeWorkspace.symbol;
  const timeframe = isTimeframe(tf) ? tf : activeWorkspace.timeframe;
  const question = params.get('q');
  const [shareRisk, setShareRisk] = useShareRisk();
  const { context, loading, failed, reload } = useAssistantContext(symbol, timeframe, shareRisk);

  const set = (patch: Record<string, string | null>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v === null) next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: true },
    );
  const clearQuestion = useCallback(
    () =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete('q');
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5 px-4 py-5 sm:px-6 lg:h-full">
      <PageHeader
        eyebrow="07 · AI assistant"
        title="Assistant"
        description="Ask about the analysis on screen, what would invalidate it and what it means for your capital. It can only use the data listed as context."
      />
      <div className="grid grid-cols-[minmax(0,1fr)] min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-label="Conversation with the assistant" className="flex h-[85dvh] min-h-[520px] flex-col overflow-hidden rounded-xl border border-line bg-surface lg:h-auto">
          {loading ? (
            <div role="status" className="flex flex-1 items-center justify-center text-sm text-fg-3">
              Loading the context for the assistant…
            </div>
          ) : (
            <AssistantPanel
              key={`${symbol}:${timeframe}`}
              context={context}
              shareRisk={shareRisk}
              onShareRisk={setShareRisk}
              initialQuestion={question}
              onInitialQuestionSent={clearQuestion}
              timeZone={timeZone}
            />
          )}
        </section>

        <aside aria-label="Assistant context" className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
            <p className="eyebrow">Focus</p>
            <Field label="Instrument">
              {({ id }) => (
                <Select id={id} value={symbol} onChange={(e) => set({ symbol: e.target.value })}>
                  {INSTRUMENTS.map((i) => (
                    <option key={i.symbol} value={i.symbol}>
                      {i.display}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-fg">Timeframe</span>
              <SegmentedControl label="Timeframe" value={timeframe} options={TIMEFRAMES.map((t) => ({ value: t.id, label: t.label }))} onChange={(v) => set({ tf: v })} size="md" />
            </div>
            {failed > 0 && (
              <div role="alert" className="flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2 text-xs text-fg">
                <AlertTriangle aria-hidden className="mt-0.5 size-3.5 shrink-0 text-warning" />
                <span className="flex-1">Part of the context could not be loaded, so the assistant will say it is missing.</span>
                <Button size="sm" variant="ghost" icon={RotateCw} onClick={reload}>
                  Retry
                </Button>
              </div>
            )}
          </div>
          <div className="rounded-xl border border-line bg-surface p-4">
            <p className="eyebrow mb-2.5">It can</p>
            <ul className="flex flex-col gap-1.5 text-sm text-fg-2">
              {CAN.map((c) => (
                <li key={c} className="flex gap-2">
                  <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0 text-fg-3" /> {c}
                </li>
              ))}
            </ul>
            <p className="eyebrow mt-4 mb-2.5">It cannot</p>
            <ul className="flex flex-col gap-1.5 text-sm text-fg-2">
              {CANNOT.map((c) => (
                <li key={c} className="flex gap-2">
                  <Ban aria-hidden className="mt-0.5 size-4 shrink-0 text-fg-3" /> {c}
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
