import { useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router';
import { BrandMark } from '@/components/brand/BrandMark';
import { useServices } from '@/app/contexts';
import { PUBLIC_NAV } from '../content';
import { PublicHeader } from './PublicHeader';

function PublicFooter() {
  const { source } = useServices();
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-[1240px] gap-10 px-5 py-14 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div className="flex flex-col gap-4">
          <BrandMark />
          <p className="max-w-xs text-sm text-fg-2">A research terminal for gold and FX: charts, a model’s assessment and your own risk limits, each labelled for where it came from.</p>
        </div>
        <nav aria-label="Platform" className="flex flex-col gap-2.5 text-sm">
          <p className="eyebrow mb-1">Platform</p>
          {PUBLIC_NAV.filter((n) => n.to.startsWith('/#')).map((n) => (
            <Link key={n.to} to={n.to} className="text-fg-2 hover:text-fg">
              {n.label}
            </Link>
          ))}
        </nav>
        <nav aria-label="Account" className="flex flex-col gap-2.5 text-sm">
          <p className="eyebrow mb-1">Account</p>
          <Link to="/membership" className="text-fg-2 hover:text-fg">
            Membership
          </Link>
          <Link to="/register" className="text-fg-2 hover:text-fg">
            Create account
          </Link>
          <Link to="/login" className="text-fg-2 hover:text-fg">
            Sign in
          </Link>
          {source === 'demo' && (
            <Link to="/overview" className="text-fg-2 hover:text-fg">
              Open the live demo
            </Link>
          )}
        </nav>
        <div className="flex flex-col gap-2.5 text-sm">
          <p className="eyebrow mb-1">Status</p>
          <p className="text-fg-2">Graduation project, 2026.</p>
          <p className="text-fg-3">{source === 'demo' ? 'Running in demo mode: market data and model output are simulated.' : 'Connected to the project backend.'}</p>
        </div>
      </div>
      <div className="border-t border-line">
        <p className="mx-auto max-w-[1240px] px-5 py-6 text-xs leading-5 text-fg-3 sm:px-8">
          <strong className="font-semibold text-fg-2">Risk disclaimer.</strong> Trading gold and foreign exchange carries a high level of risk and may not be suitable for
          everyone; you can lose more than you expect. AI Trading Assistance provides analysis and decision support only. It is not financial advice, it is not a broker,
          and it never places, modifies or closes trades. Model outputs are probabilistic estimates that can be wrong. Past or simulated results do not guarantee future
          results.
        </p>
      </div>
    </footer>
  );
}

/**
 * Scroll to #hash after navigation, below the fixed header (scroll-margin);
 * to the top on page change. Lazily loaded pages render a moment later, so
 * the target is looked up for up to ~1 s before giving up.
 */
function useScrollRestore() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) {
      window.scrollTo({ top: 0 });
      return;
    }
    const id = decodeURIComponent(hash.slice(1));
    let frame = 0;
    let tries = 0;
    const find = () => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ block: 'start' });
      else if (tries++ < 60) frame = requestAnimationFrame(find);
    };
    frame = requestAnimationFrame(find);
    return () => cancelAnimationFrame(frame);
  }, [pathname, hash]);
}

/** Public website frame: window-scrolling page, fixed header, footer. */
export function PublicLayout() {
  useScrollRestore();
  return (
    <div className="min-h-dvh bg-canvas text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[100] focus:rounded-full focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-fg"
      >
        Skip to content
      </a>
      <PublicHeader />
      <main id="main" tabIndex={-1} className="outline-none">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  );
}
