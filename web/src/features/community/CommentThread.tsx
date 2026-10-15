import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field, FormError, Textarea } from '@/components/ui/Form';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { ROLE_LABELS } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { formatRelative } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { commentSchema, type CommentForm } from './schemas';

export function CommentThread({ threadId, onAdded }: { threadId: string; onAdded: () => void }) {
  const services = useServices();
  const res = useResource(`comments:${threadId}`, (signal) => services.community.listComments(threadId, { signal }));
  const [error, setError] = useState<string | null>(null);
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
          {(res.data ?? []).length === 0 && <li className="text-sm text-fg-3">No comments yet. Start the discussion.</li>}
          {(res.data ?? []).map((c) => (
            <li key={c.id} className="text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-fg">{c.author.name}</span>
                <Badge>{ROLE_LABELS[c.author.role]}</Badge>
                <span className="text-xs text-fg-3">{formatRelative(c.createdAt)}</span>
              </div>
              <p className="mt-0.5 text-fg-2">{c.body}</p>
            </li>
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
    </div>
  );
}
