import { LineChart, Plus } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import type { StrategyDefinition } from '@/domain/strategies';
import type { Resource } from '@/hooks/useResource';
import { formatNumber } from '@/lib/format';
import { formatJsonValue, humanize } from './strategyUtils';

/** The platform's global strategies (GET /strategies). */
export function CatalogSection({
  catalog,
  onPreview,
  onActivate,
}: {
  catalog: Resource<StrategyDefinition[]>;
  onPreview: (def: StrategyDefinition) => void;
  onActivate: (def: StrategyDefinition) => void;
}) {
  if (catalog.status === 'loading')
    return (
      <Loading label="Loading strategy catalog">
        <div className="grid gap-3 md:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </Loading>
    );
  if (catalog.status === 'error' && !catalog.data) return <ErrorState error={catalog.error} onRetry={catalog.reload} />;
  if (!catalog.data?.length) return <EmptyState title="No strategies" description="The backend did not return any platform strategies." />;

  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {catalog.data.map((s) => (
        <li key={s.key} className="flex">
          <Panel
            className="flex-1"
            title={s.title}
            meta={<Badge>{humanize(s.category)}</Badge>}
            bodyClassName="flex flex-col gap-3"
          >
            <p className="text-sm text-fg-2">{s.description}</p>
            {s.params.length > 0 && (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
                {s.params.map((p) => (
                  <div key={p.name} className="min-w-0">
                    <dt className="truncate text-fg-3">{p.title}</dt>
                    <dd className="num text-fg">{formatJsonValue(p.default)}</dd>
                  </div>
                ))}
              </dl>
            )}
            <p className="text-xs text-fg-3">
              Needs {formatNumber(s.history)} bars of history{s.indicators.length > 0 ? ` · draws ${s.indicators.map((i) => i.name).join(', ')}` : ''}
            </p>
            <div className="mt-auto flex flex-wrap gap-2">
              <Button size="sm" icon={LineChart} onClick={() => onPreview(s)}>
                Preview
              </Button>
              <Button size="sm" variant="primary" icon={Plus} onClick={() => onActivate(s)}>
                Activate
              </Button>
            </div>
          </Panel>
        </li>
      ))}
    </ul>
  );
}
