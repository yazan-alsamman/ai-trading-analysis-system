import { Check, Minus } from 'lucide-react';
import { useState } from 'react';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { FEATURES, formatPrice, getPlan, PLANS, STATUS_LABELS, suggestPlan, type Access, type FeatureGroup, type FeatureStatus, type FitAnswers, type Plan, type PlanId } from '@/domain/membership';
import { cn } from '@/lib/cn';
import { Reveal } from '@/motion/Reveal';

const STATUS_TONE: Record<FeatureStatus, BadgeTone> = { available: 'accent', demo: 'demo', backend: 'warning', planned: 'neutral' };

export function StatusBadge({ status }: { status: FeatureStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]} title={STATUS_LABELS[status].description}>
      {STATUS_LABELS[status].label}
    </Badge>
  );
}

export function StatusLegend() {
  return (
    <ul aria-label="What each status means" className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-fg-3">
      {(Object.keys(STATUS_LABELS) as FeatureStatus[]).map((s) => (
        <li key={s} className="flex items-center gap-2">
          <StatusBadge status={s} />
          <span>{STATUS_LABELS[s].description}</span>
        </li>
      ))}
    </ul>
  );
}

function AccessCell({ access }: { access: Access }) {
  if (access === false)
    return (
      <span className="inline-flex items-center gap-1.5 text-fg-3">
        <Minus aria-hidden className="size-4" />
        <span className="sr-only">Not included</span>
      </span>
    );
  if (access === true)
    return (
      <span className="inline-flex items-center gap-1.5 text-fg">
        <Check aria-hidden className="size-4 text-accent" />
        <span className="sr-only">Included</span>
      </span>
    );
  return <span className="text-sm text-fg">{access}</span>;
}

/** One plan, selectable. Selection uses the spring curve and a gold hairline. */
export function PlanCard({ plan, selected, onSelect, index = 0 }: { plan: Plan; selected: boolean; onSelect: (id: PlanId) => void; index?: number }) {
  return (
    <Reveal
      index={index}
      stagger={110}
      className={cn(
        'plan-card relative flex flex-col rounded-2xl border bg-surface p-6',
        selected ? 'border-accent shadow-glow-aurum' : 'border-line hover:border-line-strong',
      )}
    >
      <div data-selected={selected} className="plan-card-inner flex h-full flex-col">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow">{`0${index + 1}`}</p>
            <h3 className="display mt-1 text-d3 text-fg">{plan.name}</h3>
          </div>
          <span aria-hidden className={cn('plan-check inline-flex size-7 items-center justify-center rounded-full bg-accent text-accent-fg', !selected && 'scale-0 opacity-0')}>
            <Check className="size-4" />
          </span>
        </div>
        <p className="mt-2 text-md text-fg">{plan.tagline}</p>
        <p className="mt-1 text-sm text-fg-3">{plan.audience}</p>
        <div className="mt-5 border-y border-line py-4">
          <p className="text-lg font-semibold text-fg">{formatPrice(plan.price)}</p>
          <p className="mt-0.5 text-xs text-fg-3">No commercial terms have been set. No payment is taken.</p>
        </div>
        <ul className="mt-5 flex flex-1 flex-col gap-2.5">
          {plan.highlights.map((h) => (
            <li key={h} className="flex gap-2 text-sm text-fg-2">
              <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" /> {h}
            </li>
          ))}
        </ul>
        <button
          type="button"
          role="radio"
          aria-checked={selected}
          onClick={() => onSelect(plan.id)}
          className={cn(
            'mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full border text-md font-medium transition-[background-color,color,border-color,transform] duration-150 active:translate-y-px',
            selected ? 'border-transparent bg-primary text-primary-fg' : 'border-line-strong text-fg hover:bg-hover',
          )}
        >
          {selected ? (
            <>
              <Check aria-hidden className="size-4" /> {plan.name} selected
            </>
          ) : (
            plan.cta
          )}
        </button>
      </div>
    </Reveal>
  );
}

export function PlanGrid({ selected, onSelect }: { selected: PlanId | null; onSelect: (id: PlanId) => void }) {
  return (
    <div role="radiogroup" aria-label="Membership plans" className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-3">
      {PLANS.map((p, i) => (
        <PlanCard key={p.id} plan={p} index={i} selected={selected === p.id} onSelect={onSelect} />
      ))}
    </div>
  );
}

const GROUPS: FeatureGroup[] = ['Research', 'Personalisation', 'Risk & review', 'Assistant & workflow'];

/** Full comparison: table on wide screens, one plan at a time on phones. */
export function CompareTable({ highlight }: { highlight: PlanId | null }) {
  const [mobilePlan, setMobilePlan] = useState<PlanId>(highlight ?? 'professional');
  const shownMobile = getPlan(mobilePlan);
  return (
    <div>
      {/* Phones and small tablets */}
      <div className="md:hidden">
        <div role="tablist" aria-label="Plan to compare" className="grid grid-cols-3 rounded-full border border-line bg-surface p-1">
          {PLANS.map((p) => (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={mobilePlan === p.id}
              onClick={() => setMobilePlan(p.id)}
              className={cn('h-9 rounded-full text-sm font-medium transition-colors', mobilePlan === p.id ? 'bg-primary text-primary-fg' : 'text-fg-2')}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div className="mt-4 flex flex-col gap-6">
          {GROUPS.map((g) => (
            <section key={g} aria-label={g}>
              <p className="eyebrow mb-2">{g}</p>
              <ul className="flex flex-col divide-y divide-line rounded-xl border border-line bg-surface">
                {FEATURES.filter((f) => f.group === g).map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <span className="min-w-0">
                      <span className="block text-sm text-fg">{f.label}</span>
                      <span className="mt-1 block">
                        <StatusBadge status={f.status} />
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      {shownMobile.access[f.id] === false ? <span className="text-sm text-fg-3">Not included</span> : <AccessCell access={shownMobile.access[f.id]} />}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>

      {/* Tablets and up */}
      <div className="hidden overflow-hidden rounded-2xl border border-line bg-surface md:block">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Features included in each membership plan, with what each feature runs on today</caption>
          <thead>
            <tr className="border-b border-line">
              <th scope="col" className="px-5 py-4 text-left text-xs font-medium text-fg-3">
                Feature
              </th>
              <th scope="col" className="px-3 py-4 text-left text-xs font-medium text-fg-3">
                Today
              </th>
              {PLANS.map((p) => (
                <th
                  key={p.id}
                  scope="col"
                  className={cn('px-4 py-4 text-left transition-colors duration-300', highlight === p.id && 'bg-accent-soft')}
                >
                  <span className="display block text-xl text-fg">{p.name}</span>
                  {highlight === p.id && <span className="text-xs font-medium text-accent">Your selection</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {GROUPS.map((g) => (
              <GroupRows key={g} group={g} highlight={highlight} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GroupRows({ group, highlight }: { group: FeatureGroup; highlight: PlanId | null }) {
  return (
    <>
      <tr>
        <th scope="colgroup" colSpan={2 + PLANS.length} className="bg-inset px-5 py-2 text-left">
          <span className="eyebrow">{group}</span>
        </th>
      </tr>
      {FEATURES.filter((f) => f.group === group).map((f) => (
        <tr key={f.id} className="border-t border-line">
          <th scope="row" className="px-5 py-3 text-left font-normal">
            <span className="block text-fg">{f.label}</span>
            <span className="block text-xs text-fg-3">{f.detail}</span>
          </th>
          <td className="px-3 py-3 align-middle">
            <StatusBadge status={f.status} />
          </td>
          {PLANS.map((p) => (
            <td key={p.id} className={cn('px-4 py-3 align-middle transition-colors duration-300', highlight === p.id && 'bg-accent-soft')}>
              <AccessCell access={p.access[f.id]} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

function Choice({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn('h-9 rounded-full border px-4 text-sm transition-colors duration-150', on ? 'border-accent bg-accent-soft text-fg' : 'border-line text-fg-2 hover:text-fg')}
    >
      {label}
    </button>
  );
}

/** Three questions → the smallest plan that covers the answers. */
export function PlanFit({ onPick }: { onPick: (id: PlanId) => void }) {
  const [a, setA] = useState<FitAnswers>({ instruments: 'gold', personalise: false, assistant: false });
  const suggestion = getPlan(suggestPlan(a));
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 rounded-2xl border border-line bg-surface p-6 lg:grid-cols-[1fr_auto] lg:items-center">
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-sm text-fg-2">What do you trade?</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Choice label="Gold only" on={a.instruments === 'gold'} onClick={() => setA({ ...a, instruments: 'gold' })} />
            <Choice label="Gold and FX majors" on={a.instruments === 'gold_fx'} onClick={() => setA({ ...a, instruments: 'gold_fx' })} />
          </div>
        </div>
        <div>
          <p className="text-sm text-fg-2">Should setups be filtered by your own rules?</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Choice label="No" on={!a.personalise} onClick={() => setA({ ...a, personalise: false })} />
            <Choice label="Yes" on={a.personalise} onClick={() => setA({ ...a, personalise: true })} />
          </div>
        </div>
        <div>
          <p className="text-sm text-fg-2">Do you want the assistant?</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Choice label="No" on={!a.assistant} onClick={() => setA({ ...a, assistant: false })} />
            <Choice label="Yes" on={a.assistant} onClick={() => setA({ ...a, assistant: true })} />
          </div>
        </div>
      </div>
      <div aria-live="polite" className="rounded-xl border border-line-strong bg-inset p-5 lg:w-72">
        <p className="eyebrow">Smallest plan that fits</p>
        <p key={suggestion.id} className="display m-in mt-1 text-d3 text-fg">
          {suggestion.name}
        </p>
        <p className="mt-1 text-sm text-fg-2">{suggestion.tagline}</p>
        <button
          type="button"
          onClick={() => onPick(suggestion.id)}
          className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-full bg-primary px-4 text-sm font-medium text-primary-fg hover:bg-primary-hover"
        >
          Select {suggestion.name}
        </button>
      </div>
    </div>
  );
}
