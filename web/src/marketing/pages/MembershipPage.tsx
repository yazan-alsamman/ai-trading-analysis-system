import { ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { membershipStore, useSelectedPlan } from '@/app/membershipStore';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { isPlanId, type PlanId } from '@/domain/membership';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';
import { Reveal, RevealText } from '@/motion/Reveal';
import { PlanConfirmSheet } from '../membership/PlanConfirmSheet';
import { CompareTable, PlanFit, PlanGrid, StatusLegend } from '../membership/PlanComponents';
import { MEMBERSHIP_FAQ } from '../content';
import { Faq } from '../sections/Closing';

const WHY = [
  ['One honest workflow', 'Market context, the model’s assessment, its evidence and your risk in one place — with every number sourced.'],
  ['Transparency in every plan', 'Model analytics and the full risk toolkit are never paywalled.'],
  ['Clear about what is real', 'Each feature says whether it works now, runs on demo data, needs the backend or is still planned.'],
] as const;

export function MembershipPage() {
  useDocumentMeta({
    title: 'Membership',
    description: 'Compare the Essential, Professional and Elite research plans — what each includes and what every feature runs on today. Pricing to be announced.',
    path: '/membership',
  });
  const [params] = useSearchParams();
  const selected = useSelectedPlan();
  const [confirm, setConfirm] = useState<PlanId | null>(null);

  // ?plan=… preselects a plan (validated); never trusted for anything but display.
  const fromUrl = params.get('plan');
  useEffect(() => {
    if (isPlanId(fromUrl)) membershipStore.select(fromUrl);
  }, [fromUrl]);

  const pick = (id: PlanId) => {
    membershipStore.select(id);
    setConfirm(id);
  };

  return (
    <>
      <section aria-labelledby="mem-title" className="atmosphere border-b border-line pt-32 pb-16">
        <div className="mx-auto max-w-[1240px] px-5 sm:px-8">
          <p className="eyebrow m-in mb-4" style={{ '--at': '0ms' } as React.CSSProperties}>
            Membership
          </p>
          <RevealText as="h1" id="mem-title" trigger="mount" delay={60} className="display max-w-4xl text-d2 text-fg sm:text-d1" lines={['One research desk.', <em key="e">Three ways in.</em>]} />
          <p className="m-in-blur mt-6 max-w-2xl text-md text-fg-2" style={{ '--at': '450ms' } as React.CSSProperties}>
            Choose the breadth you need. Every plan is honest about what runs today: some modules use demo data until the backend is connected, and no plan can be paid for
            yet.
          </p>
          <ul className="mt-10 grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-3">
            {WHY.map(([t, d], i) => (
              <li key={t} className="m-in rounded-xl border border-line bg-surface/70 p-5" style={{ '--at': `${650 + i * 90}ms` } as React.CSSProperties}>
                <p className="text-md font-medium text-fg">{t}</p>
                <p className="mt-1 text-sm text-fg-2">{d}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="plans" data-section aria-labelledby="plans-title" className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-20 sm:px-8">
          <h2 id="plans-title" className="sr-only">
            Plans
          </h2>
          <PlanGrid selected={selected} onSelect={pick} />
          <Reveal className="mt-10">
            <p className="eyebrow mb-3">Not sure? Answer three questions</p>
            <PlanFit onPick={pick} />
          </Reveal>
        </div>
      </section>

      <section id="compare" data-section aria-labelledby="compare-title" className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-20 sm:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow mb-3">Compare plans</p>
              <RevealText as="h2" id="compare-title" className="display text-d3 text-fg sm:text-d2" lines={['Every feature,', <em key="e">and what it runs on today.</em>]} />
            </div>
          </div>
          <Reveal className="mt-6">
            <StatusLegend />
          </Reveal>
          <Reveal className="mt-8">
            <CompareTable highlight={selected} />
          </Reveal>
          <Reveal className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-line bg-surface p-6">
            <div>
              <p className="text-md font-medium text-fg">{selected ? 'Ready when you are.' : 'Pick a plan to continue.'}</p>
              <p className="text-sm text-fg-2">Already have an account? Sign in — your selection comes with you.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to={selected ? `/login?plan=${selected}` : '/login'} viewTransition className={buttonClasses({ variant: 'secondary', shape: 'pill', className: 'bg-transparent' })}>
                Sign in
              </Link>
              <Link to={selected ? `/register?plan=${selected}` : '/register'} viewTransition className={buttonClasses({ variant: 'primary', shape: 'pill' })}>
                Create account <ArrowRight aria-hidden className="size-4" />
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <Faq items={MEMBERSHIP_FAQ} title="About access. Answered plainly." eyebrow="Membership FAQ" id="membership-faq" />
      <PlanConfirmSheet plan={confirm} onClose={() => setConfirm(null)} />
    </>
  );
}
