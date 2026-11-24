import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { Field, FormError, Select } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { AI_GRADES, AI_PROFILES, type AIFollow, type AIGrade } from '@/domain/aiSetups';
import type { BackendInstrument } from '@/domain/strategies';
import type { Resource } from '@/hooks/useResource';
import { formatDate } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { instrumentLabel } from './setupFormat';

/** Follows decide who is told when a setup becomes ARMED (docs/notifications.md, B11). */
export function FollowsPanel({ follows, instruments }: { follows: Resource<AIFollow[]>; instruments: Resource<BackendInstrument[]> }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const active = (instruments.data ?? []).filter((i) => i.isActive);
  const [instrumentId, setInstrumentId] = useState('');
  const [profile, setProfile] = useState<string>(AI_PROFILES[0]);
  const [grade, setGrade] = useState<AIGrade | ''>('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chosen = instrumentId || active[0]?.id || '';

  const add = async () => {
    if (!chosen) return;
    setBusy('add');
    setError(null);
    try {
      const f = await services.aiSetups.follow(chosen, profile, grade || null);
      follows.setData((list) => [f, ...(list ?? []).filter((x) => !(x.instrumentId === f.instrumentId && x.profile === f.profile))]);
      notify(`Following ${instrumentLabel(f.instrumentId, instruments.data)} (${f.profile}).`, 'success');
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (f: AIFollow) => {
    const key = `${f.instrumentId}:${f.profile}`;
    setBusy(key);
    try {
      await services.aiSetups.unfollow(f.instrumentId, f.profile);
      follows.setData((list) => (list ?? []).filter((x) => !(x.instrumentId === f.instrumentId && x.profile === f.profile)));
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel title="Follows" meta={<span>You are told when a setup on a followed instrument becomes armed</span>}>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <Field label="Instrument" className="w-full sm:w-48">
          {({ id }) => (
            <Select id={id} value={chosen} onChange={(e) => setInstrumentId(e.target.value)} disabled={!active.length}>
              {active.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.symbol}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Profile" className="w-full sm:w-36">
          {({ id }) => (
            <Select id={id} value={profile} onChange={(e) => setProfile(e.target.value)}>
              {AI_PROFILES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Minimum grade" className="w-full sm:w-40">
          {({ id }) => (
            <Select id={id} value={grade} onChange={(e) => setGrade(e.target.value as AIGrade | '')}>
              <option value="">Any grade</option>
              {AI_GRADES.map((g) => (
                <option key={g} value={g}>
                  {g} or better
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Button type="submit" variant="primary" icon={Plus} loading={busy === 'add'} disabled={!chosen}>
          Follow
        </Button>
      </form>
      {grade && (
        <p role="note" className="mt-2 text-xs text-warning">
          Version 1 of the AI engine assigns no grades, so with a minimum grade you will not be told about any setup until a model is validated.
        </p>
      )}
      <div className="mt-3">
        <FormError message={error} />
      </div>

      <div className="mt-4">
        {follows.status === 'loading' ? (
          <Loading label="Loading follows">
            <SkeletonRows rows={2} />
          </Loading>
        ) : follows.status === 'error' && !follows.data ? (
          <ErrorState error={follows.error} onRetry={follows.reload} compact />
        ) : !follows.data?.length ? (
          <EmptyState compact title="You follow no instrument yet" description="Follow an instrument to be told when the AI engine arms a setup on it." />
        ) : (
          <ul className="divide-y divide-line rounded-md border border-line" aria-label="Your follows">
            {follows.data.map((f) => (
              <li key={`${f.instrumentId}:${f.profile}`} className="flex flex-wrap items-center gap-3 px-3 py-2">
                <span className="text-sm font-medium text-fg">{instrumentLabel(f.instrumentId, instruments.data)}</span>
                <Badge>{f.profile}</Badge>
                <Badge tone={f.minGrade ? 'warning' : 'neutral'}>{f.minGrade ? `Grade ${f.minGrade} or better` : 'Any grade'}</Badge>
                <span className="text-xs text-fg-3">since {formatDate(f.createdAt, timeZone)}</span>
                <IconButton
                  className="ml-auto"
                  icon={Trash2}
                  size="sm"
                  label={`Unfollow ${instrumentLabel(f.instrumentId, instruments.data)} (${f.profile})`}
                  disabled={busy === `${f.instrumentId}:${f.profile}`}
                  onClick={() => void remove(f)}
                  tooltipSide="left"
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}
