import { ArrowRight, Lock, Send, Unplug } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { useServices } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { FormError, Textarea } from '@/components/ui/Form';
import { EmptyState, ErrorState, Loading, Skeleton, SkeletonRows } from '@/components/ui/StateViews';
import type { Expert, ExpertAvailability } from '@/domain/community';
import { getInstrument } from '@/domain/instruments';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatRelative } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { useNow } from '@/hooks/useEnvironment';
import { ChatModerationBar, OwnMessageActions } from './chatModeration';

const AVAILABILITY: Record<ExpertAvailability, { label: string; tone: BadgeTone }> = {
  available: { label: 'Available', tone: 'accent' },
  busy: { label: 'Busy', tone: 'warning' },
  offline: { label: 'Offline', tone: 'neutral' },
};

function Conversation({ expert, chatAvailable }: { expert: Expert; chatAvailable: boolean }) {
  const services = useServices();
  const res = useResource(`conversation:${expert.id}`, (signal) => services.community.getConversation(expert.id, { signal }));
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const api = services.source === 'api';
  const now = useNow(30_000);
  // Backend: the conversation itself (status, blocking). It exists once the messages loaded (opened by the server).
  const conv = useResource(api && res.status === 'success' ? `conversation-detail:${expert.id}` : `conversation-detail:${expert.id}:pending`, async (signal) => {
    if (!api || res.status !== 'success') return null;
    const found = (await services.social.conversations({ signal })).find((c) => c.expertId === expert.id);
    return found ? services.social.conversation(found.id, { signal }) : null;
  });
  const canSend = chatAvailable && conv.data?.canSend !== false;

  const send = async () => {
    const body = draft.trim();
    if (!canSend || !body) return;
    setSending(true);
    setSendError(null);
    try {
      const message = await services.community.sendMessage(expert.id, body);
      res.setData((list) => [...(list ?? []), message]);
      setDraft('');
    } catch (e) {
      setSendError(userMessage(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <section aria-label={`Conversation with ${expert.name}`} className="flex min-h-[420px] flex-col rounded-lg border border-line bg-surface">
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-fg">{expert.name}</h2>
        <ExpertStatus expert={expert} />
        {expert.isSubscribed ? (
          <Badge tone="accent" className="ml-auto">
            Subscribed
          </Badge>
        ) : (
          <span className="ml-auto flex items-center gap-2">
            {expert.cheapestPlan && (
              <span className="text-xs text-fg-3">
                From <span className="num text-fg-2">{expert.cheapestPlan.price} {expert.cheapestPlan.currency}</span> / {expert.cheapestPlan.interval}
              </span>
            )}
            {services.source === 'api' ? (
              <Link to={`/community/experts/${expert.id}`} className={buttonClasses({ variant: 'primary', size: 'sm' })}>
                View plans
                <ArrowRight aria-hidden className="size-4" />
              </Link>
            ) : (
              <Button
                size="sm"
                variant="primary"
                icon={Lock}
                disabled
                title="Subscribing is not available in the web client yet (the backend's checkout uses demo payments only)."
              >
                Subscribe to chat
              </Button>
            )}
          </span>
        )}
      </header>

      {!chatAvailable && (
        <div className="flex items-start gap-2 border-b border-line bg-warning-soft px-4 py-2.5 text-xs text-fg">
          <Unplug aria-hidden className="mt-0.5 size-3.5 shrink-0 text-warning" />
          <p>
            Live expert chat and subscriptions need the backend realtime and subscription services, which are not connected yet. The transcript below is
            sample content; sending is disabled so no message is silently lost.
          </p>
        </div>
      )}

      {conv.data && <ChatModerationBar conversation={conv.data} onChange={(c) => conv.setData(() => c)} />}

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {res.status === 'loading' ? (
          <Loading label="Loading conversation">
            <SkeletonRows rows={3} />
          </Loading>
        ) : res.status === 'error' && !res.data ? (
          <ErrorState error={res.error} onRetry={res.reload} compact />
        ) : !res.data?.length ? (
          <EmptyState title="No messages yet" description={`Your conversation with ${expert.name} will appear here.`} compact />
        ) : (
          <ol className="flex flex-col gap-3">
            {res.data.map((m) => (
              <li key={m.id} className={cn('flex flex-col', m.from === 'user' ? 'items-end' : 'items-start')}>
                <p className={cn('max-w-[85%] rounded-lg px-3 py-2 text-sm', m.from === 'user' ? 'bg-selected text-fg' : 'bg-hover text-fg')}>{m.body}</p>
                <span className="mt-1 flex items-center gap-1 text-xs text-fg-3">
                  {m.from === 'user' ? 'You' : expert.name} · {formatRelative(m.sentAt)}
                  {m.editedAt !== undefined && ' · edited'}
                  {api && m.from === 'user' && (
                    <OwnMessageActions
                      message={m}
                      now={now}
                      onEdited={(edited) => res.setData((list) => (list ?? []).map((x) => (x.id === edited.id ? edited : x)))}
                      onDeleted={(id) => res.setData((list) => (list ?? []).filter((x) => x.id !== id))}
                    />
                  )}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {sendError && (
        <div className="px-3 pt-3">
          <FormError message={sendError} />
        </div>
      )}
      <form
        className="flex items-end gap-2 border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <label className="sr-only" htmlFor="chat-message">
          Message {expert.name}
        </label>
        <Textarea
          id="chat-message"
          rows={1}
          className="min-h-9"
          placeholder={canSend ? `Message ${expert.name}` : chatAvailable ? 'This conversation is read-only' : 'Messaging unavailable until the chat service is connected'}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={!canSend}
        />
        <Button type="submit" variant="primary" icon={Send} loading={sending} disabled={!canSend || draft.trim().length === 0} aria-label="Send message" />
      </form>
    </section>
  );
}

/** Demo: presence. Backend: whether the expert accepts chat (it reports no presence). */
function ExpertStatus({ expert, className }: { expert: Expert; className?: string }) {
  if (expert.availability)
    return (
      <Badge tone={AVAILABILITY[expert.availability].tone} {...(className ? { className } : {})}>
        {AVAILABILITY[expert.availability].label}
      </Badge>
    );
  if (expert.chatEnabled === undefined) return null;
  return (
    <Badge tone={expert.chatEnabled ? 'accent' : 'neutral'} {...(className ? { className } : {})}>
      {expert.chatEnabled ? 'Chat open' : 'No chat'}
    </Badge>
  );
}

export function ExpertsPage() {
  const services = useServices();
  const res = useResource('experts', (signal) => services.community.listExperts({ signal }));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // In demo mode there is no realtime service; in API mode the backend decides.
  const chatAvailable = services.source === 'api';

  if (res.status === 'loading')
    return (
      <Loading label="Loading experts">
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <Skeleton className="h-64" />
          <Skeleton className="h-96" />
        </div>
      </Loading>
    );
  if (res.status === 'error' && !res.data) return <ErrorState error={res.error} onRetry={res.reload} title="Could not load experts" />;
  if (!res.data?.length) return <EmptyState title="No experts listed" description="Human trading experts will appear here once they join." />;

  const selected = res.data.find((e) => e.id === selectedId) ?? res.data[0];

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <ul aria-label="Experts" className="flex flex-col gap-2">
        {res.data.map((e) => {
          const active = e.id === selected?.id;
          return (
            <li key={e.id}>
              <button
                type="button"
                aria-current={active ? 'true' : undefined}
                onClick={() => setSelectedId(e.id)}
                className={cn('w-full rounded-lg border p-3 text-left transition-colors', active ? 'border-accent/60 bg-selected' : 'border-line bg-surface hover:bg-hover')}
              >
                <span className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-fg">{e.name}</span>
                  <ExpertStatus expert={e} className="ml-auto" />
                </span>
                <span className="mt-0.5 block text-sm text-fg-2">{e.headline}</span>
                <span className="mt-2 block text-xs text-fg-3">
                  {[...e.specialties, ...(e.marketCategories ?? [])].join(' · ')} · {e.languages.join(', ')}
                  {e.responseTimeHint ? ` · replies ${e.responseTimeHint}` : ''}
                </span>
                <span className="mt-2 flex flex-wrap gap-1">
                  {e.markets.map((s) => (
                    <Badge key={s}>{getInstrument(s).display}</Badge>
                  ))}
                  {e.isSubscribed && <Badge tone="accent">Subscribed</Badge>}
                </span>
              </button>
              {services.source === 'api' && (
                <Link
                  to={`/community/experts/${e.id}`}
                  className="mt-1 inline-flex items-center gap-1 px-1 text-xs font-medium text-accent underline-offset-2 hover:underline"
                >
                  {e.cheapestPlan ? `View plans · from ${e.cheapestPlan.price} ${e.cheapestPlan.currency} / ${e.cheapestPlan.interval}` : 'View profile & plans'}
                  <span className="sr-only"> for {e.name}</span>
                </Link>
              )}
            </li>
          );
        })}
      </ul>
      {selected && <Conversation key={selected.id} expert={selected} chatAvailable={chatAvailable && selected.chatEnabled !== false} />}
    </div>
  );
}
