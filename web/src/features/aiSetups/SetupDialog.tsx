import { CheckCircle2, Undo2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, FormError, Input } from '@/components/ui/Form';
import { Stat } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { SETUP_STATE_LABELS, type AISetup } from '@/domain/aiSetups';
import { formatAmount } from '@/features/backtests/backtestFormat';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatPct, MISSING } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { formatR, formatSetupPrice, NO_MODEL_HINT, STATE_TONE } from './setupFormat';

const SOURCE_LABEL: Record<string, string> = { profile: 'your risk profile', config: 'your risk settings', default: 'server default' };

/** One setup: the server's size for your account, its explanation, and your "taken" record. */
export function SetupDialog({ setup, onClose, onTakenChange }: { setup: AISetup; onClose: () => void; onTakenChange: () => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [lang, setLang] = useState<'en' | 'ar'>('en');
  const [lots, setLots] = useState('');
  const [entryPrice, setEntryPrice] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const size = useResource(`ai-size:${setup.setupId}`, (signal) => services.aiSetups.size(setup.setupId, { signal }));
  const explanation = useResource(`ai-explain:${setup.setupId}:${lang}`, (signal) => services.aiSetups.explanation(setup.setupId, lang, { signal }));
  const p = setup.instrument?.pricePrecision;

  const parse = (v: string) => (v.trim() === '' ? null : Number(v));
  const take = async () => {
    const l = parse(lots);
    const e = parse(entryPrice);
    if ((l !== null && !(l > 0)) || (e !== null && !(e > 0))) {
      setError('Lots and entry price must be positive numbers, or left empty.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await services.aiSetups.take(setup.setupId, { lots: l, entryPrice: e });
      notify('Recorded as taken. The platform did not place any order.', 'success');
      size.reload();
      onTakenChange();
    } catch (err) {
      setError(userMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const untake = async () => {
    setBusy(true);
    setError(null);
    try {
      await services.aiSetups.untake(setup.setupId);
      notify('Your "taken" record was removed.', 'info');
      size.reload();
      onTakenChange();
    } catch (err) {
      setError(userMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const taken = size.data?.taken === true;
  return (
    <Dialog
      open
      onClose={onClose}
      size="lg"
      title={`${setup.direction === 'buy' ? 'Buy' : 'Sell'} setup · ${setup.instrument?.symbol ?? 'Unknown instrument'}`}
      description="From the AI engine's setup rules (version 1 has no trained model). Analysis only: the platform never places, changes or closes a trade."
      footer={<Button onClick={onClose}>Close</Button>}
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATE_TONE[setup.state]}>{SETUP_STATE_LABELS[setup.state]}</Badge>
          {setup.profile && <Badge>{setup.profile}</Badge>}
          {setup.validUntil && <span className="text-xs text-fg-3">Entry valid until {formatDateTime(setup.validUntil, timeZone)}</span>}
        </div>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Entry" value={<span className="num">{formatSetupPrice(setup.entry, p)}</span>} />
          <Stat label="Stop" value={<span className="num">{formatSetupPrice(setup.sl, p)}</span>} />
          <Stat label="Target" value={<span className="num">{formatSetupPrice(setup.tp, p)}</span>} />
          <Stat label="Reward / risk" value={<span className="num">{setup.rMultiple === null ? MISSING : `${formatNumber(setup.rMultiple, 2)}R`}</span>} />
          <Stat label="Probability" value={<span title={setup.probability === null ? NO_MODEL_HINT : undefined}>{setup.probability === null ? 'Not provided' : formatPct(setup.probability * 100, 0)}</span>} />
          <Stat label="Expected value" value={<span title={setup.evR === null ? NO_MODEL_HINT : undefined}>{setup.evR === null ? 'Not provided' : formatR(setup.evR)}</span>} />
          <Stat label="Grade" value={<span title={setup.grade === null ? NO_MODEL_HINT : undefined}>{setup.grade ?? 'Not provided'}</span>} />
          <Stat label="Result" value={<span className="num">{formatR(setup.realizedR)}</span>} />
        </dl>

        <section aria-labelledby="ai-size-h" className="rounded-md border border-line p-3">
          <h3 id="ai-size-h" className="text-sm font-semibold text-fg">
            Size for your account
          </h3>
          {size.status === 'loading' ? (
            <Loading label="Sizing the setup">
              <SkeletonRows rows={2} className="mt-2" />
            </Loading>
          ) : size.status === 'error' ? (
            <ErrorState error={size.error} onRetry={size.reload} compact title="Could not size this setup" />
          ) : size.data ? (
            <div className="mt-2 flex flex-col gap-3">
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Lots" value={<span className="num">{formatNumber(size.data.lots, 2)}</span>} />
                <Stat label="Money at risk" value={<span className="num">{formatAmount(size.data.riskAmount, size.data.inputs.currency)}</span>} />
                <Stat label="Margin" value={<span className="num">{formatAmount(size.data.marginRequired, size.data.inputs.currency)}</span>} />
                <Stat label="Feasible" value={size.data.feasible ? 'Yes' : 'No'} />
              </dl>
              <p className="text-xs text-fg-3">
                Balance {formatAmount(size.data.inputs.balance, size.data.inputs.currency)} ({SOURCE_LABEL[size.data.inputs.sources.balance ?? ''] ?? 'server'}), risk{' '}
                {formatPct(size.data.inputs.riskPerTradePct)} per trade, leverage 1:{formatNumber(size.data.inputs.leverage, 0)}. Sized by{' '}
                {size.data.source === 'remote' ? 'the AI engine' : 'the backend'} at {formatDateTime(size.data.computedAt, timeZone)}. Change these in Capital &amp; risk.
              </p>
              {size.data.warnings.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-warning">
                  {size.data.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </section>

        <section aria-labelledby="ai-explain-h" className="rounded-md border border-line p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 id="ai-explain-h" className="text-sm font-semibold text-fg">
              Explanation
            </h3>
            <SegmentedControl
              label="Explanation language"
              value={lang}
              onChange={setLang}
              options={[
                { value: 'en', label: 'English' },
                { value: 'ar', label: 'العربية' },
              ]}
            />
          </div>
          {explanation.status === 'loading' ? (
            <Loading label="Loading the explanation">
              <SkeletonRows rows={2} className="mt-2" />
            </Loading>
          ) : explanation.status === 'error' ? (
            <ErrorState error={explanation.error} onRetry={explanation.reload} compact title="Could not load the explanation" />
          ) : explanation.data?.text ? (
            <p lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'} className="mt-2 text-sm leading-relaxed text-fg">
              {explanation.data.text}
            </p>
          ) : (
            <p className="mt-2 text-sm text-fg-3" lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
              {lang === 'ar' ? 'الشرح غير متاح' : 'Explanation unavailable'}
              <span className="block text-xs" lang="en" dir="ltr">
                Only explanations verified against the setup&apos;s numbers are shown.
              </span>
            </p>
          )}
        </section>

        <section aria-labelledby="ai-take-h" className="rounded-md border border-line p-3">
          <h3 id="ai-take-h" className="text-sm font-semibold text-fg">
            Your record
          </h3>
          <p className="mt-1 text-xs text-fg-3">
            If you took this trade at your broker, record it here to be told about its outcome and to track your results. Nothing is sent to a broker.
          </p>
          {taken ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Badge tone="up">
                <CheckCircle2 aria-hidden className="size-3" /> Taken
              </Badge>
              <Button size="sm" icon={Undo2} onClick={() => void untake()} loading={busy}>
                Remove my record
              </Button>
            </div>
          ) : (
            <form
              className="mt-3 flex flex-wrap items-end gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                void take();
              }}
            >
              <Field label="Lots" optional hint="Empty: the size above" className="w-full sm:w-36">
                {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} inputMode="decimal" value={lots} onChange={(e) => setLots(e.target.value)} />}
              </Field>
              <Field label="Your entry price" optional hint="Empty: the setup entry" className="w-full sm:w-44">
                {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} inputMode="decimal" value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} />}
              </Field>
              <Button type="submit" variant="primary" loading={busy} disabled={size.status === 'loading'}>
                I took this trade
              </Button>
            </form>
          )}
          <div className="mt-3">
            <FormError message={error} />
          </div>
        </section>
      </div>
    </Dialog>
  );
}
