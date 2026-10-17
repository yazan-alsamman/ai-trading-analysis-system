import { Bot, Maximize2 } from 'lucide-react';
import { lazy, Suspense, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router';
import { SideSheet } from '@/components/ui/SideSheet';
import { cn } from '@/lib/cn';
import { subscribeFrames } from '@/motion/runtime';
// Loaded only when the sheet is opened, so the assistant adds nothing to the first paint.
const PublicAssistant = lazy(() => import('./PublicAssistant').then((m) => ({ default: m.PublicAssistant })));

/** Pages that get the floating entry point (never over sign-up, membership or the assistant page itself). */
const PAGES = new Set(['/', '/about']);

/**
 * Floating "Ask the research assistant" button for the public story pages.
 * It appears once the hero (and its calls to action) has scrolled away, and
 * steps aside while the footer is in view so it never covers footer links.
 */
export function AssistantLauncher() {
  const { pathname } = useLocation();
  const enabled = PAGES.has(pathname);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let footerVisible = false;
    const footer = document.querySelector('footer');
    const io =
      footer && typeof IntersectionObserver !== 'undefined'
        ? new IntersectionObserver(([e]) => {
            footerVisible = !!e?.isIntersecting;
            update();
          })
        : null;
    if (footer) io?.observe(footer);
    function update() {
      const next = window.scrollY > window.innerHeight * 0.8 && !footerVisible;
      setShown((prev) => (prev === next ? prev : next));
    }
    const unsubscribe = subscribeFrames(update);
    return () => {
      unsubscribe();
      io?.disconnect();
    };
  }, [enabled, pathname]);

  if (!enabled) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        tabIndex={shown ? 0 : -1}
        aria-hidden={!shown}
        className={cn(
          'launcher fixed right-4 bottom-4 z-40 inline-flex h-12 items-center gap-2 rounded-full border border-forecast/40 bg-surface pr-4 pl-3 text-sm font-medium text-fg shadow-float sm:right-6 sm:bottom-6',
          'transition-[opacity,transform] duration-300 ease-[var(--m-ease-out)] hover:border-forecast/70',
          shown ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-3 opacity-0',
        )}
      >
        <span aria-hidden className="inline-flex size-7 items-center justify-center rounded-full bg-forecast-soft text-forecast">
          <Bot className="size-4" />
        </span>
        <span className="max-sm:sr-only">Ask the research assistant</span>
      </button>
      <SideSheet
        open={open}
        onClose={() => setOpen(false)}
        title="Research assistant"
        meta={
          <Link to="/ai-assistant" onClick={() => setOpen(false)} className="inline-flex items-center gap-1 text-xs text-fg-2 hover:text-fg">
            <Maximize2 aria-hidden className="size-3" /> Full page
          </Link>
        }
      >
        <Suspense fallback={<p className="p-4 text-sm text-fg-3">Loading the assistant…</p>}>
          <PublicAssistant variant="drawer" />
        </Suspense>
      </SideSheet>
    </>
  );
}
