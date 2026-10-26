import { ArrowLeft, UserMinus, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { buttonClasses } from '@/components/ui/buttonClasses';
import { Panel, Stat } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, Skeleton } from '@/components/ui/StateViews';
import { ROLE_LABELS } from '@/domain/user';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatNumber, formatRelative } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';

/** A member's public profile (backend: GET /users/{id}/profile, follow / unfollow). */
export function ProfilePage() {
  const { userId = '' } = useParams();
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const res = useResource(`profile:${userId}`, (signal) => services.social.profile(userId, { signal }));
  const [busy, setBusy] = useState(false);
  usePageTitle(res.data ? `${res.data.name} · Community` : 'Profile');

  const back = (
    <Link to="/community/people" className={buttonClasses({ variant: 'ghost', size: 'sm', className: 'self-start' })}>
      <ArrowLeft aria-hidden className="size-4" />
      People
    </Link>
  );

  if (res.status === 'loading')
    return (
      <Loading label="Loading profile">
        <Skeleton className="h-40 w-full" />
      </Loading>
    );
  if (res.status === 'error' && !res.data)
    return (
      <div className="flex flex-col gap-3">
        {back}
        {isApiError(res.error) && res.error.kind === 'not_found' ? (
          <EmptyState title="Profile not found" description="This member does not exist or their account was removed." />
        ) : (
          <ErrorState error={res.error} onRetry={res.reload} title="Could not load the profile" />
        )}
      </div>
    );
  const p = res.data;
  if (!p) return null;

  const toggleFollow = async () => {
    setBusy(true);
    try {
      const state = p.isFollowing ? await services.social.unfollow(p.id) : await services.social.follow(p.id);
      res.setData((prev) => ({ ...(prev ?? p), isFollowing: state.following, followers: state.followers }));
      notify(state.following ? `You now follow ${p.name}.` : `You no longer follow ${p.name}.`, state.following ? 'success' : 'info');
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {back}
      <section aria-labelledby="profile-name" className="rounded-lg border border-line bg-surface p-4">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 id="profile-name" className="flex flex-wrap items-center gap-2 text-lg font-semibold text-fg">
              {p.name} <Badge>{ROLE_LABELS[p.role]}</Badge>
            </h2>
            <p className="mt-0.5 text-xs text-fg-3">Member since {formatDate(p.memberSince, timeZone)}</p>
          </div>
          {p.followable && (
            <Button variant={p.isFollowing ? 'secondary' : 'primary'} icon={p.isFollowing ? UserMinus : UserPlus} loading={busy} onClick={() => void toggleFollow()}>
              {p.isFollowing ? 'Unfollow' : 'Follow'}
            </Button>
          )}
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-4">
          <Stat label="Posts" value={<span className="num">{formatNumber(p.posts)}</span>} />
          <Stat label="Followers" value={<span className="num">{formatNumber(p.followers)}</span>} />
          <Stat label="Following" value={<span className="num">{formatNumber(p.following)}</span>} />
        </dl>
        {!p.followable && <p className="mt-3 text-xs text-fg-3">Only analysts and experts can be followed.</p>}
      </section>

      <Panel title="Recent posts" flush>
        {p.recentPosts.length === 0 ? (
          <EmptyState title="No posts yet" compact />
        ) : (
          <ul className="divide-y divide-line">
            {p.recentPosts.map((post) => (
              <li key={post.id} className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-2.5 text-sm">
                <span className="min-w-0 text-fg">{post.title}</span>
                <span className="text-xs text-fg-3">{formatRelative(post.createdAt)}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Public strategies" meta={<span>Rule-based strategies this member shares</span>} flush>
        {p.publicStrategies.length === 0 ? (
          <EmptyState title="No public strategies" compact />
        ) : (
          <ul className="divide-y divide-line">
            {p.publicStrategies.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-medium text-fg">
                    {s.name} <Badge>{s.kind}</Badge>
                  </p>
                  {s.description && <p className="text-xs text-fg-3">{s.description}</p>}
                </div>
                <Link to="/strategies" className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
                  Open strategies
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
