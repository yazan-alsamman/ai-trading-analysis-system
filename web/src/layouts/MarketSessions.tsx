import { sessionStates } from '@/domain/sessions';
import { useNow } from '@/hooks/useEnvironment';
import { cn } from '@/lib/cn';

/** Compact session board for the sidebar footer: which FX centres are open now. */
export function MarketSessions({ collapsed }: { collapsed: boolean }) {
  const now = useNow(30_000);
  const states = sessionStates(now);
  const openCount = states.filter((s) => s.open).length;

  if (collapsed) {
    return (
      <p className="text-center text-xs text-fg-3" title={states.map((s) => `${s.label}: ${s.open ? 'open' : 'closed'}`).join('\n')}>
        <span className="num text-fg-2">{openCount}</span>/4
      </p>
    );
  }

  return (
    <section aria-label="FX market sessions" className="px-2.5">
      <h2 className="mb-1.5 text-xs font-medium text-fg-3">Sessions</h2>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
        {states.map((s) => (
          <li key={s.id} className="flex items-center gap-1.5 text-xs">
            <span aria-hidden className={cn('size-1.5 rounded-full', s.open ? 'bg-accent' : 'bg-line-strong')} />
            <span className={s.open ? 'text-fg' : 'text-fg-3'}>{s.label}</span>
            <span className="sr-only">{s.open ? 'open' : 'closed'}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
