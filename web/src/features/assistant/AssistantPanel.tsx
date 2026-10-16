import { ArrowUp, Bot, Eraser, FlaskConical, RotateCw, Square, UserRound } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Form';
import { Markdown } from '@/components/ui/Markdown';
import { describeContext, SUGGESTED_PROMPTS, type AssistantContext } from '@/domain/assistant';
import { getInstrument } from '@/domain/instruments';
import { cn } from '@/lib/cn';
import { formatClock } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { PlanGate } from '@/features/membership/PlanGate';
import { useFeatureAccess } from '@/features/membership/useFeatureAccess';
import { useAssistantThread } from './useAssistantThread';

interface Props {
  context: AssistantContext;
  shareRisk: boolean;
  onShareRisk: (share: boolean) => void;
  /** 'page' for the dedicated view, 'drawer' for the workspace side panel. */
  variant?: 'page' | 'drawer';
  /** A question to send once, e.g. from a "Ask the assistant" link. */
  initialQuestion?: string | null;
  onInitialQuestionSent?: () => void;
  timeZone: string;
}

export function ContextChips({ context }: { context: AssistantContext }) {
  const items = describeContext(context);
  if (items.length === 0) return <p className="text-xs text-fg-3">No market data is shared. The assistant can only define terms.</p>;
  return (
    <ul aria-label="Data available to the assistant" className="flex flex-wrap gap-1.5">
      {items.map((i) => (
        <li key={i}>
          <Badge tone={i.includes('Model') ? 'forecast' : i.includes('risk') ? 'accent' : 'neutral'}>{i}</Badge>
        </li>
      ))}
    </ul>
  );
}

export function AssistantPanel(props: Props) {
  const access = useFeatureAccess('assistant');
  if (!access.allowed) return <PlanGate feature="assistant" className="h-full justify-center" />;
  return <AssistantPanelBody {...props} />;
}

function AssistantPanelBody({ context, shareRisk, onShareRisk, variant = 'page', initialQuestion, onInitialQuestionSent, timeZone }: Props) {
  const thread = useAssistantThread(context);
  const [draft, setDraft] = useState('');
  const logRef = useRef<HTMLDivElement>(null);
  const inputId = useId();
  const sentInitial = useRef(false);
  const { send } = thread;

  useEffect(() => {
    if (!initialQuestion || sentInitial.current) return;
    sentInitial.current = true;
    send(initialQuestion);
    onInitialQuestionSent?.();
  }, [initialQuestion, onInitialQuestionSent, send]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [thread.messages.length, thread.status]);

  const submit = () => {
    if (!draft.trim()) return;
    thread.send(draft);
    setDraft('');
  };

  const isDemo = thread.description.provider === 'demo-rules';
  const where = context.symbol && context.timeframe ? `${getInstrument(context.symbol).display} ${context.timeframe}` : null;

  return (
    <div className={cn('flex min-h-0 flex-col', variant === 'page' ? 'h-full' : 'h-full')}>
      {/* What the assistant is, and what it can see */}
      <div className="flex shrink-0 flex-col gap-3 border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={isDemo ? 'demo' : 'forecast'}>
            {isDemo ? <FlaskConical aria-hidden className="size-3" /> : <Bot aria-hidden className="size-3" />}
            {thread.description.label}
          </Badge>
          <p className="hidden min-w-0 flex-1 text-xs text-fg-3 sm:block">{thread.description.description}</p>
          <span className="flex-1 sm:hidden" />
          {thread.messages.length > 0 && <IconButton icon={Eraser} size="sm" label="Clear conversation" onClick={thread.clear} tooltipSide="left" />}
        </div>
        <div className="flex flex-col gap-2">
          <p className="eyebrow">Context{where ? ` · ${where}` : ''}</p>
          <ContextChips context={context} />
          <Switch checked={shareRisk} onChange={onShareRisk} label="Share my risk profile" description="Lets it size trades with your capital and limits." />
        </div>
      </div>

      {/* Conversation */}
      <div ref={logRef} role="log" aria-live="polite" aria-label="Conversation" tabIndex={0} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {thread.messages.length === 0 ? (
          <div className="flex flex-col gap-4">
            <div>
              <p className={cn('display text-fg', variant === 'page' ? 'text-d3' : 'text-xl')}>
                Question the evidence, <em>not the market.</em>
              </p>
              <p className="mt-2 max-w-xl text-sm text-fg-2">
                Answers are built only from the context above. Ask what the model saw, what would prove it wrong, or what a trade means for your capital.
              </p>
            </div>
            <ul className={cn('grid gap-2', variant === 'page' && 'sm:grid-cols-2')}>
              {SUGGESTED_PROMPTS.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => thread.send(p)}
                    className="group flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-inset px-3 py-2.5 text-left text-sm text-fg-2 transition-colors hover:border-line-strong hover:bg-hover hover:text-fg"
                  >
                    {p}
                    <ArrowUp aria-hidden className="size-3.5 shrink-0 rotate-45 text-fg-3 transition-transform group-hover:translate-x-0.5" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className="flex flex-col gap-5">
            {thread.messages.map((m) => (
              <li key={m.id} className={cn('flex gap-3', m.role === 'user' && 'flex-row-reverse')}>
                <span
                  aria-hidden
                  className={cn(
                    'mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-full border',
                    m.role === 'user' ? 'border-line-strong bg-raised text-fg-2' : 'border-forecast/40 bg-forecast-soft text-forecast',
                  )}
                >
                  {m.role === 'user' ? <UserRound className="size-3.5" /> : <Bot className="size-3.5" />}
                </span>
                <div className={cn('min-w-0', m.role === 'user' ? 'max-w-[85%]' : 'flex-1')}>
                  <p className="sr-only">{m.role === 'user' ? 'You said' : 'Assistant replied'}</p>
                  {m.role === 'user' ? (
                    <p className="rounded-2xl rounded-tr-sm bg-selected px-3.5 py-2 text-sm text-fg">{m.content}</p>
                  ) : (
                    <>
                      <Markdown source={m.content} />
                      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-3">
                        <span className="num">{formatClock(m.createdAt, timeZone, false)}</span>
                        {m.provider === 'demo-rules' && <span>· rule-based, not a language model</span>}
                        {m.contextUsed && m.contextUsed.length > 0 && <span>· used: {m.contextUsed.join(', ')}</span>}
                      </p>
                    </>
                  )}
                </div>
              </li>
            ))}
            {thread.status === 'pending' && (
              <li className="flex items-center gap-3 text-sm text-fg-3" role="status">
                <span aria-hidden className="inline-flex size-7 items-center justify-center rounded-full border border-forecast/40 bg-forecast-soft text-forecast">
                  <Bot className="size-3.5" />
                </span>
                <span className="inline-flex gap-1" aria-hidden>
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="size-1.5 animate-pulse rounded-full bg-fg-3" style={{ animationDelay: `${i * 150}ms` }} />
                  ))}
                </span>
                <span>Composing an answer from the context…</span>
              </li>
            )}
          </ol>
        )}
        {thread.status === 'error' && (
          <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-fg">
            <span className="flex-1">The assistant could not answer: {userMessage(thread.error)}</span>
            <Button size="sm" icon={RotateCw} onClick={thread.retry}>
              Retry
            </Button>
          </div>
        )}
      </div>

      {/* Composer */}
      <form
        className="shrink-0 border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {thread.messages.length > 0 && thread.status !== 'pending' && (
          <ul aria-label="Suggested questions" className="-mx-1 mb-2 flex gap-1.5 overflow-x-auto px-1 pb-1">
            {SUGGESTED_PROMPTS.map((p) => (
              <li key={p} className="shrink-0">
                <button
                  type="button"
                  onClick={() => thread.send(p)}
                  className="h-7 rounded-full border border-line px-3 text-xs whitespace-nowrap text-fg-2 hover:border-line-strong hover:bg-hover hover:text-fg"
                >
                  {p}
                </button>
              </li>
            ))}
          </ul>
        )}
        <label htmlFor={inputId} className="sr-only">
          Ask the assistant
        </label>
        <div className="flex items-end gap-2 rounded-xl border border-line-strong bg-inset p-1.5 focus-within:border-accent">
          <textarea
            id={inputId}
            rows={1}
            value={draft}
            maxLength={1000}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={where ? `Ask about ${where}…` : 'Ask about an analysis, a term or your risk…'}
            className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-fg placeholder:text-fg-3 focus:outline-none"
          />
          {thread.status === 'pending' ? (
            <Button size="md" shape="pill" icon={Square} onClick={thread.cancel} aria-label="Stop the answer">
              Stop
            </Button>
          ) : (
            <Button type="submit" size="md" shape="pill" variant="primary" icon={ArrowUp} disabled={!draft.trim()} aria-label="Send question">
              Send
            </Button>
          )}
        </div>
        <p className="mt-1.5 px-1 text-xs text-fg-3">Analysis support only — never financial advice, and it cannot place trades. History is kept in this browser.</p>
      </form>
    </div>
  );
}
