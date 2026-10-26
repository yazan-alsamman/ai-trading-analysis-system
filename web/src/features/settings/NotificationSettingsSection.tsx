import { ExternalLink, Link2, RefreshCw, Save, Send, Unlink } from 'lucide-react';
import { useState } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input, Select, Switch } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import {
  CHANNEL_LABELS,
  EXTERNAL_CHANNELS,
  NOTIFICATION_EVENTS,
  type ChannelInfo,
  type ChannelStatus,
  type ExternalChannel,
  type NotificationPreferences,
  type TelegramLink,
  type TestDelivery,
} from '@/domain/notificationSettings';
import { TIME_ZONE_OPTIONS } from '@/domain/preferences';
import { useNow } from '@/hooks/useEnvironment';
import { useResource } from '@/hooks/useResource';
import { userMessage } from '@/services/errors';

type Draft = Omit<NotificationPreferences, 'updatedAt'>;
type TestChannel = 'in_app' | ExternalChannel;

const DEFAULT_CAP = 30;
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

const toDraft = (p: NotificationPreferences): Draft => ({
  matrix: p.matrix,
  minSignalStrength: p.minSignalStrength,
  onlyValidPlans: p.onlyValidPlans,
  quietHours: p.quietHours,
  language: p.language,
  maxPerHour: p.maxPerHour,
});

function browserZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/** IANA zones for quiet hours ('local' resolved to the browser's zone; the server needs a real zone id). */
function zoneOptions(current: string | undefined): string[] {
  const zones = TIME_ZONE_OPTIONS.map((t) => (t.id === 'local' ? browserZone() : t.id));
  if (current) zones.push(current);
  return [...new Set(zones)];
}

function channelSummary(id: TestChannel, info: ChannelInfo): string {
  if (!info.enabledOnServer) return 'Not configured on this server';
  if (id === 'in_app') return 'Always on: every notification is stored in your inbox';
  if (id === 'telegram') return info.linked ? `Linked${info.username ? ` as @${info.username}` : ''}` : 'Not linked yet';
  if (id === 'email') return info.address ? `Sent to ${info.address}` : 'Sent to your account email';
  return info.devices ? `${info.devices} registered device${info.devices === 1 ? '' : 's'}` : 'No device registered (use the mobile app)';
}

function TelegramLinker({ info, onChanged }: { info: ChannelInfo; onChanged: () => void }) {
  const services = useServices();
  const { notify } = useToast();
  const now = useNow(1000);
  const [link, setLink] = useState<(TelegramLink & { issuedAt: number }) | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const left = link ? Math.max(0, Math.round((link.issuedAt + link.expiresInSeconds * 1000 - now) / 1000)) : 0;

  const start = async () => {
    setBusy(true);
    try {
      setLink({ ...(await services.notificationSettings.linkTelegram()), issuedAt: Date.now() });
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    try {
      await services.notificationSettings.unlinkTelegram();
      notify('Telegram unlinked.', 'info');
      setConfirmUnlink(false);
      onChanged();
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  if (!info.enabledOnServer) return null;
  if (info.linked)
    return (
      <>
        <Button size="sm" variant="ghost" icon={Unlink} onClick={() => setConfirmUnlink(true)}>
          Unlink
        </Button>
        <ConfirmDialog
          open={confirmUnlink}
          title="Unlink Telegram?"
          description="Notifications will no longer be sent to your Telegram chat. You can link it again at any time."
          confirmLabel="Unlink Telegram"
          busy={busy}
          onConfirm={unlink}
          onCancel={() => setConfirmUnlink(false)}
        />
      </>
    );
  if (!link || left === 0)
    return (
      <Button size="sm" icon={Link2} loading={busy} onClick={start}>
        {link ? 'Get a new code' : 'Link Telegram'}
      </Button>
    );
  return (
    <div className="flex w-full flex-col gap-2 rounded-md border border-line bg-inset p-3 text-sm">
      <p className="text-fg-2">
        Open the bot{link.botUsername ? ` @${link.botUsername}` : ''} and send it this code, or use the link. The code expires in{' '}
        <span className="num text-fg">
          {Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
        </span>
        .
      </p>
      <p className="num text-lg font-semibold tracking-widest text-fg" aria-label={`Link code ${link.code}`}>
        {link.code}
      </p>
      <div className="flex flex-wrap gap-2">
        {link.deepLink && /^https:\/\//i.test(link.deepLink) && (
          <a
            href={link.deepLink}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-3 text-sm text-fg hover:bg-hover"
          >
            Open Telegram <ExternalLink aria-hidden className="size-3.5" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        )}
        <Button
          size="sm"
          icon={RefreshCw}
          onClick={() => {
            setLink(null);
            onChanged();
          }}
        >
          I’ve linked it — refresh
        </Button>
      </div>
    </div>
  );
}

function ChannelsPanel({ channels, onChanged }: { channels: ChannelStatus; onChanged: () => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [testing, setTesting] = useState<TestChannel | null>(null);
  const [results, setResults] = useState<Partial<Record<TestChannel, TestDelivery[]>>>({});

  const sendTest = async (channel: TestChannel) => {
    setTesting(channel);
    try {
      const deliveries = await services.notificationSettings.sendTest(channel);
      setResults((r) => ({ ...r, [channel]: deliveries }));
      if (deliveries.length === 0) notify(`No ${CHANNEL_LABELS[channel]} target to send to.`, 'warning');
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setTesting(null);
    }
  };

  const ids: TestChannel[] = ['in_app', ...EXTERNAL_CHANNELS];
  return (
    <ul className="divide-y divide-line rounded-md border border-line">
      {ids.map((id) => {
        const info = channels[id];
        const delivered = results[id];
        return (
          <li key={id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-sm font-medium text-fg">
                {CHANNEL_LABELS[id]}
                {!info.enabledOnServer ? (
                  <Badge tone="warning">Not available</Badge>
                ) : id === 'telegram' && !info.linked ? (
                  <Badge>Not linked</Badge>
                ) : (
                  <Badge tone="up">Ready</Badge>
                )}
              </p>
              <p className="text-xs text-fg-3">{channelSummary(id, info)}</p>
              {delivered && delivered.length > 0 && (
                <ul className="mt-1 text-xs text-fg-2" aria-live="polite">
                  {delivered.map((d, i) => (
                    <li key={`${d.target}-${i}`}>
                      Test to {d.target}: <span className={d.status === 'failed' ? 'text-danger' : 'text-fg'}>{d.status}</span>
                      {d.lastError && <span className="text-danger"> — {d.lastError}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {id === 'telegram' && <TelegramLinker info={info} onChanged={onChanged} />}
            {info.enabledOnServer && (id !== 'telegram' || info.linked) && (
              <Button size="sm" variant="ghost" icon={Send} loading={testing === id} disabled={testing !== null && testing !== id} onClick={() => sendTest(id)}>
                Send test
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function PreferencesForm({ initial, channels, onSaved }: { initial: NotificationPreferences; channels: ChannelStatus; onSaved: (p: NotificationPreferences) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [draft, setDraft] = useState<Draft>(() => toDraft(initial));
  const [base, setBase] = useState(() => JSON.stringify(toDraft(initial)));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const dirty = JSON.stringify(draft) !== base;
  const quiet = draft.quietHours;
  const quietInvalid = quiet !== null && (!HHMM.test(quiet.start) || !HHMM.test(quiet.end));

  const toggle = (event: string, channel: ExternalChannel, on: boolean) =>
    setDraft((d) => ({ ...d, matrix: { ...d.matrix, [event]: { ...d.matrix[event], [channel]: on } } }));

  const save = async () => {
    if (quietInvalid) return setError('Quiet hours need a start and end time as HH:MM (24-hour).');
    setError(null);
    setSaving(true);
    try {
      const saved = await services.notificationSettings.savePreferences(draft);
      const next = toDraft(saved);
      setDraft(next);
      setBase(JSON.stringify(next));
      onSaved(saved);
      notify('Notification preferences saved on the server.', 'success');
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      noValidate
      aria-label="Notification preferences"
      className="flex flex-col gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div>
        <h3 className="mb-1 text-sm font-medium text-fg">What is sent where</h3>
        <p className="mb-2 text-xs text-fg-3">The in-app inbox always receives everything. These switches control the external channels only.</p>
        <TableRegion label="Notification channels per event" className="rounded-md border border-line">
          <thead>
            <tr>
              <Th>Event</Th>
              {EXTERNAL_CHANNELS.map((c) => (
                <Th key={c}>{CHANNEL_LABELS[c]}</Th>
              ))}
            </tr>
          </thead>
          <tbody>
            {NOTIFICATION_EVENTS.map((ev) => (
              <tr key={ev.type} className="hover:bg-hover">
                <Td className="whitespace-normal">{ev.label}</Td>
                {EXTERNAL_CHANNELS.map((c) => {
                  const available = channels[c].enabledOnServer;
                  return (
                    <Td key={c}>
                      <input
                        type="checkbox"
                        className="size-4 cursor-pointer accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
                        aria-label={`${ev.label} by ${CHANNEL_LABELS[c]}${available ? '' : ' (not configured on this server)'}`}
                        checked={draft.matrix[ev.type]?.[c] ?? false}
                        disabled={!available}
                        onChange={(e) => toggle(ev.type, c, e.target.checked)}
                      />
                    </Td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </TableRegion>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Minimum signal strength" hint="0 sends every signal; 1 sends only the strongest. Applies to external channels.">
          {({ id, describedBy }) => (
            <Input
              id={id}
              aria-describedby={describedBy}
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={draft.minSignalStrength}
              onChange={(e) => setDraft((d) => ({ ...d, minSignalStrength: Math.min(1, Math.max(0, Number(e.target.value) || 0)) }))}
            />
          )}
        </Field>
        <Field label="Language of notification texts">
          {({ id, describedBy }) => (
            <Select id={id} aria-describedby={describedBy} value={draft.language} onChange={(e) => setDraft((d) => ({ ...d, language: e.target.value === 'en' ? 'en' : 'ar' }))}>
              <option value="ar">Arabic</option>
              <option value="en">English</option>
            </Select>
          )}
        </Field>
      </div>

      <Checkbox
        label="Only signals with a valid trade plan"
        description="Skip signals whose plan the risk engine marked invalid (for example, a stop that does not fit your limits)."
        checked={draft.onlyValidPlans}
        onChange={(e) => setDraft((d) => ({ ...d, onlyValidPlans: e.target.checked }))}
      />

      <div className="flex flex-col gap-3">
        <Switch
          checked={quiet !== null}
          onChange={(on) => setDraft((d) => ({ ...d, quietHours: on ? { start: '23:00', end: '07:00', tz: browserZone() } : null }))}
          label="Quiet hours"
          description="External deliveries are held during these hours and sent as one digest afterwards. Security lockout alerts are never held."
        />
        {quiet && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="From" error={HHMM.test(quiet.start) ? undefined : 'Use HH:MM'}>
              {({ id, describedBy, invalid }) => (
                <Input id={id} type="time" aria-describedby={describedBy} invalid={invalid} value={quiet.start} onChange={(e) => setDraft((d) => ({ ...d, quietHours: { ...quiet, start: e.target.value } }))} />
              )}
            </Field>
            <Field label="Until" error={HHMM.test(quiet.end) ? undefined : 'Use HH:MM'}>
              {({ id, describedBy, invalid }) => (
                <Input id={id} type="time" aria-describedby={describedBy} invalid={invalid} value={quiet.end} onChange={(e) => setDraft((d) => ({ ...d, quietHours: { ...quiet, end: e.target.value } }))} />
              )}
            </Field>
            <Field label="Time zone">
              {({ id, describedBy }) => (
                <Select id={id} aria-describedby={describedBy} value={quiet.tz} onChange={(e) => setDraft((d) => ({ ...d, quietHours: { ...quiet, tz: e.target.value } }))}>
                  {zoneOptions(quiet.tz).map((z) => (
                    <option key={z} value={z}>
                      {z}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        )}
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-fg">Hourly limit per channel</legend>
        <p className="mb-2 text-xs text-fg-3">Beyond the limit, deliveries wait for the next hour and are sent as one digest (1–1000).</p>
        <div className="grid gap-4 sm:grid-cols-3">
          {EXTERNAL_CHANNELS.map((c) => (
            <Field key={c} label={CHANNEL_LABELS[c]}>
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  type="number"
                  min={1}
                  max={1000}
                  step={1}
                  value={draft.maxPerHour[c] ?? DEFAULT_CAP}
                  onChange={(e) => {
                    const v = Math.round(Number(e.target.value));
                    setDraft((d) => ({ ...d, maxPerHour: { ...d.maxPerHour, [c]: Math.min(1000, Math.max(1, Number.isFinite(v) ? v : DEFAULT_CAP)) } }));
                  }}
                />
              )}
            </Field>
          ))}
        </div>
      </fieldset>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" icon={Save} loading={saving} disabled={!dirty}>
          Save preferences
        </Button>
        {dirty && (
          <Button
            onClick={() => {
              setDraft(JSON.parse(base) as Draft);
              setError(null);
            }}
            disabled={saving}
          >
            Discard changes
          </Button>
        )}
      </div>
    </form>
  );
}

/**
 * Backend mode: the server's delivery settings (docs/notifications.md) —
 * channel status, Telegram linking, test deliveries and the per-event matrix.
 */
export function NotificationSettingsSection() {
  const services = useServices();
  const prefs = useResource('notification-preferences', (signal) => services.notificationSettings.getPreferences({ signal }));
  const channels = useResource('notification-channels', (signal) => services.notificationSettings.channels({ signal }));

  return (
    <div id="notifications" className="scroll-mt-4">
      <div id="channels" className="scroll-mt-4">
        <Panel title="Notifications" meta={<span>Saved on the server, shared with the mobile app</span>}>
          {prefs.status === 'loading' || channels.status === 'loading' ? (
            <Loading label="Loading notification settings">
              <SkeletonRows rows={5} />
            </Loading>
          ) : !channels.data ? (
            <ErrorState error={channels.error} onRetry={channels.reload} compact />
          ) : (
            <div className="flex flex-col gap-6">
              <div>
                <h3 className="mb-2 text-sm font-medium text-fg">Delivery channels</h3>
                <ChannelsPanel channels={channels.data} onChanged={channels.reload} />
              </div>
              {!prefs.data ? (
                <ErrorState error={prefs.error} onRetry={prefs.reload} compact />
              ) : (
                <PreferencesForm key={prefs.data.updatedAt} initial={prefs.data} channels={channels.data} onSaved={(p) => prefs.setData(() => p)} />
              )}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
