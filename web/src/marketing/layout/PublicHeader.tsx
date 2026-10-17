import { ArrowRight, Menu, X } from 'lucide-react';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Link, NavLink, useLocation } from 'react-router';
import { BrandGlyph, BrandMark } from '@/components/brand/BrandMark';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { cn } from '@/lib/cn';
import { subscribeFrames } from '@/motion/runtime';
import { PUBLIC_NAV } from '../content';


function NavItem({ to, label, onClick }: { to: string; label: string; onClick?: () => void }) {
  const { pathname, hash } = useLocation();
  const active = to.startsWith('/#') ? pathname === '/' && hash === to.slice(1) : pathname === to;
  return (
    <Link
      to={to}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={cn('nav-link relative px-3 py-2 text-sm transition-colors duration-150', active ? 'text-fg' : 'text-fg-2 hover:text-fg')}
    >
      {label}
    </Link>
  );
}

/** Full-height mobile menu on a native <dialog> (focus trap, Esc, inert page). */
function MobileMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-label="Site menu"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      // pointer-events-auto: the header wrapper is pointer-events-none, which the dialog would otherwise inherit.
      className="sheet pointer-events-auto m-0 h-dvh max-h-dvh w-full max-w-none bg-canvas p-0 text-fg backdrop:bg-overlay"
    >
      {open && (
        <div className="atmosphere flex h-full flex-col px-5 pt-4 pb-8">
          <div className="flex h-12 items-center justify-between">
            <BrandMark />
            <button type="button" onClick={onClose} aria-label="Close menu" className="inline-flex size-10 items-center justify-center rounded-full border border-line hover:bg-hover">
              <X aria-hidden className="size-5" />
            </button>
          </div>
          <nav aria-label="Site" className="mt-8 flex flex-col">
            {PUBLIC_NAV.map((n, i) => (
              <Link
                key={n.to}
                to={n.to}
                onClick={onClose}
                className="m-in display flex items-center justify-between border-b border-line py-4 text-d3 text-fg"
                style={{ '--at': `${60 + i * 40}ms` } as CSSProperties}
              >
                {n.label}
                <ArrowRight aria-hidden className="size-5 text-fg-3" />
              </Link>
            ))}
          </nav>
          <div className="m-in mt-auto flex flex-col gap-3" style={{ '--at': '340ms' } as CSSProperties}>
            <Link to="/membership#plans" onClick={onClose} className={buttonClasses({ variant: 'primary', size: 'lg', shape: 'pill', className: 'w-full' })}>
              Get started
            </Link>
            <Link to="/login" onClick={onClose} className={buttonClasses({ variant: 'secondary', size: 'lg', shape: 'pill', className: 'w-full bg-transparent' })}>
              Sign in
            </Link>
          </div>
        </div>
      )}
    </dialog>
  );
}

export function PublicHeader() {
  const [compact, setCompact] = useState(false);
  const [menu, setMenu] = useState(false);
  useEffect(() => subscribeFrames(() => setCompact((c) => (c === window.scrollY > 24 ? c : window.scrollY > 24))), []);

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-5">
      <div
        data-compact={compact}
        className={cn(
          'public-bar pointer-events-auto mx-auto flex max-w-[1240px] items-center gap-2 rounded-full border px-3 transition-[height,background-color,border-color,box-shadow] duration-[260ms] ease-[var(--m-ease-out)] sm:px-4',
          compact ? 'h-14 border-line-strong bg-surface/80 shadow-float backdrop-blur-xl' : 'h-16 border-transparent bg-transparent',
        )}
      >
        <Link to="/" viewTransition aria-label="AI Trading Assistance — home" className="mr-2 flex items-center" style={{ viewTransitionName: 'brand' }}>
          <span className="hidden sm:block">
            <BrandMark />
          </span>
          <span className="sm:hidden">
            <BrandGlyph className="size-8" />
          </span>
        </Link>
        <nav aria-label="Site" className="hidden flex-1 items-center justify-center lg:flex">
          {PUBLIC_NAV.map((n) => (
            <NavItem key={n.to} {...n} />
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          <NavLink to="/login" viewTransition className="hidden rounded-full px-3 py-2 text-sm font-medium text-fg-2 hover:text-fg sm:inline-flex">
            Sign in
          </NavLink>
          <Link to="/membership#plans" viewTransition className={buttonClasses({ variant: 'primary', size: 'sm', shape: 'pill', className: 'h-9 px-4' })}>
            Get started
          </Link>
          <button
            type="button"
            onClick={() => setMenu(true)}
            aria-label="Open menu"
            className="inline-flex size-9 items-center justify-center rounded-full text-fg-2 hover:bg-hover hover:text-fg lg:hidden"
          >
            <Menu aria-hidden className="size-5" />
          </button>
        </div>
      </div>
      <MobileMenu open={menu} onClose={() => setMenu(false)} />
    </header>
  );
}
