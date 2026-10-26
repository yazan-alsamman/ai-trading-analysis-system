import { cn } from '@/lib/cn';

/** "snake_case_key" → "Snake case key". */
function humanize(key: string): string {
  const text = key.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function Scalar({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') return <span className="text-fg-3">—</span>;
  if (typeof value === 'boolean') return <span className={value ? 'text-up' : 'text-fg-2'}>{value ? 'Yes' : 'No'}</span>;
  if (typeof value === 'number') return <span className="num">{Number.isInteger(value) ? value.toLocaleString('en-US') : value.toLocaleString('en-US', { maximumFractionDigits: 4 })}</span>;
  return <span className="break-all">{String(value)}</span>;
}

/**
 * Server-owned JSON (status blocks, statistics) shown as nested label/value
 * lists, exactly as the backend sent it: nothing is renamed into meaning the
 * backend did not state, keys are only made readable.
 */
export function JsonView({ value, depth = 0, className }: { value: unknown; depth?: number; className?: string }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-fg-3">None</span>;
    if (value.every((v) => typeof v !== 'object' || v === null))
      return (
        <span className="break-all">
          {value.map((v, i) => (
            <span key={i}>
              {i > 0 && ', '}
              <Scalar value={v} />
            </span>
          ))}
        </span>
      );
    return (
      <ol className={cn('flex flex-col gap-2', className)}>
        {value.map((v, i) => (
          <li key={i} className="rounded-md border border-line p-2">
            <JsonView value={v} depth={depth + 1} />
          </li>
        ))}
      </ol>
    );
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-fg-3">None</span>;
    return (
      <dl className={cn('grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[minmax(140px,max-content)_1fr]', className)}>
        {entries.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-fg-3">{humanize(k)}</dt>
            <dd className="min-w-0 text-fg">{v && typeof v === 'object' && depth < 4 ? <JsonView value={v} depth={depth + 1} /> : <Scalar value={v && typeof v === 'object' ? JSON.stringify(v) : v} />}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return <Scalar value={value} />;
}
