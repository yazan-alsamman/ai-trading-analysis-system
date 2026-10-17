import { ArrowRight, BookOpen, CircleDashed, FileSearch, FlaskConical, GitCompareArrows, HelpCircle, ListChecks, Scale, TriangleAlert, type LucideIcon } from 'lucide-react';
import { Markdown } from '@/components/ui/Markdown';
import { REPLY_KINDS, type AssistantMessage, type ReplyKind, type SuggestedPrompt } from '@/domain/assistant';
import { formatClock } from '@/lib/format';
import { splitSimulatedNote } from './replyText';

const KIND_ICON: Record<ReplyKind, LucideIcon> = {
  explain: FileSearch,
  evidence: ListChecks,
  invalidate: TriangleAlert,
  risk: Scale,
  compare: GitCompareArrows,
  missing: CircleDashed,
  glossary: BookOpen,
  unknown: HelpCircle,
};

/**
 * One assistant answer, laid out as a research note: what kind of answer it is,
 * the answer itself, a separate "simulated data" callout, what it was based
 * on, and the research step that usually comes next.
 */
export function ReplyCard({ message, timeZone, onFollowUp, followUpsEnabled }: { message: AssistantMessage; timeZone: string; onFollowUp: (p: SuggestedPrompt) => void; followUpsEnabled: boolean }) {
  const kind = message.kind;
  const meta = kind ? REPLY_KINDS[kind] : null;
  const Icon = kind ? KIND_ICON[kind] : null;
  const { body, note } = splitSimulatedNote(message.content);

  return (
    <article className="reply-card m-in overflow-hidden rounded-2xl border border-line bg-surface" aria-label={meta ? `Assistant answer: ${meta.label}` : 'Assistant answer'}>
      {meta && Icon && (
        <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <Icon aria-hidden className="size-3.5 text-forecast" />
          <p className="text-xs font-medium tracking-wide text-fg-2 uppercase">{meta.label}</p>
        </header>
      )}
      <div className="px-4 py-3">
        <Markdown source={body} />
        {note && (
          <p className="mt-3 flex gap-2 rounded-lg border border-dashed border-demo/50 bg-demo-soft px-3 py-2 text-xs text-fg-2">
            <FlaskConical aria-hidden className="mt-0.5 size-3.5 shrink-0 text-demo" />
            <span>
              <strong className="font-semibold text-fg">Simulated data.</strong> {note}
            </span>
          </p>
        )}
      </div>
      <footer className="flex flex-col gap-2 border-t border-line bg-inset/60 px-4 py-2.5">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-3">
          <span className="num">{formatClock(message.createdAt, timeZone, false)}</span>
          {message.provider === 'demo-rules' && <span>· rule-based, not a language model</span>}
          {message.contextUsed && message.contextUsed.length > 0 && <span>· used: {message.contextUsed.join(', ')}</span>}
        </p>
        {meta && followUpsEnabled && meta.next.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-fg-3">Next research step:</span>
            {meta.next.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => onFollowUp(p)}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-forecast/30 px-2.5 text-xs text-fg-2 transition-colors hover:border-forecast/60 hover:bg-forecast-soft hover:text-fg"
              >
                {p}
                <ArrowRight aria-hidden className="size-3" />
              </button>
            ))}
          </div>
        )}
      </footer>
    </article>
  );
}
