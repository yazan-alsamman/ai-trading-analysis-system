import { Copy, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { CustomStrategy } from '@/domain/strategies';
import { ROLE_LABELS, type UserRole } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { errorText } from './strategyUtils';

const roleLabel = (role: string) => (role in ROLE_LABELS ? ROLE_LABELS[role as UserRole] : role);

/** Strategies other users published (GET /custom-strategies/public); cloning makes a private copy. */
export function PublicSection({ onCloned }: { onCloned: (s: CustomStrategy) => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    const id = window.setTimeout(() => setSearch(query.trim()), 350);
    return () => window.clearTimeout(id);
  }, [query]);

  const res = useResource(`public-strategies:${search}`, (signal) => services.strategies.listPublic(search ? { search } : {}, { signal }));

  const clone = async (id: string) => {
    setBusyId(id);
    try {
      const copy = await services.strategies.clonePublic(id);
      onCloned(copy);
      notify(`“${copy.name}” added to your custom strategies.`, 'success');
    } catch (e) {
      notify(errorText(e), 'danger');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Panel
      title="Community strategies"
      meta={<span>Published by analysts and experts. Past rules, not recommendations.</span>}
      flush
    >
      <div className="border-b border-line p-4">
        <label className="relative block max-w-sm">
          <span className="sr-only">Search public strategies by name</span>
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-3" />
          <Input type="search" className="pl-9" placeholder="Search by name" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
      </div>
      {res.status === 'loading' ? (
        <Loading label="Loading community strategies">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact title={search ? 'No matching strategies' : 'No public strategies yet'} description={search ? 'Try another name.' : 'Nobody has published a strategy yet.'} />
      ) : (
        <ul className="divide-y divide-line">
          {res.data.map((s) => (
            <li key={s.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                  {s.name}
                  <Badge>{s.kind === 'builder' ? 'Builder' : 'Composite'}</Badge>
                </p>
                <p className="text-xs text-fg-3">
                  By {s.author.name} ({roleLabel(s.author.role)}) · <span className="num">v{s.version}</span> · updated {formatDate(s.updatedAt, timeZone)}
                </p>
                {s.description && <p className="mt-1 text-sm text-fg-2">{s.description}</p>}
              </div>
              <Button size="sm" icon={Copy} loading={busyId === s.id} onClick={() => void clone(s.id)}>
                Clone to my strategies
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
