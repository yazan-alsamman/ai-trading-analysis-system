import { FlaskConical } from 'lucide-react';
import type { ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router';
import { useServices } from '@/app/contexts';
import { cn } from '@/lib/cn';

/**
 * Sign in ↔ Create account switch. Real links (Back works, own URLs); the
 * selected plan travels along; the indicator slides between the two.
 */
function AuthSwitch() {
  const { pathname, search } = useLocation();
  const plan = new URLSearchParams(search).get('plan');
  const q = plan ? `?plan=${encodeURIComponent(plan)}` : '';
  const onRegister = pathname.startsWith('/register');
  return (
    <nav aria-label="Account" className="relative grid grid-cols-2 rounded-full border border-line bg-inset p-1">
      <span
        aria-hidden
        className="absolute top-1 bottom-1 left-1 w-[calc(50%-0.25rem)] rounded-full bg-primary transition-transform duration-[260ms] ease-[var(--m-ease-out)]"
        style={{ transform: onRegister ? 'translateX(100%)' : 'none' }}
      />
      {[
        ['/login', 'Sign in'],
        ['/register', 'Create account'],
      ].map(([to, label]) => (
        <NavLink
          key={to}
          to={`${to}${q}`}
          viewTransition
          className={({ isActive }) =>
            cn('relative z-[1] flex h-9 items-center justify-center rounded-full text-sm font-medium transition-colors duration-200', isActive ? 'text-primary-fg' : 'text-fg-2 hover:text-fg')
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export function AuthCard({
  title,
  muted,
  subtitle,
  children,
  footer,
  before,
}: {
  title: string;
  muted?: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Shown above the switch (journey progress). */
  before?: ReactNode;
}) {
  const { source } = useServices();
  return (
    <div className="reveal flex flex-col gap-7" style={{ viewTransitionName: 'auth-card' }}>
      {before}
      <AuthSwitch />
      <div>
        <h1 className="display text-d3 text-fg sm:text-d2">
          {title}
          {muted && (
            <>
              {' '}
              <em>{muted}</em>
            </>
          )}
        </h1>
        <p className="mt-2 text-sm text-fg-2">{subtitle}</p>
      </div>
      {source === 'demo' && (
        <p className="flex items-start gap-2 rounded-lg border border-dashed border-demo/50 bg-demo-soft px-3 py-2.5 text-xs text-fg-2">
          <FlaskConical aria-hidden className="mt-0.5 size-3.5 shrink-0 text-demo" />
          <span>
            <strong className="font-semibold text-fg">Demo mode — no backend is connected.</strong> Credentials are not sent or verified, and the password is never stored. A
            local demo session is created.
          </span>
        </p>
      )}
      {children}
      {footer && <div className="border-t border-line pt-5 text-center text-sm text-fg-2">{footer}</div>}
    </div>
  );
}
