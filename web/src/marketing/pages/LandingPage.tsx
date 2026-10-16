import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { useSelectedPlan, membershipStore } from '@/app/membershipStore';
import { buttonClasses } from '@/components/ui/buttonClasses';
import type { PlanId } from '@/domain/membership';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';
import { Reveal, RevealText } from '@/motion/Reveal';
import { PlanConfirmSheet } from '../membership/PlanConfirmSheet';
import { PlanGrid } from '../membership/PlanComponents';
import { ChartToPlanSequence } from '../sections/ChartToPlanSequence';
import { GENERAL_FAQ } from '../content';
import { FinalCta, Faq } from '../sections/Closing';
import { EcosystemSequence } from '../sections/EcosystemSequence';
import { EvidenceSection } from '../sections/EvidenceSection';
import { Hero } from '../sections/Hero';
import { ProblemSequence } from '../sections/ProblemSequence';
import { RiskSection } from '../sections/RiskSection';
import { SignalsAssistantSection } from '../sections/SignalsAssistantSection';

/** Sequence E — the story concludes in the membership options. */
function MembershipPreview() {
  const selected = useSelectedPlan();
  const [confirm, setConfirm] = useState<PlanId | null>(null);
  const pick = (id: PlanId) => {
    membershipStore.select(id);
    setConfirm(id);
  };
  return (
    <section id="membership" data-section aria-labelledby="membership-title" className="border-b border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="eyebrow mb-3">07 · Membership</p>
            <RevealText as="h2" id="membership-title" className="display text-d3 text-fg sm:text-d2" lines={['Choose how much', <em key="e">of the desk you need.</em>]} />
            <Reveal as="p" delay={150} className="mt-4 max-w-2xl text-md text-fg-2">
              Every plan includes the risk tools and the model’s track record. Plans differ in breadth and personalisation. Pricing has not been announced.
            </Reveal>
          </div>
          <Link to="/membership#compare" viewTransition className={buttonClasses({ variant: 'secondary', shape: 'pill', className: 'bg-transparent' })}>
            Compare every feature <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
        <div className="mt-12">
          <PlanGrid selected={selected} onSelect={pick} />
        </div>
      </div>
      <PlanConfirmSheet plan={confirm} onClose={() => setConfirm(null)} />
    </section>
  );
}

export function LandingPage() {
  useDocumentMeta({
    title: 'AI Trading Assistance',
    description:
      'A research platform for gold and FX: charts, an AI model’s assessment with its evidence, and position sizing against your own limits. Analysis only — it never trades for you.',
    path: '/',
  });
  return (
    <>
      <Hero />
      <ProblemSequence />
      <EcosystemSequence />
      <ChartToPlanSequence />
      <RiskSection />
      <SignalsAssistantSection />
      <EvidenceSection />
      <MembershipPreview />
      <Faq items={GENERAL_FAQ} />
      <FinalCta />
    </>
  );
}
