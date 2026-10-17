import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router';
import { AssistantLauncher } from '../assistant/AssistantLauncher';
import { PublicFooter } from './PublicFooter';
import { PublicHeader } from './PublicHeader';

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
      <AssistantLauncher />
    </div>
  );
}
