import { zodResolver } from '@hookform/resolvers/zod';
import { Send } from 'lucide-react';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field, FormError, Textarea } from '@/components/ui/Form';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import type { Post } from '@/domain/community';
import { getInstrument, INSTRUMENTS } from '@/domain/instruments';
import { ROLE_LABELS } from '@/domain/user';
import { useResource } from '@/hooks/useResource';
import { cn } from '@/lib/cn';
import { formatRelative } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { POST_MAX, postSchema, type PostForm } from './schemas';

function Composer({ onPublished }: { onPublished: (post: Post) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<PostForm>({ resolver: zodResolver(postSchema), defaultValues: { body: '', symbols: [] } });
  const length = form.watch('body').length;

  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      onPublished(await services.community.createPost(values));
      form.reset();
      notify('Post published.', 'success');
    } catch (e) {
      setError(userMessage(e));
    }
  });

  return (
    <form onSubmit={submit} noValidate className="rounded-lg border border-line bg-surface p-4">
      <FormError message={error} />
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

export function PostsPage() {
  const services = useServices();
  const res = useResource('posts', (signal) => services.community.listPosts({ signal }));

  return (
    <div className="flex flex-col gap-4">
      <Composer onPublished={(post) => res.setData((list) => [post, ...(list ?? [])])} />
      {res.status === 'loading' ? (
        <Loading label="Loading posts">
          <Skeleton className="h-24 w-full" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} title="Could not load posts" />
      ) : !res.data?.length ? (
        <EmptyState title="No posts yet" description="Be the first to share an analysis." />
      ) : (
        <ul className="flex flex-col gap-3">
          {res.data.map((p) => (
            <li key={p.id}>
              <article className="rounded-lg border border-line bg-surface p-4">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-fg">{p.author.name}</span>
                  <Badge>{ROLE_LABELS[p.author.role]}</Badge>
                  <span className="text-xs text-fg-3">{formatRelative(p.createdAt)}</span>
                </div>
                <p className="mt-2 text-sm whitespace-pre-line text-fg">{p.body}</p>
                {p.symbols.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {p.symbols.map((s) => (
                      <Badge key={s}>{getInstrument(s).display}</Badge>
                    ))}
                  </div>
                )}
              </article>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
