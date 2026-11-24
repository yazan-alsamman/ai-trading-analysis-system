import { zodResolver } from '@hookform/resolvers/zod';
import { Flag, Pencil, Reply, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Field, FormError, Textarea } from '@/components/ui/Form';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { Comment } from '@/domain/community';
import { ROLE_LABELS } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { formatRelative } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { commentSchema, type CommentForm } from './schemas';
import { ReportDialog } from './socialUi';

/** Inline form for a reply or an edit (backend only). Same limits as a new comment. */
function InlineCommentForm({ label, initial, submitLabel, onSubmit, onCancel }: { label: string; initial: string; submitLabel: string; onSubmit: (body: string) => Promise<void>; onCancel: () => void }) {
  const [body, setBody] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const parsed = commentSchema.safeParse({ body });
    if (!parsed.success) return setError(parsed.error.issues[0]?.message ?? 'Check the comment.');
    setBusy(true);
    setError(null);
    try {
      await onSubmit(parsed.data.body);
    } catch (e) {
      setError(userMessage(e));
      setBusy(false);
    }
  };

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      className="mt-2 flex flex-col gap-2"
    >
      <FormError message={error} />
      <Field label={label}>
        {({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} rows={2} className="min-h-16" autoFocus value={body} onChange={(e) => setBody(e.target.value)} />}
      </Field>
      <div className="flex justify-end gap-2">
        <Button size="sm" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" type="submit" loading={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

interface ThreadActions {
  replyingTo: string | null;
  editingId: string | null;
  setReplyingTo: (id: string | null) => void;
  setEditingId: (id: string | null) => void;
  reply: (parent: Comment, body: string) => Promise<void>;
  edit: (comment: Comment, body: string) => Promise<void>;
  onDelete: (comment: Comment) => void;
  onReport: (comment: Comment) => void;
}

function CommentItem({ comment: c, replies, actions }: { comment: Comment; replies: Map<string, Comment[]>; actions: ThreadActions | null }) {
  const children = replies.get(c.id) ?? [];
  const editing = actions?.editingId === c.id;
  return (
    <li className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-fg">{c.author.name}</span>
        <Badge>{ROLE_LABELS[c.author.role]}</Badge>
        <span className="text-xs text-fg-3">{formatRelative(c.createdAt)}</span>
        {c.editedAt ? <span className="text-xs text-fg-3">· edited</span> : null}
        {actions && !editing && (
          <span className="ml-auto flex items-center gap-0.5">
            <IconButton icon={Reply} label={`Reply to ${c.author.name}`} size="sm" onClick={() => actions.setReplyingTo(c.id)} tooltipSide="top" />
            {c.canEdit && (
              <>
                <IconButton icon={Pencil} label="Edit comment" size="sm" onClick={() => actions.setEditingId(c.id)} tooltipSide="top" />
                <IconButton icon={Trash2} label="Delete comment" size="sm" onClick={() => actions.onDelete(c)} tooltipSide="top" />
              </>
            )}
            <IconButton icon={Flag} label="Report comment" size="sm" onClick={() => actions.onReport(c)} tooltipSide="top" />
          </span>
        )}
      </div>
      {editing && actions ? (
        <InlineCommentForm label="Edit comment" initial={c.body} submitLabel="Save" onSubmit={(body) => actions.edit(c, body)} onCancel={() => actions.setEditingId(null)} />
      ) : (
        <p className="mt-0.5 text-fg-2">{c.body}</p>
      )}
      {actions?.replyingTo === c.id && (
        <InlineCommentForm label={`Reply to ${c.author.name}`} initial="" submitLabel="Reply" onSubmit={(body) => actions.reply(c, body)} onCancel={() => actions.setReplyingTo(null)} />
      )}
      {children.length > 0 && (
        <ul aria-label={`Replies to ${c.author.name}`} className="mt-3 ml-3 flex flex-col gap-3 border-l border-line pl-3">
          {children.map((r) => (
            <CommentItem key={r.id} comment={r} replies={replies} actions={actions} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function CommentThread({ threadId, onAdded }: { threadId: string; onAdded: () => void }) {
  const services = useServices();
  const { notify } = useToast();
  const isApi = services.source === 'api';
  const res = useResource(`comments:${threadId}`, (signal) => services.community.listComments(threadId, { signal }));
  const [error, setError] = useState<string | null>(null);
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Comment | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [reporting, setReporting] = useState<Comment | null>(null);
  const form = useForm<CommentForm>({ resolver: zodResolver(commentSchema), defaultValues: { body: '' } });

  const submit = form.handleSubmit(async ({ body }) => {
    setError(null);
    try {
      const comment = await services.community.addComment(threadId, body);
      res.setData((list) => [...(list ?? []), comment]);
      form.reset();
      onAdded();
    } catch (e) {
      setError(userMessage(e));
    }
  });

  const actions: ThreadActions | null = isApi
    ? {
        replyingTo,
        editingId,
        setReplyingTo: (id) => {
          setEditingId(null);
          setReplyingTo(id);
        },
        setEditingId: (id) => {
          setReplyingTo(null);
          setEditingId(id);
        },
        reply: async (parent, body) => {
          const comment = await services.community.addComment(threadId, body, parent.id);
          res.setData((list) => [...(list ?? []), comment]);
          setReplyingTo(null);
          onAdded();
        },
        edit: async (comment, body) => {
          await services.social.updateComment(comment.id, body);
          res.setData((list) => (list ?? []).map((x) => (x.id === comment.id ? { ...x, body, editedAt: Date.now() } : x)));
          setEditingId(null);
          notify('Comment updated.', 'success');
        },
        onDelete: setDeleting,
        onReport: setReporting,
      }
    : null;

  const confirmDelete = async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await services.social.deleteComment(deleting.id);
      res.setData((list) => (list ?? []).filter((x) => x.id !== deleting.id));
      notify('Comment deleted.', 'info');
      setDeleting(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setDeleteBusy(false);
    }
  };

  // Replies are grouped under their parent; a reply whose parent is not shown (deleted, hidden) stays at the top level.
  const comments = res.data ?? [];
  const ids = new Set(comments.map((c) => c.id));
  const replies = new Map<string, Comment[]>();
  const roots: Comment[] = [];
  for (const c of comments) {
    if (c.parentId && ids.has(c.parentId)) replies.set(c.parentId, [...(replies.get(c.parentId) ?? []), c]);
    else roots.push(c);
  }

  return (
    <div className="mt-3 border-t border-line pt-3">
      {res.status === 'loading' ? (
        <Loading label="Loading comments">
          <SkeletonRows rows={2} />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact title="Could not load comments" />
      ) : (
        <ul className="flex flex-col gap-3">
          {comments.length === 0 && <li className="text-sm text-fg-3">No comments yet. Start the discussion.</li>}
          {roots.map((c) => (
            <CommentItem key={c.id} comment={c} replies={replies} actions={actions} />
          ))}
        </ul>
      )}

      <form onSubmit={submit} noValidate className="mt-3 flex flex-col gap-2">
        <FormError message={error} />
        <Field label="Add a comment" error={form.formState.errors.body?.message}>
          {({ id, describedBy, invalid }) => <Textarea id={id} aria-describedby={describedBy} invalid={invalid} rows={2} className="min-h-16" {...form.register('body')} />}
        </Field>
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-fg-3">{services.source === 'demo' ? 'Demo: your comment is kept for this session only.' : 'Be respectful. No investment solicitations.'}</p>
          <Button type="submit" size="sm" variant="primary" loading={form.formState.isSubmitting}>
            Comment
          </Button>
        </div>
      </form>

      {isApi && (
        <>
          <ConfirmDialog
            open={deleting !== null}
            title="Delete comment?"
            description="The comment is removed from the discussion for everyone."
            confirmLabel="Delete comment"
            busy={deleteBusy}
            onConfirm={() => void confirmDelete()}
            onCancel={() => setDeleting(null)}
          />
          <ReportDialog target="comment" targetId={reporting?.id ?? null} open={reporting !== null} onClose={() => setReporting(null)} />
        </>
      )}
    </div>
  );
}
