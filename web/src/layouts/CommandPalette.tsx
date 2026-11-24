import { CornerDownLeft, Search } from 'lucide-react';
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth, usePreferences } from '@/app/contexts';
import { INSTRUMENTS, matchesInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { useServices } from '@/app/contexts';
import { allNavFor } from './navigation';

interface Item {
  id: string;
  group: 'Instruments' | 'Pages';
  label: string;
  hint: string;
  run: () => void;
}

/** ⌘K / Ctrl+K quick switcher for instruments and pages (combobox pattern). */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const { updateWorkspace } = usePreferences();
  const { source } = useServices();
  const role = useAuth().session?.user.role;
  const listId = useId();

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      setQuery('');
      setActive(0);
      d.showModal();
    } else if (!open && d.open) d.close();
  }, [open]);

  const items = useMemo<Item[]>(() => {
    const q = query.trim().toLowerCase();
    const instruments: Item[] = INSTRUMENTS.filter((i) => matchesInstrument(i, q)).map((i) => ({
      id: `i-${i.symbol}`,
      group: 'Instruments',
      label: i.display,
      hint: i.name,
      run: () => {
        updateWorkspace({ symbol: i.symbol });
        navigate('/workspace');
      },
    }));
    const pages: Item[] = allNavFor(source, role)
      .filter((p) => !q || p.label.toLowerCase().includes(q) || p.description.toLowerCase().includes(q))
      .map((p) => ({ id: `p-${p.to}`, group: 'Pages', label: p.label, hint: p.description, run: () => navigate(p.to) }));
    return [...instruments, ...pages];
  }, [query, navigate, updateWorkspace, source, role]);

  const choose = (item: Item | undefined) => {
    if (!item) return;
    item.run();
    onClose();
  };

  return (
    <dialog
      ref={ref}
      aria-label="Quick search"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
      className="mx-auto mt-[12vh] w-[calc(100vw-2rem)] max-w-lg rounded-lg border border-line-strong bg-raised p-0 text-fg shadow-float backdrop:bg-overlay"
    >
      {open && (
        <div>
          <div className="flex items-center gap-2 border-b border-line px-3">
            <Search aria-hidden className="size-4 text-fg-3" />
            <input
              autoFocus
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-activedescendant={items[active]?.id}
              aria-label="Search instruments and pages"
              placeholder="Search instruments and pages…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault();
                  setActive((a) => Math.min(items.length - 1, a + 1));
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault();
                  setActive((a) => Math.max(0, a - 1));
                } else if (e.key === 'Enter') {
                  e.preventDefault();
                  choose(items[active]);
                }
              }}
              className="h-11 flex-1 bg-transparent text-base outline-none placeholder:text-fg-3"
            />
            <kbd className="rounded-sm border border-line px-1.5 text-xs text-fg-3">Esc</kbd>
          </div>
          <ul id={listId} role="listbox" aria-label="Results" className="max-h-80 overflow-y-auto p-1.5">
            {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-fg-2">No matches for “{query}”.</li>}
            {items.map((item, index) => (
              <li
                key={item.id}
                id={item.id}
                role="option"
                aria-selected={index === active}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(item)}
                className={cn('flex cursor-pointer items-center gap-3 rounded-md px-3 py-2', index === active && 'bg-selected')}
              >
                <span className="w-24 shrink-0 text-xs text-fg-3">{item.group === 'Instruments' ? 'Instrument' : 'Page'}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-fg">{item.label}</span>
                  <span className="block truncate text-xs text-fg-3">{item.hint}</span>
                </span>
                {index === active && <CornerDownLeft aria-hidden className="size-4 text-fg-3" />}
              </li>
            ))}
          </ul>
        </div>
      )}
    </dialog>
  );
}
