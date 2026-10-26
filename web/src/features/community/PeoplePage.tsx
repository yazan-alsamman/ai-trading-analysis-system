import { UserMinus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { FollowEntry } from '@/domain/social';
import { ROLE_LABELS } from '@/domain/user';
import { useResource, type Resource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { userMessage } from '@/services/errors';

function FollowList({
  title,
  res,
  empty,
  sinceLabel,
  onUnfollow,
}: {
  title: string;
  res: Resource<FollowEntry[]>;
  empty: { title: string; description: string };
  sinceLabel: string;
  onUnfollow?: (entry: FollowEntry) => Promise<void>;
}) {
  const { timeZone } = usePreferences();
  const [busyId, setBusyId] = useState<string | null>(null);

  return (
    <Panel title={title} meta={res.data && <span>{res.data.length}</span>} flush>
      {res.status === 'loading' ? (
        <Loading label={`Loading ${title.toLowerCase()}`}>
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState title={empty.title} description={empty.description} compact />
      ) : (
        <ul className="divide-y divide-line">
          {res.data.map((entry) => (
            <li key={entry.user.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  <Link to={`/community/people/${entry.user.id}`} className="font-medium text-fg underline-offset-2 hover:underline">
                    {entry.user.name}
                  </Link>
                  <Badge>{ROLE_LABELS[entry.user.role]}</Badge>
                </p>
                <p className="text-xs text-fg-3">
                  {sinceLabel} {formatDate(entry.since, timeZone)}
                </p>
              </div>
              {onUnfollow && (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={UserMinus}
                  loading={busyId === entry.user.id}
                  onClick={() => {
                    setBusyId(entry.user.id);
                    void onUnfollow(entry).finally(() => setBusyId(null));
                  }}
                >
                  Unfollow
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Who you follow and who follows you (backend: /me/following, /me/followers). */
export function PeoplePage() {
  const services = useServices();
  const { notify } = useToast();
  const following = useResource('following', (signal) => services.social.following({ signal }));
  const followers = useResource('followers', (signal) => services.social.followers({ signal }));

  const unfollow = async (entry: FollowEntry) => {
    try {
      await services.social.unfollow(entry.user.id);
      following.setData((list) => (list ?? []).filter((x) => x.user.id !== entry.user.id));
      notify(`You no longer follow ${entry.user.name}.`, 'info');
    } catch (e) {
      notify(userMessage(e), 'danger');
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-2">
        Follow analysts and experts from their profile to see their posts under <span className="text-fg">Posts → Following</span> and be notified when they publish.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <FollowList
          title="Following"
          res={following}
          sinceLabel="Following since"
          empty={{ title: 'You do not follow anyone yet', description: 'Open an author’s name on a post to see their profile and follow them.' }}
          onUnfollow={unfollow}
        />
        <FollowList
          title="Followers"
          res={followers}
          sinceLabel="Follows you since"
          empty={{ title: 'No followers yet', description: 'Analysts and experts can be followed by other members.' }}
        />
      </div>
    </div>
  );
}
