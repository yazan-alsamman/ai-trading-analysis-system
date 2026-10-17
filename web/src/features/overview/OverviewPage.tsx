import { ArrowRight, ArrowUpRight, Ban, CircleDot, FlaskConical, PlugZap, ShieldCheck } from 'lucide-react';
import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { ChangeText, DirectionBadge, FeedStatusPill } from '@/components/ui/Market';
import { SectionHeading } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/StateViews';
import { SourceTag } from '@/components/ui/SourceTag';
import { getInstrument } from '@/domain/instruments';
import { computePredictionStats } from '@/domain/predictions';
import { evaluateLimits, remainingRiskCapacity } from '@/domain/risk';
import { sessionSummary } from '@/domain/sessions';
import { evaluateSignal } from '@/domain/signalProfile';
import { useNow } from '@/hooks/useEnvironment';
import { useLiveCandles, useLiveQuotes } from '@/hooks/useMarketData';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { MODULES, type ModuleState } from '@/layouts/navigation';
import { cn } from '@/lib/cn';
import { formatClock, formatDate, formatMoney, formatNumber, formatPercent, formatPercentChange, formatPrice, formatRiskReward } from '@/lib/format';
import { LimitMeter } from '../risk/LimitMeter';
import { ResearchChart } from './ResearchChart';

const FOCUS = 'XAUUSD' as const;
/** The hero shows the first timeframe on which the model currently detects a setup (1h preferred). */
const TF_PREFERENCE = ['1h', '4h', '15m'] as const;

const STATE_STYLE: Record<ModuleState, { icon: typeof CircleDot; cls: string }> = {
  working: { icon: ShieldCheck, cls: 'text-fg' },
  simulated: { icon: FlaskConical, cls: 'text-demo' },
  rules: { icon: FlaskConical, cls: 'text-demo' },
  pending: { icon: PlugZap, cls: 'text-warning' },
};

function GlanceCard({
  eyebrow,
  title,
  to,
  cta,
  children,
  tag,
}: {
  eyebrow: string;
  title: string;
  to: string;
  cta: string;
  children: React.ReactNode;
  tag?: React.ReactNode;
}) {
  return (
    <section aria-label={title} className="flex min-w-0 flex-col rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3 className="mt-1.5 text-md font-semibold text-fg">{title}</h3>
        </div>
        {tag}
      </div>
      <div className="mt-4 flex-1">{children}</div>
      <Link to={to} className="mt-5 inline-flex items-center gap-1.5 self-start text-sm font-medium text-fg underline-offset-4 hover:underline">
        {cta} <ArrowRight aria-hidden className="size-3.5" />
      </Link>
    </section>
  );
}

export function OverviewPage() {
  usePageTitle('Overview');
  const services = useServices();
  const { prefs, timeZone, updateWorkspace } = usePreferences();
  const navigate = useNavigate();
  const now = useNow(1000);
  const inst = getInstrument(FOCUS);
  const focusOpp = useResource(`overview-opp:${FOCUS}`, (signal) => services.opportunities.list({ symbol: FOCUS }, { signal }));
  const byTf = new Map((focusOpp.data ?? []).map((o) => [o.timeframe, o] as const));
  const FOCUS_TF = TF_PREFERENCE.find((tf) => byTf.get(tf)?.status === 'detected') ?? '1h';
  const live = useLiveCandles(FOCUS, FOCUS_TF);
  const quotes = useLiveQuotes();
  const all = useResource('opportunities:all', (signal) => services.opportunities.list({}, { signal }));
  const history = useResource('predictions:history', (signal) => services.predictions.listHistory({ signal }));

  const candles = useMemo(() => live.candles.slice(-72), [live.candles]);
  const lastCandle = candles[candles.length - 1];
  const quote = quotes.quotes.get(FOCUS);
  const price = quote?.price ?? lastCandle?.close;
  const changeRatio = quote ? (quote.price - quote.reference) / quote.reference : null;
  const main = byTf.get(FOCUS_TF) ?? null;
  const stats = useMemo(() => (history.data ? computePredictionStats(history.data) : null), [history.data]);
  const risk = prefs.riskProfile;
  const capacity = remainingRiskCapacity(risk);
  // `now` ticks every second; signal freshness only needs minute precision.
  const minute = Math.floor(now / 60_000);
  const matches = useMemo(
    () =>
      (all.data ?? [])
        .map((o) => ({
          o,
          e: evaluateSignal(o, prefs.signalProfile, risk, minute * 60_000),
        }))
        .filter((x) => x.e.matches),
    [all.data, prefs.signalProfile, risk, minute],
  );
  const isDemo = services.source === 'demo';
  const provenance = live.resource.data?.provenance ?? (isDemo ? 'demo' : 'live');

  const openWorkspace = () => {
    updateWorkspace({
      symbol: FOCUS,
      timeframe: FOCUS_TF,
      showOpportunityOverlay: true,
    });
    navigate('/workspace');
  };

  const chartSummary = main
    ? `${inst.display} ${FOCUS_TF}: last ${candles.length} closes up to now, then the model's levels${main.forecast?.length ? ' and its projected path' : ''} to the right of the NOW line.`
    : `${inst.display} ${FOCUS_TF}: last ${candles.length} closes.`;

  return (
    <div className="flex flex-col">
      {/* ---------------------------------------------------------- hero */}
      <section aria-labelledby="overview-title" className="atmosphere border-b border-line">
        <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1400px] items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:py-14 xl:gap-16">
          <div className="reveal flex flex-col gap-6">
            <p className="eyebrow flex items-center gap-2">
              <span aria-hidden className="size-1.5 rounded-full bg-accent" />
              Gold &amp; FX research · {formatDate(now, timeZone)}
            </p>
            <SectionHeading level={1} id="overview-title" title="Read the market. Weigh the model." muted="Size the risk." />
            <p className="max-w-xl text-md text-fg-2">
              A research terminal for short-term gold and FX decisions. Price behaviour, the AI model’s assessment and your own capital limits sit side by side
              — each labelled for what it is, so you decide with the evidence in view. It never places a trade.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={openWorkspace}
                className={buttonClasses({
                  variant: 'primary',
                  size: 'lg',
                  shape: 'pill',
                })}
              >
                Open {inst.display} workspace <ArrowRight aria-hidden className="size-4" />
              </button>
              <Link
                to="/risk"
                className={buttonClasses({
                  variant: 'secondary',
                  size: 'lg',
                  shape: 'pill',
                  className: 'bg-transparent',
                })}
              >
                Plan a trade
              </Link>
            </div>
            <dl className="mt-2 grid max-w-xl grid-cols-2 gap-x-6 gap-y-3 border-t border-line pt-5 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-fg-3">Data</dt>
                <dd className={cn('mt-0.5 font-medium', isDemo ? 'text-demo' : 'text-fg')}>{isDemo ? 'Simulated' : 'Backend'}</dd>
              </div>
              <div>
                <dt className="text-xs text-fg-3">Feed</dt>
                <dd className="mt-0.5">
                  <FeedStatusPill status={live.feedStatus} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-fg-3">Session</dt>
                <dd className="mt-0.5 truncate text-fg-2">{sessionSummary(now)}</dd>
              </div>
              <div>
                <dt className="text-xs text-fg-3">UTC</dt>
                <dd className="num mt-0.5 text-fg">{formatClock(now, 'UTC')}</dd>
              </div>
            </dl>
          </div>

          {/* Research card: real data, labelled */}
          <figure
            aria-label={`${inst.display} research card`}
            className="reveal reveal-2 rounded-2xl border border-line-strong bg-surface/90 shadow-float backdrop-blur"
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
              <div>
                <p className="flex items-center gap-2 text-sm font-semibold text-fg">
                  {inst.display} <span className="font-normal text-fg-3">· {FOCUS_TF}</span>
                </p>
                <p className="mt-1 flex items-baseline gap-2.5">
                  <span className="num text-xl text-fg">{formatPrice(price, inst.pricePrecision)}</span>
                  {changeRatio !== null && <ChangeText value={changeRatio} text={formatPercentChange(changeRatio)} className="text-sm" />}
                </p>
              </div>
              <SourceTag kind={provenance === 'demo' ? 'demo' : 'live'} />
            </div>
            <div className="px-3 pt-3">
              {live.resource.status === 'loading' || candles.length < 2 ? (
                <Skeleton className="mx-2 h-56" />
              ) : (
                <ResearchChart candles={candles} timeframe={FOCUS_TF} opportunity={main} precision={inst.pricePrecision} summary={chartSummary} />
              )}
            </div>
            <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-5 py-3.5 text-xs text-fg-3">
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className="h-0.5 w-4 rounded-full bg-fg" /> Observed
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className="w-4 border-t-2 border-dashed border-forecast" /> Model projection
                {main && main.status === 'detected' && !main.forecast?.length ? ' (none supplied)' : ''}
              </span>
              <span className="ml-auto flex items-center gap-2">
                {main?.status === 'detected' ? (
                  <>
                    <DirectionBadge direction={main.direction} />
                    <span className="num text-forecast">{formatPercent(main.probability)}</span>
                    <span className="num">{formatRiskReward(main.riskReward)}</span>
                  </>
                ) : main ? (
                  <Badge>No opportunity</Badge>
                ) : (
                  <span>Model output loading…</span>
                )}
              </span>
            </figcaption>
          </figure>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-16 px-4 py-12 sm:px-6">
        {/* ------------------------------------------------------ workflow */}
        <section aria-labelledby="workflow-title" className="flex flex-col gap-8">
          <SectionHeading
            id="workflow-title"
            eyebrow="The platform"
            title="Seven modules."
            muted="One research workflow."
            description="Each module answers one question on the way from market noise to a decision you can justify. The status tells you what each runs on today."
          />
          <ol className="grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
            {MODULES.map((m) => {
              const st = m.status(services.source);
              const S = STATE_STYLE[st.state];
              return (
                <li key={m.n} className="bg-surface">
                  <Link to={m.to} className="group flex h-full flex-col gap-3 p-5 transition-colors hover:bg-raised focus-visible:bg-raised">
                    <div className="flex items-center justify-between">
                      <span className="num text-xs text-fg-3">{m.n}</span>
                      <ArrowUpRight
                        aria-hidden
                        className="size-4 text-fg-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-fg"
                      />
                    </div>
                    <div>
                      <h3 className="text-md font-semibold text-fg">{m.name}</h3>
                      <p className="display mt-0.5 text-lg text-fg-2 italic">{m.question}</p>
                    </div>
                    <p className="flex-1 text-sm text-fg-3">{m.summary}</p>
                    <p className={cn('inline-flex items-center gap-1.5 text-xs font-medium', S.cls)}>
                      <S.icon aria-hidden className="size-3.5" />
                      {st.label}
                    </p>
                  </Link>
                </li>
              );
            })}
            <li className="flex flex-col gap-3 bg-inset p-5">
              <span className="num text-xs text-fg-3">—</span>
              <h3 className="text-md font-semibold text-fg">What it never does</h3>
              <ul className="flex flex-col gap-1.5 text-sm text-fg-2">
                {['Place, modify or close trades', 'Promise profit or certainty', 'Show simulated data unlabelled', 'Guess broker specifications'].map((t) => (
                  <li key={t} className="flex gap-2">
                    <Ban aria-hidden className="mt-0.5 size-3.5 shrink-0 text-fg-3" />
                    {t}
                  </li>
                ))}
              </ul>
            </li>
          </ol>
        </section>

        {/* ----------------------------------------------------- at a glance */}
        <section aria-labelledby="glance-title" className="flex flex-col gap-8">
          <SectionHeading id="glance-title" eyebrow="Today" title="Where things stand." muted="With sources." />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <GlanceCard
              eyebrow="03 · Research"
              title="Gold across timeframes"
              to="/workspace"
              cta="Open the chart"
              tag={focusOpp.data?.[0]?.provenance === 'demo' ? <SourceTag kind="demo" /> : <SourceTag kind="model" />}
            >
              {focusOpp.status === 'loading' ? (
                <Skeleton className="h-24 w-full" />
              ) : focusOpp.data ? (
                <ul className="flex flex-col divide-y divide-line">
                  {(['15m', '1h', '4h'] as const).map((tf) => {
                    const o = byTf.get(tf);
                    return (
                      <li key={tf} className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
                        <span className="num w-8 text-sm text-fg-2">{tf}</span>
                        {o?.status === 'detected' ? (
                          <>
                            <DirectionBadge direction={o.direction} />
                            <span className="num ml-auto text-sm text-forecast">{formatPercent(o.probability)}</span>
                          </>
                        ) : (
                          <span className="text-sm text-fg-3">No opportunity</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-sm text-fg-2">The model output could not be loaded.</p>
              )}
              <p className="mt-3 text-xs text-fg-3">Probability that the target is reached before the stop, per timeframe. Not a guarantee.</p>
            </GlanceCard>

            <GlanceCard
              eyebrow="04 · Risk"
              title="Your risk budget"
              to="/risk"
              cta={risk.capital ? 'Plan a trade' : 'Set your capital'}
              tag={<SourceTag kind="user" />}
            >
              {risk.capital && capacity ? (
                <div className="flex flex-col gap-4">
                  <div>
                    <p className="text-xs text-fg-3">Next trade may risk up to</p>
                    <p className="num mt-0.5 text-xl text-fg">{formatMoney(capacity.money, risk.currency)}</p>
                  </div>
                  {(() => {
                    const daily = evaluateLimits(risk, null).find((l) => l.id === 'daily_loss');
                    return daily ? <LimitMeter check={daily} currency={risk.currency} showTrade={false} /> : null;
                  })()}
                </div>
              ) : (
                <p className="text-sm text-fg-2">
                  No capital is set, so nothing is sized and no limit is checked. The platform never assumes a balance — enter yours to unlock sizing across
                  Signals and the Assistant.
                </p>
              )}
            </GlanceCard>

            <GlanceCard
              eyebrow="05 · Signals"
              title="Matching your profile"
              to="/signals?view=for-you"
              cta="See your signals"
              tag={all.data?.[0]?.provenance === 'demo' ? <SourceTag kind="demo" /> : undefined}
            >
              {all.status === 'loading' ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                <>
                  <p className="num text-xl text-fg">
                    {matches.length} <span className="font-sans text-sm text-fg-3">of {all.data?.length ?? 0} analyses</span>
                  </p>
                  <ul className="mt-3 flex flex-col gap-1.5">
                    {matches
                      .sort((a, b) => b.o.probability - a.o.probability)
                      .slice(0, 3)
                      .map(({ o }) => (
                        <li key={o.id} className="flex items-center gap-2 text-sm">
                          <span className="text-fg">{getInstrument(o.symbol).display}</span>
                          <span className="num text-fg-3">{o.timeframe}</span>
                          <DirectionBadge direction={o.direction} className="ml-auto" />
                          <span className="num w-10 text-right text-forecast">{formatPercent(o.probability)}</span>
                        </li>
                      ))}
                    {matches.length === 0 && <li className="text-sm text-fg-2">Nothing passes every check right now. That is a valid answer.</li>}
                  </ul>
                </>
              )}
            </GlanceCard>

            <GlanceCard
              eyebrow="06 · Insights"
              title="Model track record"
              to="/insights"
              cta="See calibration"
              tag={history.data?.[0]?.provenance === 'demo' ? <SourceTag kind="demo" /> : <SourceTag kind="historical" />}
            >
              {history.status === 'loading' ? (
                <Skeleton className="h-24 w-full" />
              ) : stats && stats.resolved > 0 ? (
                <>
                  <dl className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="text-xs text-fg-3" title="Target reached ÷ resolved predictions">
                        Hit rate
                      </dt>
                      <dd className="num mt-0.5 text-xl text-fg">{formatPercent(stats.hitRate)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-fg-3" title="Mean squared error of probability vs outcome. Lower is better; 0.25 = coin flip.">
                        Brier score
                      </dt>
                      <dd className="num mt-0.5 text-xl text-fg">{formatNumber(stats.brierScore, 3)}</dd>
                    </div>
                  </dl>
                  <p className="mt-4 text-xs text-fg-3">
                    Over {stats.resolved} resolved predictions (mean stated probability {formatPercent(stats.meanPredicted)}). Brier: lower is better, 0.25 is a
                    coin flip.
                  </p>
                </>
              ) : (
                <p className="text-sm text-fg-2">No resolved predictions yet, so no accuracy can be reported.</p>
              )}
            </GlanceCard>
          </div>
        </section>

        <p className="border-t border-line pt-6 text-xs text-fg-3">
          Analysis and decision support only — not financial advice.{' '}
          {isDemo ? 'All market data, model outputs and statistics on this page are simulated in the browser. ' : ''}
          Model probabilities describe the chance of reaching the target before the stop within the model’s horizon, and they can be wrong.
        </p>
      </div>
    </div>
  );
}
