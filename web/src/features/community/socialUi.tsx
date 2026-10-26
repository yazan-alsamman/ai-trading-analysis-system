import { Heart } from 'lucide-react';
import { useState } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, FormError, Input, Select, Textarea } from '@/components/ui/Form';
import type { Post } from '@/domain/community';
import type { PostDirection, PostVisibility, ReportTarget } from '@/domain/social';
import { cn } from '@/lib/cn';
import { userMessage } from '@/services/errors';
import { POST_MAX } from './schemas';
import { DIRECTION_LABELS, VISIBILITY_LABELS } from './socialFormat';

/* Backend community controls (docs/news-posts.md). Rendered in API mode only. */

const DIRECTION_TONE: Record<PostDirection, BadgeTone> = { bullish: 'up', bearish: 'down', neutral: 'neutral' };

export function DirectionBadge({ direction }: { direction: PostDirection }) {
  return <Badge tone={DIRECTION_TONE[direction]}>{DIRECTION_LABELS[direction]}</Badge>;
}

/** Like toggle: optimistic, reverted on error; the server's answer is authoritative. */
export function LikeButton({ post, onChange }: { post: Post; onChange: (state: { liked: boolean; likes: number }) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [busy, setBusy] = useState(false);
  const liked = post.likedByMe === true;
  const likes = post.likes ?? 0;

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    const previous = { liked, likes };
    onChange({ liked: !liked, likes: Math.max(0, likes + (liked ? -1 : 1)) });
    try {
      onChange(liked ? await services.social.unlikePost(post.id) : await services.social.likePost(post.id));
    } catch (e) {
      onChange(previous);
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      aria-pressed={liked}
      aria-label={liked ? `Unlike (${likes} likes)` : `Like (${likes} likes)`}
      onClick={() => void toggle()}
      disabled={busy || post.status === 'hidden'}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors hover:bg-hover disabled:cursor-not-allowed disabled:opacity-60',
        liked ? 'text-down' : 'text-fg-2',
      )}
    >
      <Heart aria-hidden className={cn('size-4', liked && 'fill-current')} />
      <span className="num">{likes}</span>
    </button>
  );
}

/** Report content to the moderators (POST /reports: 3–500 characters). */
export function ReportDialog({ target, targetId, open, onClose }: { target: ReportTarget; targetId: string | null; open: boolean; onClose: () => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const formId = `report-${target}-form`;

  const close = () => {
    setReason('');
    setError(null);
    onClose();
  };

  const submit = async () => {
    const text = reason.trim();
    if (text.length < 3 || text.length > 500) return setError('Describe the problem in 3 to 500 characters.');
    if (!targetId) return;
    setBusy(true);
    setError(null);
    try {
      await services.social.report(target, targetId, text);
      notify('Report sent to the moderators. Thank you.', 'success');
      close();
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title={`Report ${target}`}
      description="Moderators review every report. Reporting the same content twice keeps your first report."
      size="sm"
      footer={
        <>
          <Button onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={busy}>
            Send report
          </Button>
        </>
      }
    >
      <form
        id={formId}
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        className="flex flex-col gap-3"
      >
        <FormError message={error} />
        <Field label="Reason" hint="For example: spam, pump and dump, abusive language.">
          {({ id, describedBy, invalid }) => (
            <Textarea id={id} aria-describedby={describedBy} invalid={invalid} rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          )}
        </Field>
      </form>
    </Dialog>
  );
}

/** Edit a post (PATCH /posts/{id}): the author within 24 hours, or an admin — the server decides (`can_edit`). */
export function EditPostDialog({ post, onClose, onSaved }: { post: Post | null; onClose: () => void; onSaved: (post: Post) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [draft, setDraft] = useState({ title: '', body: '', direction: '' as PostDirection | '', visibility: 'public' as PostVisibility });
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (post && post.id !== loadedId) {
    setLoadedId(post.id);
    setDraft({ title: post.title ?? '', body: post.body, direction: post.direction ?? '', visibility: post.visibility ?? 'public' });
    setError(null);
  }

  const submit = async () => {
    if (!post) return;
    const title = draft.title.trim();
    const body = draft.body.trim();
    if (!title || title.length > 140) return setError('The title needs 1 to 140 characters.');
    if (body.length < 10 || body.length > POST_MAX) return setError(`The post needs 10 to ${POST_MAX} characters.`);
    setBusy(true);
    setError(null);
    try {
      onSaved(await services.social.updatePost(post.id, { title, body, direction: draft.direction || null, visibility: draft.visibility }));
      notify('Post updated.', 'success');
      onClose();
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={post !== null}
      onClose={onClose}
      title="Edit post"
      description="Posts can be edited within 24 hours of publishing."
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="edit-post-form" loading={busy}>
            Save changes
          </Button>
        </>
      }
    >
      <form
        id="edit-post-form"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        className="flex flex-col gap-4"
      >
        <FormError message={error} />
        <Field label="Title">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} maxLength={140} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />}
        </Field>
        <Field label="Post">
          {({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} rows={5} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Direction" optional>
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={draft.direction} onChange={(e) => setDraft({ ...draft, direction: e.target.value as PostDirection | '' })}>
                <option value="">None</option>
                {(Object.keys(DIRECTION_LABELS) as PostDirection[]).map((d) => (
                  <option key={d} value={d}>
                    {DIRECTION_LABELS[d]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Visibility" hint="Subscribers-only posts are for experts.">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={draft.visibility} onChange={(e) => setDraft({ ...draft, visibility: e.target.value as PostVisibility })}>
                {(Object.keys(VISIBILITY_LABELS) as PostVisibility[]).map((v) => (
                  <option key={v} value={v}>
                    {VISIBILITY_LABELS[v]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      </form>
    </Dialog>
  );
}
