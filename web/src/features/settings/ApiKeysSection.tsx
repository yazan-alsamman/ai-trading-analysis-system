import { BarChart3, Copy, KeyRound, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { ApiKey, ApiKeyScope } from '@/domain/apiKeys';
import { useResource } from '@/hooks/useResource';
import { formatDate, formatNumber, formatRelative, MISSING } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';

/** Positive whole number, or null when empty. `undefined` = invalid. */
function optionalInt(text: string, min: number, max: number): number | null | undefined {
  if (text.trim() === '') return null;
  const n = Number(text);
  return Number.isInteger(n) && n >= min && n <= max ? n : undefined;
}

function KeyDialog({
  open,
  editing,
  scopes,
  onClose,
  onCreated,
  onUpdated,
}: {
  open: boolean;
  editing: ApiKey | null;
  scopes: ApiKeyScope[];
  onClose: () => void;
  onCreated: (key: ApiKey, secret: string) => void;
  onUpdated: (key: ApiKey) => void;
}) {
  const services = useServices();
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [expires, setExpires] = useState('');
  const [rate, setRate] = useState('');
  const [errors, setErrors] = useState<{ name?: string; scopes?: string; expires?: string; rate?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastOpen, setLastOpen] = useState(false);
  if (open !== lastOpen) {
    // Reset the form each time the dialog opens.
    setLastOpen(open);
    if (open) {
      setName(editing?.name ?? '');
      setSelected(editing?.scopes ?? []);
      setExpires('');
      setRate(editing?.rateLimitPerMinute ? String(editing.rateLimitPerMinute) : '');
      setErrors({});
      setFormError(null);
    }
  }

  const submit = async () => {
    const next: typeof errors = {};
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 100) next.name = 'Give the key a name (1–100 characters).';
    if (selected.length === 0) next.scopes = 'Choose at least one scope.';
    const expiresInDays = optionalInt(expires, 1, 3650);
    if (expiresInDays === undefined) next.expires = 'Enter whole days between 1 and 3650, or leave empty.';
    const rateLimit = optionalInt(rate, 1, 1_000_000);
    if (rateLimit === undefined) next.rate = 'Enter a whole number of requests per minute, or leave empty.';
    setErrors(next);
    if (Object.keys(next).length > 0 || expiresInDays === undefined || rateLimit === undefined) return;
    setBusy(true);
    setFormError(null);
    try {
      if (editing) onUpdated(await services.apiKeys.update(editing.id, { name: trimmed, scopes: selected, rateLimitPerMinute: rateLimit }));
      else {
        const created = await services.apiKeys.create({ name: trimmed, scopes: selected, expiresInDays, rateLimitPerMinute: rateLimit });
        onCreated(created.apiKey, created.secret);
      }
    } catch (e) {
      setFormError(isApiError(e) && e.kind === 'validation' && e.fieldErrors.rate_limit_per_minute?.[0] ? e.fieldErrors.rate_limit_per_minute[0] : userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing ? `Edit “${editing.name}”` : 'New API key'}
      description="API keys give read-only programmatic access. They cannot trade, change your account or post."
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="api-key-form" loading={busy}>
            {editing ? 'Save' : 'Create key'}
          </Button>
        </>
      }
    >
      <form
        id="api-key-form"
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <FormError message={formError} />
        <Field label="Name" error={errors.name} hint="So you can recognise it later, e.g. “Research notebook”.">
          {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">Scopes</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {scopes.map((s) => (
              <Checkbox
                key={s.scope}
                label={<span className="num">{s.scope}</span>}
                description={s.grantable ? s.description : `${s.description} (administrators only)`}
                checked={selected.includes(s.scope)}
                disabled={!s.grantable && !selected.includes(s.scope)}
                onChange={(e) => setSelected((list) => (e.target.checked ? [...list, s.scope] : list.filter((x) => x !== s.scope)))}
              />
            ))}
          </div>
          {errors.scopes && <p className="mt-1.5 text-xs text-danger">{errors.scopes}</p>}
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          {!editing && (
            <Field label="Expires after (days)" optional error={errors.expires} hint="Empty = never expires.">
              {({ id, describedBy, invalid }) => (
                <Input id={id} aria-describedby={describedBy} invalid={invalid} type="number" min={1} max={3650} value={expires} onChange={(e) => setExpires(e.target.value)} />
              )}
            </Field>
          )}
          <Field label="Rate limit (requests/minute)" optional error={errors.rate} hint="Empty = your account tier’s limit.">
            {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} type="number" min={1} value={rate} onChange={(e) => setRate(e.target.value)} />}
          </Field>
        </div>
      </form>
    </Dialog>
  );
}

function SecretDialog({ secret, onClose }: { secret: string | null; onClose: () => void }) {
  const { notify } = useToast();
  const copy = () =>
    navigator.clipboard
      .writeText(secret ?? '')
      .then(() => notify('API key copied.', 'success'))
      .catch(() => notify('Could not copy. Select the key and copy it manually.', 'warning'));
  return (
    <Dialog
      open={secret !== null}
      onClose={onClose}
      title="Your new API key"
      size="sm"
      footer={
        <Button variant="primary" onClick={onClose}>
          I’ve stored it
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <p role="alert" className="rounded-md border border-warning/40 bg-warning-soft px-3 py-2 text-sm text-fg">
          Copy this key now. It is shown only once: the server keeps a hash, so it cannot be displayed again.
        </p>
        <div className="flex items-center gap-2">
          <Input readOnly value={secret ?? ''} aria-label="API key" className="num" onFocus={(e) => e.target.select()} />
          <IconButton icon={Copy} label="Copy API key" onClick={copy} tooltipSide="left" />
        </div>
        <p className="text-xs text-fg-3">
          Send it as <span className="num">X-API-Key</span> header. Keep it secret; revoke it here if it leaks.
        </p>
      </div>
    </Dialog>
  );
}

function UsageDialog({ apiKey, onClose }: { apiKey: ApiKey | null; onClose: () => void }) {
  const services = useServices();
  const usage = useResource(`api-key-usage:${apiKey?.id ?? 'none'}`, (signal) => (apiKey ? services.apiKeys.usage(apiKey.id, { signal }) : Promise.resolve([])));
  return (
    <Dialog open={apiKey !== null} onClose={onClose} title={`Usage of “${apiKey?.name ?? ''}”`} size="sm">
      {usage.status === 'loading' ? (
        <Loading label="Loading usage">
          <SkeletonRows rows={4} />
        </Loading>
      ) : usage.status === 'error' ? (
        <ErrorState error={usage.error} onRetry={usage.reload} compact />
      ) : (usage.data?.length ?? 0) === 0 ? (
        <EmptyState compact title="No requests yet" description="Requests made with this key are counted per day." />
      ) : (
        <TableRegion label="Requests per day">
          <thead>
            <tr>
              <Th>Day</Th>
              <Th numeric>Requests</Th>
              <Th numeric>Rejected</Th>
            </tr>
          </thead>
          <tbody>
            {(usage.data ?? []).map((d) => (
              <tr key={d.date}>
                <Td className="num">{d.date}</Td>
                <Td numeric>{formatNumber(d.requests)}</Td>
                <Td numeric className={d.rejected ? 'text-danger' : 'text-fg-2'}>
                  {formatNumber(d.rejected)}
                </Td>
              </tr>
            ))}
          </tbody>
        </TableRegion>
      )}
    </Dialog>
  );
}

/** Backend mode: personal API keys (docs/api-keys.md). */
export function ApiKeysSection() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const keys = useResource('api-keys', (signal) => services.apiKeys.list({ signal }));
  const scopes = useResource('api-key-scopes', (signal) => services.apiKeys.scopes({ signal }));
  const [dialog, setDialog] = useState<{ editing: ApiKey | null } | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);
  const [usageOf, setUsageOf] = useState<ApiKey | null>(null);
  const [busy, setBusy] = useState(false);

  const revoke = async () => {
    if (!revoking) return;
    setBusy(true);
    try {
      await services.apiKeys.revoke(revoking.id);
      keys.reload();
      notify(`Key “${revoking.name}” revoked.`, 'info');
      setRevoking(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div id="api-keys" className="scroll-mt-4">
      <Panel
        title="API keys"
        meta={<span>Read-only access for your own scripts and tools</span>}
        actions={
          <Button size="sm" icon={Plus} disabled={!scopes.data} onClick={() => setDialog({ editing: null })}>
            New key
          </Button>
        }
        flush
      >
        {keys.status === 'loading' ? (
          <Loading label="Loading API keys">
            <SkeletonRows rows={2} className="p-4" />
          </Loading>
        ) : keys.status === 'error' && !keys.data ? (
          <ErrorState error={keys.error} onRetry={keys.reload} compact />
        ) : (keys.data?.length ?? 0) === 0 ? (
          <EmptyState compact icon={KeyRound} title="No API keys" description="Create a key to read market data, indicators, signals or backtests from your own code." />
        ) : (
          <TableRegion label="API keys">
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Key</Th>
                <Th>Scopes</Th>
                <Th numeric>Limit/min</Th>
                <Th>Expires</Th>
                <Th>Last used</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {(keys.data ?? []).map((k) => (
                <tr key={k.id} className="hover:bg-hover">
                  <Td className="font-medium">
                    <span className="flex items-center gap-2">
                      {k.name}
                      {k.revoked && <Badge tone="danger">Revoked</Badge>}
                    </span>
                  </Td>
                  <Td className="num text-fg-2">{k.prefix}…</Td>
                  <Td className="max-w-64 whitespace-normal text-xs text-fg-2">{k.scopes.join(', ')}</Td>
                  <Td numeric className="text-fg-2">
                    {k.rateLimitPerMinute ?? 'Tier'}
                  </Td>
                  <Td className="num text-fg-2">{k.expiresAt ? formatDate(k.expiresAt, timeZone) : 'Never'}</Td>
                  <Td className="text-fg-2">{k.lastUsedAt ? formatRelative(k.lastUsedAt) : MISSING}</Td>
                  <Td>
                    <div className="flex justify-end gap-0.5">
                      <IconButton icon={BarChart3} label={`Usage of ${k.name}`} size="sm" onClick={() => setUsageOf(k)} tooltipSide="left" />
                      {!k.revoked && (
                        <>
                          <IconButton icon={Pencil} label={`Edit ${k.name}`} size="sm" disabled={!scopes.data} onClick={() => setDialog({ editing: k })} tooltipSide="left" />
                          <IconButton icon={Trash2} label={`Revoke ${k.name}`} size="sm" onClick={() => setRevoking(k)} tooltipSide="left" />
                        </>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
        )}
        {scopes.status === 'error' && <p className="border-t border-line px-4 py-2.5 text-xs text-danger">Could not load the available scopes: {userMessage(scopes.error)}</p>}
      </Panel>

      <KeyDialog
        open={dialog !== null}
        editing={dialog?.editing ?? null}
        scopes={scopes.data ?? []}
        onClose={() => setDialog(null)}
        onCreated={(key, s) => {
          keys.setData((list) => [key, ...(list ?? [])]);
          setDialog(null);
          setSecret(s);
        }}
        onUpdated={(key) => {
          keys.setData((list) => (list ?? []).map((k) => (k.id === key.id ? key : k)));
          setDialog(null);
          notify('API key updated.', 'success');
        }}
      />
      <SecretDialog secret={secret} onClose={() => setSecret(null)} />
      <UsageDialog apiKey={usageOf} onClose={() => setUsageOf(null)} />
      <ConfirmDialog
        open={revoking !== null}
        title="Revoke API key?"
        description={`Programs using “${revoking?.name ?? ''}” will stop working immediately. This cannot be undone.`}
        confirmLabel="Revoke key"
        busy={busy}
        onConfirm={revoke}
        onCancel={() => setRevoking(null)}
      />
    </div>
  );
}
