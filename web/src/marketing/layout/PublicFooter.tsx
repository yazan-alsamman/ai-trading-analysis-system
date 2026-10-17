import { ArrowRight, ArrowUpRight, Bot, Smartphone } from 'lucide-react';
import { useRef, type CSSProperties } from 'react';
import { Link } from 'react-router';
import { useServices } from '@/app/contexts';
import { BrandMark } from '@/components/brand/BrandMark';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { APP_STORES, isSafeExternalUrl, SOCIAL_LINKS } from '@/config/externalLinks';
import { useInView } from '@/motion/runtime';
import { FOOTER_GROUPS } from '../content';
import { buildShowcase } from '../showcase';

/** The simulated close series as faint gold linework across the footer (decorative). */
function linework(): string {
  const closes = buildShowcase().candles.map((c) => c.close);
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  return closes.map((v, i) => `${i ? 'L' : 'M'}${((i / (closes.length - 1)) * 1200).toFixed(1)} ${(110 - ((v - lo) / (hi - lo || 1)) * 90).toFixed(1)}`).join(' ');
}

/** A small phone showing the product's mark — the app is in development, so no screen content is claimed. */
function PhoneMock() {
  return (
    <div aria-hidden className="relative h-36 w-[4.6rem] shrink-0 rounded-[1.1rem] border border-line-strong bg-canvas p-1 shadow-float">
      <div className="flex h-full flex-col items-center justify-center gap-2 rounded-[0.85rem] border border-line bg-surface">
        <span className="size-2 rounded-full bg-accent" />
        <span className="h-px w-8 bg-line-strong" />
        <span className="h-px w-6 bg-line" />
        <span className="h-px w-7 bg-line" />
      </div>
    </div>
  );
}

function AppDownload() {
  const anyLive = APP_STORES.some((s) => isSafeExternalUrl(s.url));
  return (
    <section aria-labelledby="footer-app" className="flex gap-5 rounded-2xl border border-line bg-canvas/60 p-5">
      <PhoneMock />
      <div className="flex min-w-0 flex-col gap-3">
        <div>
          <p id="footer-app" className="text-md font-semibold text-fg">
            Download the app
          </p>
          <p className="mt-1 text-xs leading-5 text-fg-3">
            {anyLive ? 'Research on the move, with the same evidence and labels.' : 'The Android and iOS apps are in development and not yet published. This page will link to the stores when they are.'}
          </p>
        </div>
        <ul className="flex flex-wrap gap-2">
          {APP_STORES.map((s) =>
            isSafeExternalUrl(s.url) ? (
              <li key={s.id}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-11 items-center gap-2.5 rounded-xl border border-line-strong bg-surface px-3.5 text-left hover:border-accent"
                >
                  <Smartphone aria-hidden className="size-4 text-fg-2" />
                  <span className="flex flex-col leading-tight">
                    <span className="text-[0.625rem] tracking-wide text-fg-3 uppercase">Get it on</span>
                    <span className="text-sm font-medium text-fg">{s.store}</span>
                  </span>
                  <span className="sr-only">(opens in a new tab)</span>
                </a>
              </li>
            ) : (
              <li key={s.id}>
                <span className="inline-flex h-11 items-center gap-2.5 rounded-xl border border-dashed border-line-strong px-3.5">
                  <Smartphone aria-hidden className="size-4 text-fg-3" />
                  <span className="flex flex-col leading-tight">
                    <span className="text-[0.625rem] tracking-wide text-fg-3 uppercase">{s.platform} · coming soon</span>
                    <span className="text-sm font-medium text-fg-2">
                      {s.store}
                      <span className="sr-only"> — not yet published</span>
                    </span>
                  </span>
                </span>
              </li>
            ),
          )}
        </ul>
      </div>
    </section>
  );
}

/**
 * Public footer: the closing chapter of every public page. Brand and next
 * steps, grouped navigation (only routes that exist), the app-download area
 * (honest "coming soon" until stores are configured), social links (only
 * verified ones — none yet), the risk disclaimer and asset credits.
 * Destinations live in src/config/externalLinks.ts and marketing/content.ts.
 */
export function PublicFooter() {
  const { source } = useServices();
  const lineRef = useRef<HTMLDivElement>(null);
  const lineIn = useInView(lineRef, { threshold: 0.2 });
  const year = 2026;

  return (
    <footer className="relative isolate overflow-hidden border-t border-line bg-surface">
      {/* Gold linework: the simulated price line, drawn once. */}
      <div ref={lineRef} aria-hidden data-play={lineIn} className="pointer-events-none absolute inset-x-0 top-0 -z-10 opacity-60">
        <svg viewBox="0 0 1200 120" preserveAspectRatio="none" className="h-28 w-full">
          <path
            d={linework()}
            fill="none"
            pathLength={1}
            vectorEffect="non-scaling-stroke"
            className="m-draw stroke-accent"
            strokeOpacity="0.35"
            strokeWidth="1"
            style={{ '--at': '0ms', '--dur': '2400ms', '--len': 1 } as CSSProperties}
          />
        </svg>
      </div>

      <div className="mx-auto max-w-[1240px] px-5 pt-20 pb-10 sm:px-8">
        {/* Brand and next step */}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-10 border-b border-line pb-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)] lg:items-end">
          <div className="flex flex-col gap-5">
            <BrandMark />
            <p className="display max-w-xl text-d3 leading-tight text-fg">
              Research first. <em>Then decide.</em>
            </p>
            <p className="max-w-lg text-sm leading-6 text-fg-2">
              A research platform for gold and FX: charts, a model’s assessment with its evidence, and position sizing against your own limits — every number labelled
              for where it came from. Analysis only; it never trades for you.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/membership#plans" viewTransition className={buttonClasses({ variant: 'primary', shape: 'pill' })}>
                Compare plans <ArrowRight aria-hidden className="size-4" />
              </Link>
              <Link to="/ai-assistant" viewTransition className={buttonClasses({ variant: 'secondary', shape: 'pill', className: 'bg-transparent' })}>
                <Bot aria-hidden className="size-4" /> Try the research assistant
              </Link>
            </div>
          </div>
          <AppDownload />
        </div>

        {/* Navigation */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 py-12 md:grid-cols-4">
          {FOOTER_GROUPS.map((g) => (
            <nav key={g.title} aria-label={`Footer: ${g.title}`} className="flex flex-col gap-2.5 text-sm">
              <p className="eyebrow mb-1">{g.title}</p>
              {g.links
                .filter((l) => !l.demoOnly || source === 'demo')
                .map((l) => (
                  <Link key={l.to} to={l.to} className="w-fit text-fg-2 underline-offset-4 transition-colors hover:text-fg hover:underline">
                    {l.label}
                  </Link>
                ))}
              {g.note && <p className="mt-1 max-w-[16rem] text-xs leading-5 text-fg-3">{g.note}</p>}
            </nav>
          ))}
        </div>

        {/* Social + status */}
        <div className="flex flex-col gap-4 border-t border-line pt-6 text-xs text-fg-3 md:flex-row md:items-center md:justify-between">
          {SOCIAL_LINKS.length > 0 ? (
            <ul aria-label="Social media" className="flex flex-wrap gap-2">
              {SOCIAL_LINKS.filter((s) => isSafeExternalUrl(s.url)).map((s) => (
                <li key={s.network}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line px-3 text-fg-2 hover:text-fg">
                    {s.label} <ArrowUpRight aria-hidden className="size-3" />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p>Social channels: none announced yet. Official accounts will be listed here once they exist.</p>
          )}
          <p>{source === 'demo' ? 'Demo mode: market data and model output on this site are simulated.' : 'Connected to the project backend.'}</p>
        </div>

        {/* Legal */}
        <div className="mt-6 flex flex-col gap-3 text-xs leading-5 text-fg-3">
          <p>
            <strong className="font-semibold text-fg-2">Risk disclaimer.</strong> Trading gold and foreign exchange carries a high level of risk and may not be suitable for
            everyone; you can lose more than you expect. AI Trading Assistance provides analysis and decision support only. It is not financial advice, it is not a broker,
            and it never places, modifies or closes trades. Model outputs are probabilistic estimates that can be wrong. Past or simulated results do not guarantee future
            results.{' '}
            <Link to="/legal/risk-disclosure" className="text-fg-2 underline underline-offset-2 hover:text-fg">
              Read the full risk disclosure
            </Link>
            .
          </p>
          <p>Background footage: licensed stock video from Coverr and Mixkit, for atmosphere only. The charts visible in it are not this platform’s data.</p>
          <p>
            © {year} AI Trading Assistance · Graduation project. Terms of service and a privacy policy are in preparation; until they are published, see{' '}
            <Link to="/legal/data-storage" className="text-fg-2 underline underline-offset-2 hover:text-fg">
              what this site stores in your browser
            </Link>
            .
          </p>
        </div>
      </div>
    </footer>
  );
}
