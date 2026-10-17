import { AlertTriangle, CheckCircle2, Info, OctagonAlert, X } from 'lucide-react';
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { ToastContext, type ToastApi, type ToastTone } from './contexts';

interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

const ICONS = { info: Info, success: CheckCircle2, warning: AlertTriangle, danger: OctagonAlert } as const;
const TONE_CLASS: Record<ToastTone, string> = {
  info: 'text-info',
  success: 'text-accent',
  warning: 'text-warning',
  danger: 'text-danger',
};

/** Transient, non-blocking feedback. Announced politely to screen readers. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const api = useMemo<ToastApi>(
    () => ({
      notify(message, tone = 'info') {
        nextId.current += 1;
        const id = nextId.current;
        setToasts((t) => [...t.slice(-3), { id, message, tone }]);
        setTimeout(() => dismiss(id), tone === 'danger' ? 8000 : 4500);
      },
    }),
    [dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2"
      >
        {toasts.map((t) => {
          const Icon = ICONS[t.tone];
          return (
            <div
              key={t.id}
              className="pointer-events-auto flex items-start gap-3 rounded-lg border border-line-strong bg-raised px-3 py-2.5 text-sm shadow-float"
            >
              <Icon aria-hidden className={cn('mt-0.5 size-4 shrink-0', TONE_CLASS[t.tone])} />
              <p className="min-w-0 flex-1 text-fg">{t.message}</p>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="-mr-1 rounded-sm p-0.5 text-fg-3 hover:text-fg"
                aria-label="Dismiss notification"
              >
                <X aria-hidden className="size-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
