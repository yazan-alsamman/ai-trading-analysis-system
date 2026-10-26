import { Dialog } from '@/components/ui/Dialog';
import { useServices } from '@/app/contexts';
import { allNavFor } from './navigation';

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

const groupsFor = (source: 'demo' | 'api'): { title: string; items: { keys: string[]; label: string }[] }[] => [
  {
    title: 'Global',
    items: [
      { keys: [isMac ? '⌘' : 'Ctrl', 'K'], label: 'Search instruments and pages' },
      { keys: ['?'], label: 'Show keyboard shortcuts' },
      { keys: ['T'], label: 'Toggle dark / light theme' },
    ],
  },
  { title: 'Go to', items: allNavFor(source).map((n) => ({ keys: n.shortcut.toUpperCase().split(' '), label: n.label })) },
  {
    title: 'Workspace',
    items: [
      { keys: ['1'], label: '15-minute timeframe' },
      { keys: ['2'], label: '1-hour timeframe' },
      { keys: ['3'], label: '4-hour timeframe' },
      { keys: ['['], label: 'Previous instrument' },
      { keys: [']'], label: 'Next instrument' },
      { keys: ['Z'], label: 'Toggle AI zones' },
      { keys: ['F'], label: 'Toggle AI forecast' },
    ],
  },
];

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { source } = useServices();
  return (
    <Dialog open={open} onClose={onClose} title="Keyboard shortcuts" description="Shortcuts are disabled while typing in a field.">
      <div className="grid gap-5 sm:grid-cols-2">
        {groupsFor(source).map((g) => (
          <section key={g.title} className={g.title === 'Go to' ? 'sm:row-span-2' : ''}>
            <h3 className="mb-2 text-xs font-medium text-fg-3">{g.title}</h3>
            <dl className="flex flex-col gap-1.5">
              {g.items.map((it) => (
                <div key={it.label} className="flex items-center justify-between gap-3 text-sm">
                  <dt className="text-fg-2">{it.label}</dt>
                  <dd className="flex gap-1">
                    {it.keys.map((k, i) => (
                      <kbd key={i} className="num min-w-6 rounded-sm border border-line-strong bg-inset px-1.5 text-center text-xs leading-5 text-fg">
                        {k}
                      </kbd>
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
