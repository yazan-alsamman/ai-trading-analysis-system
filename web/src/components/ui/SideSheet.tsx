import { X } from 'lucide-react';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { IconButton } from './Button';

/**
 * Right-hand sheet on a native <dialog>: focus containment, Esc to close,
 * inert background, focus returned to the opener. Used for contextual panels
 * (signal provenance, the workspace assistant) that should not leave the page.
 */
export function SideSheet({ open, onClose, title, meta, children, width = 'md' }: { open: boolean; onClose: () => void; title: string; meta?: ReactNode; children: ReactNode; width?: 'md' | 'lg' }) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement as HTMLElement | null;
      d.showModal();
    } else if (!open && d.open) {
      d.close();
      opener.current?.focus();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
      className={`sheet m-0 ml-auto h-dvh max-h-dvh w-full max-w-none border-l border-line-strong bg-surface p-0 text-fg shadow-float backdrop:bg-overlay ${width === 'lg' ? 'sm:w-[min(720px,92vw)]' : 'sm:w-[min(480px,92vw)]'}`}
    >
      {open && (
        <div className="flex h-full flex-col">
          <header className="flex min-h-14 shrink-0 items-center gap-3 border-b border-line px-4">
            <h2 id={titleId} className="text-md font-semibold">
              {title}
            </h2>
            {meta}
            <div className="ml-auto">
              <IconButton icon={X} label="Close panel" size="sm" onClick={onClose} tooltipSide="left" />
            </div>
          </header>
          <div className="min-h-0 flex-1">{children}</div>
        </div>
      )}
    </dialog>
  );
}
