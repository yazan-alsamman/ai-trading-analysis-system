import { RefreshCw, Send, Upload } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input, Select, Switch, Textarea } from '@/components/ui/Form';
import { JsonView } from '@/components/ui/JsonView';
import { Panel } from '@/components/ui/Panel';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { IngestResult, JsonObject, NewsSource } from '@/domain/admin';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber } from '@/lib/format';
import { userMessage } from '@/services/errors';
import { isHttpUrl, localUtcToIso, parseTags, SOURCE_KEY } from './contentForms';

type Label = 'positive' | 'neutral' | 'negative';
type Severity = 'info' | 'success' | 'warning' | 'critical';
const ROLES = ['trader', 'analyst', 'expert', 'admin'] as const;

function SourceRow({ source, onSaved }: { source: NewsSource; onSaved: (s: NewsSource) => void }) {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const [minutes, setMinutes] = useState(String(source.fetchIntervalMinutes));
  const [busy, setBusy] = useState(false);
  const save = async (patch: { isActive?: boolean; fetchIntervalMinutes?: number }) => {
    setBusy(true);
    try {
      onSaved(await services.admin.updateNewsSource(source.id, patch));
      notify(`Source “${source.name}” updated.`, 'success');
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };
  const n = Number(minutes);
  const intervalValid = Number.isInteger(n) && n >= 5 && n <= 1440;
  return (
    <tr>
      <Td>
        <span className="font-medium">{source.name}</span>
        <span className="block text-xs text-fg-3">{source.key}</span>
      </Td>
      <Td>
        <Badge>{source.kind}</Badge>
      </Td>
      <Td className="max-w-56 truncate text-fg-2" title={source.url ?? undefined}>
        {source.url ?? '—'}
      </Td>
      <Td>{source.language}</Td>
      <Td>
        <Switch checked={source.isActive} disabled={busy} onChange={(v) => void save({ isActive: v })} label={<span className="sr-only">Active: {source.name}</span>} />
      </Td>
      <Td>
        {source.kind === 'rss' ? (
          <form
            className="flex items-center gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (intervalValid) void save({ fetchIntervalMinutes: n });
            }}
          >
            <Input aria-label={`Fetch interval of ${source.name} (minutes)`} className="h-8 w-20" inputMode="numeric" value={minutes} invalid={!intervalValid} onChange={(e) => setMinutes(e.target.value)} />
            <Button size="sm" type="submit" disabled={busy || !intervalValid || n === source.fetchIntervalMinutes}>
              Save
            </Button>
          </form>
        ) : (
          <span className="text-fg-3">—</span>
        )}
      </Td>
      <Td className="text-fg-2">{source.lastFetchedAt ? formatDateTime(source.lastFetchedAt, timeZone) : '—'}</Td>
      <Td className="max-w-56 truncate text-danger" title={source.lastError ?? undefined}>
        {source.lastError ?? <span className="text-fg-3">—</span>}
      </Td>
      <Td numeric>{source.articles === null ? '—' : formatNumber(source.articles)}</Td>
    </tr>
  );
}

function SourcesPanel() {
  const services = useServices();
  const res = useResource('admin:news-sources', (signal) => services.admin.newsSources({ signal }));
  return (
    <Panel title="News sources" meta={<span>RSS feeds are fetched every 5–1440 minutes</span>} flush>
      {res.status === 'loading' ? (
        <Loading label="Loading news sources">
          <SkeletonRows rows={3} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact title="No news sources" />
      ) : (
        <TableRegion label="News sources">
          <thead>
            <tr>
              <Th>Source</Th>
              <Th>Kind</Th>
              <Th>URL</Th>
              <Th>Language</Th>
              <Th>Active</Th>
              <Th>Interval (min)</Th>
              <Th>Last fetched</Th>
              <Th>Last error</Th>
              <Th numeric>Articles</Th>
            </tr>
          </thead>
          <tbody>
            {res.data.map((s) => (
              <SourceRow key={`${s.id}:${s.fetchIntervalMinutes}:${s.isActive}`} source={s} onSaved={(u) => res.setData((list) => (list ?? []).map((x) => (x.id === u.id ? u : x)))} />
            ))}
          </tbody>
        </TableRegion>
      )}
    </Panel>
  );
}

function IngestSummary({ result }: { result: IngestResult }) {
  return (
    <div role="status" className="mt-3 rounded-md border border-line p-3 text-sm">
      <p>
        Inserted <strong>{result.inserted}</strong>, updated <strong>{result.updated}</strong>, skipped <strong>{result.skipped}</strong>.
      </p>
      {result.errors.map((e) => (
        <p key={`e${e.index}`} className="text-danger">
          Error: {e.error}
        </p>
      ))}
      {result.warnings.map((w) => (
        <p key={`w${w.index}`} className="text-warning">
          Warning: {w.error}
        </p>
      ))}
    </div>
  );
}

function PublishPanel() {
  const services = useServices();
  const [f, setF] = useState({ sourceKey: 'manual', externalId: '', url: '', title: '', summary: '', publishedAt: '', language: 'en', tags: '', withSentiment: false, label: 'neutral' as Label, score: '0', model: 'manual' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const set = (k: keyof typeof f) => (v: string | boolean) => setF((cur) => ({ ...cur, [k]: v }));

  const submit = async () => {
    setError(null);
    setResult(null);
    const { tags, error: tagError } = parseTags(f.tags);
    const published = localUtcToIso(f.publishedAt);
    const score = Number(f.score);
    if (!SOURCE_KEY.test(f.sourceKey)) return setError('Source key: lower-case letters, digits, “_”, “.”, “-”, 2–64 characters.');
    if (!f.externalId.trim() || f.externalId.length > 255) return setError('External id: 1–255 characters.');
    if (!isHttpUrl(f.url)) return setError('URL: an http(s) address.');
    if (!f.title.trim() || f.title.length > 500) return setError('Title: 1–500 characters.');
    if (!published) return setError('Published at: a date and time (UTC).');
    if (tagError) return setError(tagError);
    if (f.withSentiment && (!Number.isFinite(score) || score < -1 || score > 1)) return setError('Sentiment score: between −1 and 1.');
    if (f.withSentiment && !f.model.trim()) return setError('Sentiment model: required.');
    setBusy(true);
    try {
      setResult(
        await services.admin.publishArticle({
          sourceKey: f.sourceKey,
          externalId: f.externalId.trim(),
          url: f.url.trim(),
          title: f.title.trim(),
          summary: f.summary.trim() || null,
          publishedAt: published,
          language: f.language.trim() || null,
          instruments: tags,
          sentiment: f.withSentiment ? { label: f.label, score, model: f.model.trim() } : null,
        }),
      );
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Publish an article" meta={<span>Through the ingestion API, as yourself (admin). Re-sending the same source and id updates it.</span>}>
      <form
        className="grid gap-3 sm:grid-cols-2"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Field label="Source key" hint="Created as an API source if new">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={f.sourceKey} onChange={(e) => set('sourceKey')(e.target.value)} />}
        </Field>
        <Field label="External id" hint="The provider's id of this article">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={f.externalId} onChange={(e) => set('externalId')(e.target.value)} />}
        </Field>
        <Field label="URL" className="sm:col-span-2">
          {({ id }) => <Input id={id} type="url" value={f.url} onChange={(e) => set('url')(e.target.value)} />}
        </Field>
        <Field label="Title" className="sm:col-span-2">
          {({ id }) => <Input id={id} value={f.title} maxLength={500} onChange={(e) => set('title')(e.target.value)} />}
        </Field>
        <Field label="Summary" optional hint="HTML is stripped by the server" className="sm:col-span-2">
          {({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} rows={3} value={f.summary} onChange={(e) => set('summary')(e.target.value)} />}
        </Field>
        <Field label="Published at (UTC)">
          {({ id }) => <Input id={id} type="datetime-local" value={f.publishedAt} onChange={(e) => set('publishedAt')(e.target.value)} />}
        </Field>
        <Field label="Language" optional>
          {({ id }) => <Input id={id} value={f.language} maxLength={8} onChange={(e) => set('language')(e.target.value)} />}
        </Field>
        <Field label="Instrument tags" optional hint="e.g. XAU/USD:1, EUR:0.5 (relevance 0–1, default 1)" className="sm:col-span-2">
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={f.tags} onChange={(e) => set('tags')(e.target.value)} />}
        </Field>
        <div className="sm:col-span-2">
          <Checkbox label="Attach a sentiment" checked={f.withSentiment} onChange={(e) => set('withSentiment')(e.target.checked)} />
        </div>
        {f.withSentiment && (
          <div className="grid gap-3 sm:col-span-2 sm:grid-cols-3">
            <Field label="Label">
              {({ id }) => (
                <Select id={id} value={f.label} onChange={(e) => set('label')(e.target.value)}>
                  <option value="positive">Positive</option>
                  <option value="neutral">Neutral</option>
                  <option value="negative">Negative</option>
                </Select>
              )}
            </Field>
            <Field label="Score (−1 to 1)">
              {({ id }) => <Input id={id} inputMode="decimal" value={f.score} onChange={(e) => set('score')(e.target.value)} />}
            </Field>
            <Field label="Model">
              {({ id }) => <Input id={id} maxLength={64} value={f.model} onChange={(e) => set('model')(e.target.value)} />}
            </Field>
          </div>
        )}
        <div className="flex flex-col gap-3 sm:col-span-2">
          <FormError message={error} />
          <Button type="submit" variant="primary" icon={Send} loading={busy} className="self-start">
            Publish
          </Button>
        </div>
      </form>
      {result && <IngestSummary result={result} />}
    </Panel>
  );
}

function SentimentPanel() {
  const services = useServices();
  const { notify } = useToast();
  const [articleId, setArticleId] = useState('');
  const [label, setLabel] = useState<Label>('neutral');
  const [score, setScore] = useState('0');
  const [model, setModel] = useState('manual');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setError(null);
    const s = Number(score);
    if (!/^[0-9a-f-]{36}$/i.test(articleId.trim())) return setError('Article id: the article UUID (see the article page link).');
    if (!Number.isFinite(s) || s < -1 || s > 1) return setError('Score: between −1 and 1.');
    if (!model.trim()) return setError('Model: required.');
    setBusy(true);
    try {
      const r = await services.admin.setSentiment(articleId.trim(), { label, score: s, model: model.trim() });
      if (r.errors.length) setError(r.errors.join(' '));
      else notify(`Sentiment set (${r.updated} updated).`, 'success');
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel title="Set an article's sentiment" meta={<span>The last write wins</span>}>
      <form
        className="grid gap-3 sm:grid-cols-4"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Field label="Article id" className="sm:col-span-4">
          {({ id }) => <Input id={id} value={articleId} onChange={(e) => setArticleId(e.target.value)} placeholder="00000000-0000-0000-0000-000000000000" />}
        </Field>
        <Field label="Label">
          {({ id }) => (
            <Select id={id} value={label} onChange={(e) => setLabel(e.target.value as Label)}>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </Select>
          )}
        </Field>
        <Field label="Score (−1 to 1)">
          {({ id }) => <Input id={id} inputMode="decimal" value={score} onChange={(e) => setScore(e.target.value)} />}
        </Field>
        <Field label="Model">
          {({ id }) => <Input id={id} maxLength={64} value={model} onChange={(e) => setModel(e.target.value)} />}
        </Field>
        <div className="flex items-end">
          <Button type="submit" loading={busy}>
            Set sentiment
          </Button>
        </div>
        <div className="sm:col-span-4">
          <FormError message={error} />
        </div>
      </form>
    </Panel>
  );
}

function CalendarPanel() {
  const services = useServices();
  const [refreshing, setRefreshing] = useState(false);
  const [refresh, setRefresh] = useState<JsonObject | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<'forexfactory_kaggle' | 'manual'>('forexfactory_kaggle');
  const [tz, setTz] = useState('');
  const [from, setFrom] = useState('');
  const [dryRun, setDryRun] = useState(true);
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState<JsonObject | null>(null);
  const [error, setError] = useState<string | null>(null);

  const doRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      setRefresh(await services.admin.refreshCalendar());
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setRefreshing(false);
    }
  };
  const doImport = async () => {
    if (!file) return setError('Choose a CSV file.');
    setImporting(true);
    setError(null);
    setImported(null);
    try {
      setImported(await services.admin.importCalendar(file, { dryRun, source, ...(tz.trim() ? { tz: tz.trim() } : {}), ...(from ? { from } : {}) }));
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setImporting(false);
    }
  };
  const status = typeof refresh?.status === 'string' ? refresh.status : null;

  return (
    <Panel title="Economic calendar">
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-3">
          <Button icon={RefreshCw} loading={refreshing} onClick={() => void doRefresh()}>
            Refresh now
          </Button>
          <p className="text-xs text-fg-3">Fetches this week from ForexFactory once (not during a back-off after 429/403).</p>
          {status && <Badge tone={status === 'ok' || status === 'not_modified' ? 'up' : status === 'error' || status === 'blocked' ? 'danger' : 'warning'}>{status}</Badge>}
        </div>
        {refresh && <JsonView value={refresh} />}

        <form
          className="grid gap-3 border-t border-line pt-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            void doImport();
          }}
        >
          <p className="text-sm font-medium text-fg sm:col-span-2">Import history from CSV</p>
          <Field label="CSV file" className="sm:col-span-2">
            {({ id }) => <Input id={id} type="file" accept=".csv,text/csv" className="h-auto py-1.5" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
          </Field>
          <Field label="Source">
            {({ id }) => (
              <Select id={id} value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
                <option value="forexfactory_kaggle">ForexFactory (Kaggle export)</option>
                <option value="manual">Manual</option>
              </Select>
            )}
          </Field>
          <Field label="Time zone of the file" optional hint="IANA name; server default when empty">
            {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={tz} placeholder="America/New_York" onChange={(e) => setTz(e.target.value)} />}
          </Field>
          <Field label="Only rows from" optional>
            {({ id }) => <Input id={id} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}
          </Field>
          <div className="flex items-end">
            <Checkbox label="Dry run" description="Parse and report only; nothing is stored" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          </div>
          <Button type="submit" icon={Upload} loading={importing} disabled={!file} className="self-start">
            {dryRun ? 'Check file' : 'Import'}
          </Button>
        </form>
        <FormError message={error} />
        {imported && (
          <div role="status">
            <p className="mb-2 text-sm font-medium text-fg">{imported.dry_run ? 'Dry run: nothing was stored' : 'Imported'}</p>
            <JsonView value={imported} />
          </div>
        )}
      </div>
    </Panel>
  );
}

function BroadcastPanel() {
  const services = useServices();
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [severity, setSeverity] = useState<Severity>('info');
  const [roles, setRoles] = useState<string[]>([]);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<number | null>(null);
  const scope = roles.length ? `every active ${roles.join(', ')} user` : 'every active user';

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await services.admin.broadcast({ title: title.trim(), body: body.trim(), severity, roles: roles.length ? roles : null });
      setSent(r.recipients);
      setTitle('');
      setBody('');
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  };

  return (
    <Panel title="Broadcast a notification" meta={<span>A system notification, sent in batches by a background task</span>}>
      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim() || !body.trim()) return setError('Title and message are required.');
          setError(null);
          setConfirm(true);
        }}
      >
        <Field label="Title" className="sm:col-span-2">
          {({ id }) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} />}
        </Field>
        <Field label="Message" className="sm:col-span-2">
          {({ id }) => <Textarea id={id} rows={3} value={body} onChange={(e) => setBody(e.target.value)} />}
        </Field>
        <Field label="Severity">
          {({ id }) => (
            <Select id={id} value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}>
              <option value="info">Info</option>
              <option value="success">Success</option>
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
            </Select>
          )}
        </Field>
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-sm font-medium text-fg">Recipients</legend>
          <div className="flex flex-wrap gap-3">
            {ROLES.map((r) => (
              <Checkbox key={r} label={r} checked={roles.includes(r)} onChange={(e) => setRoles((cur) => (e.target.checked ? [...cur, r] : cur.filter((x) => x !== r)))} />
            ))}
          </div>
          <p className="text-xs text-fg-3">None selected: everyone.</p>
        </fieldset>
        <div className="flex flex-col gap-3 sm:col-span-2">
          <FormError message={error} />
          <Button type="submit" variant="primary" icon={Send} className="self-start">
            Send broadcast
          </Button>
          {sent !== null && (
            <p role="status" className="text-sm text-fg-2">
              Accepted: {formatNumber(sent)} recipients.
            </p>
          )}
        </div>
      </form>
      <ConfirmDialog
        open={confirm}
        title="Send this broadcast?"
        description={`“${title.trim()}” goes to ${scope}, in the app and on their notification channels. It cannot be recalled.`}
        confirmLabel="Send"
        destructive={false}
        busy={busy}
        onConfirm={() => void send()}
        onCancel={() => setConfirm(false)}
      />
    </Panel>
  );
}

/** Admin › Content: news sources and articles, the economic calendar, broadcasts. */
export function AdminContentPage() {
  return (
    <div className="flex flex-col gap-5">
      <SourcesPanel />
      <PublishPanel />
      <SentimentPanel />
      <CalendarPanel />
      <BroadcastPanel />
    </div>
  );
}
