import { MessageSquare } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Form';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import type { NewsImpact } from '@/domain/community';
import { getInstrument, INSTRUMENTS } from '@/domain/instruments';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatDateTime, formatRelative } from '@/lib/format';
import { CommentThread } from './CommentThread';
import { NewsSentimentPanel, NewsSourcesDisclosure } from './NewsInsights';

const IMPACT: Record<NewsImpact, { label: string; tone: BadgeTone }> = {
  high: { label: 'High impact', tone: 'warning' },
  medium: { label: 'Medium impact', tone: 'info' },
  low: { label: 'Low impact', tone: 'neutral' },
};

export function NewsPage() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource('news', (signal) => services.community.listNews({ signal }));
  const [openId, setOpenId] = useState<string | null>(null);
  const [impact, setImpact] = useState<'all' | NewsImpact>('all');
  const [symbol, setSymbol] = useState('all');

  if (res.status === 'loading')
    return (
      <Loading label="Loading news">
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </Loading>
    );
  if (res.status === 'error' && !res.data) return <ErrorState error={res.error} onRetry={res.reload} title="Could not load news" />;
  if (!res.data?.length) return <EmptyState title="No news right now" description="New items appear here as the news service publishes them." />;

  // Backend news has no impact rating (it has model sentiment instead): the impact filter only appears when ratings exist.
  const hasImpact = res.data.some((n) => n.impact);
  const items = res.data.filter((n) => (impact === 'all' || n.impact === impact) && (symbol === 'all' || n.symbols.some((s) => s === symbol)));

  const api = services.source === 'api';
  return (
    <div className="flex flex-col gap-3">
      {api && <NewsSentimentPanel />}
      {api && <NewsSourcesDisclosure />}
      <div className="flex flex-wrap items-center gap-2">
        {hasImpact && (
          <Select aria-label="Filter by impact" value={impact} onChange={(e) => setImpact(e.target.value as 'all' | NewsImpact)} className="h-8 w-40">
            <option value="all">All impact levels</option>
            <option value="high">High impact</option>
            <option value="medium">Medium impact</option>
            <option value="low">Low impact</option>
          </Select>
        )}
        <Select aria-label="Filter by instrument" value={symbol} onChange={(e) => setSymbol(e.target.value)} className="h-8 w-40">
          <option value="all">All instruments</option>
          {INSTRUMENTS.map((i) => (
            <option key={i.symbol} value={i.symbol}>
              {i.display}
            </option>
          ))}
        </Select>
        <span className="ml-auto text-xs text-fg-3" aria-live="polite">
          {items.length} of {res.data.length} items
        </span>
      </div>
      {items.length === 0 && <EmptyState title="No news matches these filters" compact />}
      {items.map((n) => {
        const open = openId === n.id;
        return (
          <article key={n.id} aria-labelledby={`news-${n.id}`} className="rounded-lg border border-line bg-surface px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
              {n.impact && <Badge tone={IMPACT[n.impact].tone}>{IMPACT[n.impact].label}</Badge>}
              {n.sentiment && (
                <Badge
                  tone={n.sentiment.label === 'positive' ? 'up' : n.sentiment.label === 'negative' ? 'down' : 'neutral'}
                  title="Sentiment scored by the backend's language model (FinBERT). An automated reading of the text, not advice."
                >
                  {n.sentiment.label} sentiment{n.sentiment.score !== null ? ` · ${n.sentiment.score.toFixed(2)}` : ''}
                </Badge>
              )}
              <span>{n.source}</span>
              <span aria-hidden>·</span>
              <time dateTime={new Date(n.publishedAt).toISOString()} title={formatDateTime(n.publishedAt, timeZone)}>
                {formatRelative(n.publishedAt)}
              </time>
            </div>
            <h2 id={`news-${n.id}`} className="mt-1.5 text-base font-semibold text-fg">
              {api ? (
                <Link to={`/community/news/${n.id}`} className="underline-offset-2 hover:underline">
                  {n.title}
                </Link>
              ) : (
                n.title
              )}
            </h2>
            {n.summary && <p className="mt-1 text-sm text-fg-2">{n.summary}</p>}
            {n.url && /^https?:\/\//i.test(n.url) && (
              <a href={n.url} target="_blank" rel="noopener noreferrer nofollow" className="mt-1 inline-block text-xs text-fg-2 underline underline-offset-2 hover:text-fg">
                Read at {n.source}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {n.symbols.map((s) => (
                <Badge key={s}>{getInstrument(s).display}</Badge>
              ))}
              {n.commentsEnabled !== false && (
              <button
                type="button"
                aria-expanded={open}
                aria-controls={`comments-${n.id}`}
                onClick={() => setOpenId(open ? null : n.id)}
                className={cn(
                  'ml-auto inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium hover:bg-hover',
                  open ? 'text-fg' : 'text-fg-2',
                )}
              >
                <MessageSquare aria-hidden className="size-4" />
                {n.commentCount} {n.commentCount === 1 ? 'comment' : 'comments'}
              </button>
              )}
            </div>
            {open && n.commentsEnabled !== false && (
              <div id={`comments-${n.id}`}>
                <CommentThread
                  threadId={n.id}
                  onAdded={() => res.setData((list) => (list ?? []).map((x) => (x.id === n.id ? { ...x, commentCount: x.commentCount + 1 } : x)))}
                />
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
