import { ArrowLeft, ExternalLink } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber } from '@/lib/format';
import { isApiError } from '@/services/errors';

const SENTIMENT_TONE = { positive: 'up', neutral: 'neutral', negative: 'down' } as const;

/** One backend news article (GET /news/{id}): the stored summary, its sentiment and its instrument tags. */
export function NewsArticlePage() {
  const { articleId = '' } = useParams();
  const services = useServices();
  const { timeZone } = usePreferences();
  const res = useResource(`news-article:${articleId}`, (signal) => services.marketContext.article(articleId, { signal }));

  const back = (
    <Link to="/community/news" className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg">
      <ArrowLeft aria-hidden className="size-4" /> All news
    </Link>
  );

  if (res.status === 'loading')
    return (
      <Loading label="Loading the article">
        <Skeleton className="h-64 w-full" />
      </Loading>
    );
  if (res.status === 'error' && isApiError(res.error) && res.error.kind === 'not_found')
    return (
      <div className="flex flex-col gap-3">
        {back}
        <EmptyState title="Article not found" description="It may have been removed by the news service." />
      </div>
    );
  if (res.status === 'error' || !res.data)
    return (
      <div className="flex flex-col gap-3">
        {back}
        <ErrorState error={res.error} onRetry={res.reload} />
      </div>
    );

  const a = res.data;
  const safeUrl = /^https?:\/\//i.test(a.url) ? a.url : null;
  const image = a.imageUrl && /^https:\/\//i.test(a.imageUrl) ? a.imageUrl : null;
  return (
    <article aria-labelledby="article-title" className="flex flex-col gap-4">
      {back}
      <div className="rounded-lg border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
          <span className="font-medium text-fg-2">{a.source.name}</span>
          {a.author && (
            <>
              <span aria-hidden>·</span>
              <span>{a.author}</span>
            </>
          )}
          <span aria-hidden>·</span>
          <time dateTime={new Date(a.publishedAt).toISOString()}>{formatDateTime(a.publishedAt, timeZone)}</time>
          <span aria-hidden>·</span>
          <span>{a.language.toUpperCase()}</span>
        </div>
        <h2 id="article-title" className="mt-2 text-xl font-semibold text-fg">
          {a.title}
        </h2>
        {image && <img src={image} alt="" loading="lazy" referrerPolicy="no-referrer" className="mt-4 max-h-80 w-full rounded-md border border-line object-cover" />}
        {a.summary ? <p className="mt-4 text-sm leading-relaxed whitespace-pre-line text-fg">{a.summary}</p> : <p className="mt-4 text-sm text-fg-3">No summary was stored for this article.</p>}

        <dl className="mt-5 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[160px_1fr]">
          <dt className="text-fg-3">Sentiment</dt>
          <dd>
            {a.sentiment ? (
              <span className="flex flex-wrap items-center gap-2">
                <Badge tone={SENTIMENT_TONE[a.sentiment.label]}>{a.sentiment.label}</Badge>
                {a.sentiment.score !== null && <span className="num">score {formatNumber(a.sentiment.score, 2)}</span>}
                {a.sentiment.model && <span className="text-xs text-fg-3">by {a.sentiment.model}</span>}
              </span>
            ) : (
              <span className="text-fg-3">Not scored yet</span>
            )}
          </dd>
          <dt className="text-fg-3">Instruments</dt>
          <dd className="flex flex-wrap gap-1.5">
            {a.instruments.length ? (
              a.instruments.map((t) => (
                <Badge key={t.instrumentId} title={`Relevance ${formatNumber(t.relevance, 2)}`}>
                  {t.symbol} · {formatNumber(t.relevance * 100, 0)}%
                </Badge>
              ))
            ) : (
              <span className="text-fg-3">None tagged</span>
            )}
          </dd>
        </dl>
        <p className="mt-4 text-xs text-fg-3">Sentiment is an automated reading of the text by the backend’s language model. It is not advice.</p>
        {safeUrl && (
          <a href={safeUrl} target="_blank" rel="noopener noreferrer nofollow" className={buttonClasses({ size: 'sm', className: 'mt-4' })}>
            Read at {a.source.name}
            <ExternalLink aria-hidden className="size-3.5" />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
      </div>
    </article>
  );
}
