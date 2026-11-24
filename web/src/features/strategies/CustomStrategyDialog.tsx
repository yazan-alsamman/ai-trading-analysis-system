import { CircleCheck, OctagonAlert, RotateCw } from 'lucide-react';
import { useState } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, FormError, Input, Select, Textarea } from '@/components/ui/Form';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import type { CustomStrategy, CustomStrategyKind, DefinitionIssue, DefinitionValidation, StrategyVisibility } from '@/domain/strategies';
import { useResource } from '@/hooks/useResource';
import { formatNumber } from '@/lib/format';
import { isApiError } from '@/services/errors';
import { BUILDER_TEMPLATE, compositeTemplate, errorText } from './strategyUtils';

/** `null` id: create a new strategy. */
export interface CustomEditTarget {
  id: string | null;
}

const pretty = (v: unknown) => JSON.stringify(v, null, 2);

/** The 422 of POST/PUT lists each definition problem with its JSON path (docs/custom-strategies.md). */
function issuesFromError(e: unknown): DefinitionIssue[] {
  const detail: unknown = isApiError(e) ? e.data?.detail : undefined;
  if (!Array.isArray(detail)) return [];
  return (detail as unknown[]).flatMap((d) => {
    if (typeof d !== 'object' || d === null) return [];
    const { path, msg, loc } = d as { path?: unknown; msg?: unknown; loc?: unknown };
    if (typeof msg !== 'string') return [];
    const where = typeof path === 'string' ? path : Array.isArray(loc) ? loc.filter((x) => x !== 'body').join('.') : '';
    return [{ path: where, message: msg.replace(/^Value error, /, '') }];
  });
}

/**
 * Create or edit a builder/composite strategy as its JSON definition, checked
 * by the server (POST /custom-strategies/validate). Edits carry the version
 * they started from; a newer save elsewhere is reported, never overwritten.
 */
export function CustomStrategyDialog({
  target,
  onClose,
  onSaved,
}: {
  target: CustomEditTarget | null;
  onClose: () => void;
  onSaved: (strategy: CustomStrategy, created: boolean) => void;
}) {
  return (
    <Dialog
      open={target !== null}
      onClose={onClose}
      size="lg"
      title={target?.id ? 'Edit custom strategy' : 'New custom strategy'}
      description="Rules are data, never code: the server validates the definition and evaluates it on closed bars only."
    >
      {target && (target.id ? <EditLoader id={target.id} onClose={onClose} onSaved={onSaved} /> : <Editor initial={null} onClose={onClose} onSaved={onSaved} onReload={null} />)}
    </Dialog>
  );
}

function EditLoader({ id, onClose, onSaved }: { id: string; onClose: () => void; onSaved: (s: CustomStrategy, created: boolean) => void }) {
  const services = useServices();
  const res = useResource(`custom-strategy:${id}`, (signal) => services.strategies.getCustom(id, { signal }));
  if (res.status === 'loading')
    return (
      <Loading label="Loading strategy">
        <SkeletonRows rows={5} />
      </Loading>
    );
  if (!res.data) return <ErrorState error={res.error} onRetry={res.reload} compact />;
  // Keyed by version: "Reload latest" re-seeds the editor with the server's copy.
  return (
    <Editor
      key={res.data.version}
      initial={res.data}
      onClose={onClose}
      onSaved={(s, created) => {
        res.setData(() => s);
        onSaved(s, created);
      }}
      onReload={res.reload}
    />
  );
}

function Editor({
  initial,
  onClose,
  onSaved,
  onReload,
}: {
  initial: CustomStrategy | null;
  onClose: () => void;
  onSaved: (s: CustomStrategy, created: boolean) => void;
  onReload: (() => void) | null;
}) {
  const services = useServices();
  const { notify } = useToast();
  const catalog = useResource('custom-strategies:schema', (signal) => services.strategies.builderCatalog({ signal }));
  const [kind, setKind] = useState<CustomStrategyKind>(initial?.kind ?? 'builder');
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [visibility, setVisibility] = useState<StrategyVisibility>(initial?.visibility ?? 'private');
  const [text, setText] = useState(() => pretty(initial?.definition ?? BUILDER_TEMPLATE));
  const [nameError, setNameError] = useState<string | undefined>();
  const [jsonError, setJsonError] = useState<string | undefined>();
  const [issues, setIssues] = useState<DefinitionIssue[]>(initial?.errors ?? []);
  const [validation, setValidation] = useState<DefinitionValidation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<number | null | undefined>(undefined);
  const [busy, setBusy] = useState<'validate' | 'save' | null>(null);

  const template = (k: CustomStrategyKind) => (k === 'builder' ? BUILDER_TEMPLATE : compositeTemplate((catalog.data?.compositeStrategies ?? []).map((s) => s.key)));

  const parse = (): Record<string, unknown> | null => {
    try {
      const value: unknown = JSON.parse(text);
      if (typeof value !== 'object' || value === null || Array.isArray(value)) {
        setJsonError('The definition must be a JSON object.');
        return null;
      }
      setJsonError(undefined);
      return value as Record<string, unknown>;
    } catch (e) {
      setJsonError(`Not valid JSON: ${e instanceof Error ? e.message : 'parse error'}`);
      return null;
    }
  };

  const validate = async () => {
    const definition = parse();
    if (!definition) return;
    setBusy('validate');
    setError(null);
    try {
      const result = initial ? await services.strategies.validate(kind, definition, initial.id) : await services.strategies.validate(kind, definition);
      setValidation(result);
      setIssues(result.errors);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    const trimmed = name.trim();
    setNameError(!trimmed ? 'Enter a name.' : trimmed.length > 60 ? 'Use at most 60 characters.' : undefined);
    const definition = parse();
    if (!trimmed || trimmed.length > 60 || !definition || description.length > 500) return;
    setBusy('save');
    setError(null);
    setConflict(undefined);
    try {
      const saved = initial
        ? await services.strategies.replaceCustom(initial.id, { version: initial.version, definition, name: trimmed, description })
        : await services.strategies.createCustom({ name: trimmed, description, kind, definition, visibility });
      notify(initial ? `“${saved.name}” saved (version ${saved.version}).` : `“${saved.name}” created.`, 'success');
      onSaved(saved, !initial);
    } catch (e) {
      const current: unknown = isApiError(e) ? e.data?.current_version : undefined;
      if (isApiError(e) && e.kind === 'conflict' && initial && current !== undefined) {
        setConflict(typeof current === 'number' ? current : null);
      } else {
        const found = issuesFromError(e);
        if (found.length) setIssues(found);
        setError(errorText(e));
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      {initial && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
          <Badge>{initial.kind === 'builder' ? 'Builder' : 'Composite'}</Badge>
          <span className="num">Version {initial.version}</span>
          {initial.valid ? <Badge tone="up">Can run</Badge> : <Badge tone="danger">Cannot run</Badge>}
          {initial.history !== null && <span>Warm-up {formatNumber(initial.history)} bars</span>}
          <span>
            Used by {initial.usage.activations} activation{initial.usage.activations === 1 ? '' : 's'} ({initial.usage.activeActivations} running), {initial.usage.backtests}{' '}
            backtest{initial.usage.backtests === 1 ? '' : 's'}, {initial.usage.composites} composite{initial.usage.composites === 1 ? '' : 's'}
          </span>
        </div>
      )}

      {conflict !== undefined && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-warning/40 bg-warning-soft px-3 py-2 text-sm text-fg">
          <span className="min-w-0 flex-1">
            This strategy was changed in another tab or on another device{conflict !== null ? ` (now version ${conflict})` : ''}. Your edits were not saved, so nothing was
            overwritten. Copy anything you want to keep, then reload the latest version.
          </span>
          {onReload && (
            <Button size="sm" icon={RotateCw} onClick={onReload}>
              Reload latest
            </Button>
          )}
        </div>
      )}
      <FormError message={error} />

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Name" error={nameError}>
          {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Kind" hint={initial ? 'The kind cannot change after creation.' : 'Builder: indicator rules. Composite: 2–5 strategies that vote.'}>
          {({ id, describedBy }) => (
            <Select
              id={id}
              aria-describedby={describedBy}
              disabled={initial !== null}
              value={kind}
              onChange={(e) => {
                const k = e.target.value === 'composite' ? 'composite' : 'builder';
                setKind(k);
                setText(pretty(template(k)));
                setIssues([]);
                setValidation(null);
              }}
            >
              <option value="builder">Builder</option>
              <option value="composite">Composite</option>
            </Select>
          )}
        </Field>
      </div>
      <Field label="Description" optional error={description.length > 500 ? 'Use at most 500 characters.' : undefined}>
        {({ id, describedBy, invalid }) => (
          <Textarea id={id} aria-describedby={describedBy} invalid={invalid} rows={2} className="min-h-0" value={description} onChange={(e) => setDescription(e.target.value)} />
        )}
      </Field>
      {!initial && (
        <Field label="Visibility" hint="Only analysts, experts and admins can publish a strategy; the server refuses it for traders.">
          {({ id, describedBy }) => (
            <Select id={id} aria-describedby={describedBy} value={visibility} onChange={(e) => setVisibility(e.target.value === 'public' ? 'public' : 'private')}>
              <option value="private">Private</option>
              <option value="public">Public</option>
            </Select>
          )}
        </Field>
      )}

      <Field label="Definition (JSON)" error={jsonError} hint="Edit the rules, then validate. The format is described in the reference below.">
        {({ id, describedBy, invalid }) => (
          <Textarea
            id={id}
            aria-describedby={describedBy}
            invalid={invalid}
            spellCheck={false}
            rows={14}
            className="num"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setValidation(null);
            }}
          />
        )}
      </Field>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => void validate()} loading={busy === 'validate'} disabled={busy === 'save'}>
          Validate
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            setText(pretty(template(kind)));
            setIssues([]);
            setValidation(null);
          }}
        >
          Insert template
        </Button>
        {validation?.valid && (
          <span className="inline-flex items-center gap-1 text-sm text-up">
            <CircleCheck aria-hidden className="size-4" /> Valid{validation.history !== null ? ` · warm-up ${formatNumber(validation.history)} bars` : ''}
          </span>
        )}
      </div>

      {issues.length > 0 && (
        <div role="alert" className="rounded-md border border-danger/40 bg-danger-soft px-3 py-2">
          <p className="mb-1 flex items-center gap-1.5 text-sm font-medium text-fg">
            <OctagonAlert aria-hidden className="size-4 text-danger" /> {issues.length} problem{issues.length === 1 ? '' : 's'} in the definition
          </p>
          <ul className="flex flex-col gap-0.5 text-sm text-fg-2">
            {issues.map((i, n) => (
              <li key={`${i.path}-${n}`}>
                {i.path && <code className="num mr-1.5 text-xs text-fg">{i.path}</code>}
                {i.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="rounded-md border border-line px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium text-fg">Reference: indicators, operators and strategies</summary>
        <div className="pt-3 text-xs text-fg-2">
          {catalog.status === 'loading' ? (
            <p>Loading the editor catalog…</p>
          ) : !catalog.data ? (
            <ErrorState error={catalog.error} onRetry={catalog.reload} compact />
          ) : kind === 'builder' ? (
            <div className="flex flex-col gap-3">
              <p>
                Operands: <code>{'{"type":"indicator","name":…,"params":{…},"output":…}'}</code>, <code>{'{"type":"price","field":…}'}</code>,{' '}
                <code>{'{"type":"constant","value":…}'}</code>, each with an optional <code>shift</code>. Groups: {catalog.data.groups.join(', ')}. Strength:{' '}
                {catalog.data.strengths.join(', ')}. Category (required): {catalog.data.categories.join(', ')}. At most {catalog.data.limits.maxConditions} conditions,{' '}
                {catalog.data.limits.maxDepth} levels deep.
              </p>
              <p>Price fields: {catalog.data.priceFields.join(', ')}</p>
              <div>
                <p className="mb-1 font-medium text-fg">Operators</p>
                <ul className="grid gap-x-4 sm:grid-cols-2">
                  {catalog.data.ops.map((o) => (
                    <li key={o.op}>
                      <code className="text-fg">{o.op}</code> {o.title} ({o.operands.join(', ')}
                      {o.bars ? `, bars ${o.bars.min}–${o.bars.max}` : ''})
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="mb-1 font-medium text-fg">Indicators</p>
                <ul className="grid max-h-48 gap-x-4 overflow-y-auto sm:grid-cols-2">
                  {catalog.data.indicators.map((i) => (
                    <li key={i.name}>
                      <code className="text-fg">{i.name}</code> {i.title}
                      {i.params.length > 0 && ` · ${i.params.map((p) => `${p.name}=${String(p.default)}`).join(', ')}`}
                      {i.outputs.length > 1 && ` · outputs ${i.outputs.join('/')}${i.outputRequired ? ' (output required)' : ''}`}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <p>
                Members: {catalog.data.limits.members.min}–{catalog.data.limits.members.max}, each <code>{'{"ref":…,"params"?:{…},"weight":1}'}</code>. A ref is a
                platform key below or <code>custom:&lt;id&gt;</code> of your own or a public strategy (no params). Modes: {catalog.data.compositeModes.join(', ')}. Window{' '}
                {catalog.data.limits.window.min}–{catalog.data.limits.window.max} bars.
              </p>
              <ul className="grid gap-x-4 sm:grid-cols-2">
                {catalog.data.compositeStrategies.map((s) => (
                  <li key={s.key}>
                    <code className="text-fg">{s.key}</code> {s.title}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </details>

      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <Button onClick={onClose} disabled={busy !== null}>
          Cancel
        </Button>
        <Button variant="primary" type="submit" loading={busy === 'save'} disabled={busy === 'validate'}>
          {initial ? 'Save new version' : 'Create strategy'}
        </Button>
      </div>
    </form>
  );
}
