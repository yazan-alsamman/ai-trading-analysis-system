import { zodResolver } from '@hookform/resolvers/zod';
import { EyeOff, Flag, MessageSquare, Pencil, Send, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Link } from 'react-router';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Field, FormError, Input, Select, Textarea } from '@/components/ui/Form';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import type { Post } from '@/domain/community';
import { getInstrument, INSTRUMENTS } from '@/domain/instruments';
import { TIMEFRAMES, type Timeframe } from '@/domain/market';
import type { PostDirection, PostVisibility } from '@/domain/social';
import { ROLE_LABELS } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatRelative } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { CommentThread } from './CommentThread';
import { POST_MAX, postSchema, type PostForm } from './schemas';
import { DIRECTION_LABELS, VISIBILITY_LABELS } from './socialFormat';
import { DirectionBadge, EditPostDialog, LikeButton, ReportDialog } from './socialUi';

/** Backend-only post options (direction, timeframe, visibility, title). */
interface PostExtras {
  title: string;
  direction: PostDirection | '';
  timeframe: Timeframe | '';
  visibility: PostVisibility;
}
const NO_EXTRAS: PostExtras = { title: '', direction: '', timeframe: '', visibility: 'public' };

function Composer({ onPublished }: { onPublished: (post: Post) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const isApi = services.source === 'api';
  const [error, setError] = useState<string | null>(null);
  const [extras, setExtras] = useState<PostExtras>(NO_EXTRAS);
  const form = useForm<PostForm>({ resolver: zodResolver(postSchema), defaultValues: { body: '', symbols: [] } });
  const length = form.watch('body').length;

  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      onPublished(
        await services.community.createPost(
          isApi
            ? {
                ...values,
                ...(extras.title.trim() ? { title: extras.title.trim() } : {}),
                direction: extras.direction || null,
                timeframe: extras.timeframe || null,
                visibility: extras.visibility,
              }
            : values,
        ),
      );
      form.reset();
      setExtras(NO_EXTRAS);
      notify('Post published.', 'success');
    } catch (e) {
      setError(userMessage(e));
    }
  });

  return (
    <form onSubmit={submit} noValidate className="rounded-lg border border-line bg-surface p-4">
      <FormError message={error} />
      {isApi && (
        <Field label="Title" optional hint="Defaults to the first line of your post." className="mb-3">
          {({ id, describedBy }) => (
            <Input id={id} aria-describedby={describedBy} maxLength={140} value={extras.title} onChange={(e) => setExtras({ ...extras, title: e.target.value })} />
          )}
        </Field>
      )}
      <Field label="New post" error={form.formState.errors.body?.message} hint="Share analysis or questions. Do not share personal data or solicit investments.">
        {({ id, describedBy, invalid }) => (
          <Textarea id={id} aria-describedby={describedBy} invalid={invalid} rows={3} placeholder="What are you watching?" {...form.register('body')} />
        )}
      </Field>
      <fieldset className="mt-3">
        <legend className="mb-2 text-xs font-medium text-fg-3">Tag instruments (up to 4)</legend>
        <Controller
          control={form.control}
          name="symbols"
          render={({ field }) => (
            <div className="flex flex-wrap gap-1.5">
              {INSTRUMENTS.map((i) => {
                const on = field.value.includes(i.symbol);
                return (
                  <button
                    key={i.symbol}
                    type="button"
                    aria-pressed={on}
                    onClick={() => field.onChange(on ? field.value.filter((s) => s !== i.symbol) : [...field.value, i.symbol])}
                    className={cn(
                      'h-7 rounded-md border px-2 text-xs font-medium transition-colors',
                      on ? 'border-accent bg-accent-soft text-accent' : 'border-line text-fg-2 hover:bg-hover hover:text-fg',
                    )}
                  >
                    {i.display}
                  </button>
                );
              })}
            </div>
          )}
        />
        {form.formState.errors.symbols?.message && <p className="mt-1.5 text-xs text-danger">{form.formState.errors.symbols.message}</p>}
      </fieldset>
      {isApi && (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Field label="Direction" optional>
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={extras.direction} onChange={(e) => setExtras({ ...extras, direction: e.target.value as PostDirection | '' })}>
                <option value="">None</option>
                {(Object.keys(DIRECTION_LABELS) as PostDirection[]).map((d) => (
                  <option key={d} value={d}>
                    {DIRECTION_LABELS[d]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Timeframe" optional>
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={extras.timeframe} onChange={(e) => setExtras({ ...extras, timeframe: e.target.value as Timeframe | '' })}>
                <option value="">None</option>
                {TIMEFRAMES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.id}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Visibility" hint="Subscribers-only posts are for experts.">
            {({ id, describedBy }) => (
              <Select id={id} aria-describedby={describedBy} value={extras.visibility} onChange={(e) => setExtras({ ...extras, visibility: e.target.value as PostVisibility })}>
                {(Object.keys(VISIBILITY_LABELS) as PostVisibility[]).map((v) => (
                  <option key={v} value={v}>
                    {VISIBILITY_LABELS[v]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      )}
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className={cn('num text-xs', length > POST_MAX ? 'text-danger' : 'text-fg-3')} aria-live="polite">
          {length}/{POST_MAX}
        </span>
        <Button type="submit" variant="primary" icon={Send} loading={form.formState.isSubmitting}>
          Publish
        </Button>
      </div>
    </form>
  );
}

interface PostActions {
  onChange: (post: Post) => void;
  onEdit: (post: Post) => void;
  onDelete: (post: Post) => void;
  onReport: (post: Post) => void;
}

function PostCard({ post: p, actions }: { post: Post; actions: PostActions | null }) {
  const [commentsOpen, setCommentsOpen] = useState(false);
  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {actions ? (
          <Link to={`/community/people/${p.author.id}`} className="font-medium text-fg underline-offset-2 hover:underline">
            {p.author.name}
          </Link>
        ) : (
          <span className="font-medium text-fg">{p.author.name}</span>
        )}
        <Badge>{ROLE_LABELS[p.author.role]}</Badge>
        <span className="text-xs text-fg-3">{formatRelative(p.createdAt)}</span>
        {p.editedAt ? <span className="text-xs text-fg-3">· edited</span> : null}
        {p.visibility && p.visibility !== 'public' && <Badge tone="info">{VISIBILITY_LABELS[p.visibility]}</Badge>}
      </div>
      {p.status === 'hidden' && (
        <p className="mt-2 flex items-center gap-1.5 rounded-md bg-warning-soft px-2.5 py-1.5 text-xs text-fg">
          <EyeOff aria-hidden className="size-3.5 shrink-0 text-warning" />
          Hidden by moderation. Only you can see this post.
        </p>
      )}
      {p.title && <h3 className="mt-2 text-sm font-semibold text-fg">{p.title}</h3>}
      <p className={cn('text-sm whitespace-pre-line text-fg', p.title ? 'mt-1' : 'mt-2')}>{p.body}</p>
      {(p.symbols.length > 0 || p.instrumentLabel || p.direction || p.timeframe) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {p.symbols.map((s) => (
            <Badge key={s}>{getInstrument(s).display}</Badge>
          ))}
          {p.symbols.length === 0 && p.instrumentLabel && <Badge>{p.instrumentLabel}</Badge>}
          {p.direction && <DirectionBadge direction={p.direction} />}
          {p.timeframe && <Badge>{p.timeframe}</Badge>}
        </div>
      )}
      {actions && (
        <>
          <div className="mt-3 flex flex-wrap items-center gap-1 border-t border-line pt-2">
            <LikeButton post={p} onChange={(s) => actions.onChange({ ...p, likedByMe: s.liked, likes: s.likes })} />
            <button
              type="button"
              aria-expanded={commentsOpen}
              aria-controls={`post-comments-${p.id}`}
              onClick={() => setCommentsOpen((o) => !o)}
              className={cn('inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium hover:bg-hover', commentsOpen ? 'text-fg' : 'text-fg-2')}
            >
              <MessageSquare aria-hidden className="size-4" />
              {p.commentCount} {p.commentCount === 1 ? 'comment' : 'comments'}
            </button>
            <span className="ml-auto flex items-center gap-1">
              {p.canEdit && (
                <>
                  <IconButton icon={Pencil} label="Edit post" size="sm" onClick={() => actions.onEdit(p)} tooltipSide="top" />
                  <IconButton icon={Trash2} label="Delete post" size="sm" onClick={() => actions.onDelete(p)} tooltipSide="top" />
                </>
              )}
              <IconButton icon={Flag} label="Report post" size="sm" onClick={() => actions.onReport(p)} tooltipSide="top" />
            </span>
          </div>
          {commentsOpen && (
            <div id={`post-comments-${p.id}`}>
              <CommentThread threadId={p.id} onAdded={() => actions.onChange({ ...p, commentCount: p.commentCount + 1 })} />
            </div>
          )}
        </>
      )}
    </article>
  );
}

export function PostsPage() {
  const services = useServices();
  const { notify } = useToast();
  const isApi = services.source === 'api';
  const [scope, setScope] = useState<'all' | 'following'>('all');
  const res = useResource(`posts:${scope}`, (signal) => services.community.listPosts(isApi && scope === 'following' ? { signal, scope } : { signal }));
  const [editing, setEditing] = useState<Post | null>(null);
  const [deleting, setDeleting] = useState<Post | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [reporting, setReporting] = useState<Post | null>(null);

  const replace = (post: Post) => res.setData((list) => (list ?? []).map((x) => (x.id === post.id ? post : x)));
  const actions: PostActions | null = isApi ? { onChange: replace, onEdit: setEditing, onDelete: setDeleting, onReport: setReporting } : null;

  const confirmDelete = async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await services.social.deletePost(deleting.id);
      res.setData((list) => (list ?? []).filter((x) => x.id !== deleting.id));
      notify('Post deleted.', 'info');
      setDeleting(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Composer onPublished={(post) => res.setData((list) => [post, ...(list ?? [])])} />
      {isApi && (
        <SegmentedControl
          label="Show posts from"
          value={scope}
          onChange={setScope}
          options={[
            { value: 'all', label: 'All' },
            { value: 'following', label: 'Following' },
          ]}
        />
      )}
      {res.status === 'loading' ? (
        <Loading label="Loading posts">
          <Skeleton className="h-24 w-full" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} title="Could not load posts" />
      ) : !res.data?.length ? (
        scope === 'following' ? (
          <EmptyState title="No posts from people you follow" description="Follow analysts and experts from their profile to see their posts here." />
        ) : (
          <EmptyState title="No posts yet" description="Be the first to share an analysis." />
        )
      ) : (
        <ul className="flex flex-col gap-3">
          {res.data.map((p) => (
            <li key={p.id}>
              <PostCard post={p} actions={actions} />
            </li>
          ))}
        </ul>
      )}

      {isApi && (
        <>
          <EditPostDialog post={editing} onClose={() => setEditing(null)} onSaved={replace} />
          <ConfirmDialog
            open={deleting !== null}
            title="Delete post?"
            description="The post and its discussion disappear for everyone. Deleting does not refill your daily posting limit."
            confirmLabel="Delete post"
            busy={deleteBusy}
            onConfirm={() => void confirmDelete()}
            onCancel={() => setDeleting(null)}
          />
          <ReportDialog target="post" targetId={reporting?.id ?? null} open={reporting !== null} onClose={() => setReporting(null)} />
        </>
      )}
    </div>
  );
}
