import { Checkbox, Field, Input } from '@/components/ui/Form';
import type { ParamSpec } from '@/domain/strategies';
import { isBool, type ParamDraft } from './strategyUtils';

function rangeHint(p: ParamSpec): string | undefined {
  if (p.min === null && p.max === null) return undefined;
  if (p.min !== null && p.max !== null) return `${p.min} – ${p.max}`;
  return p.min !== null ? `At least ${p.min}` : `At most ${p.max}`;
}

/** Inputs generated from a strategy's parameter specification. */
export function ParamFields({
  specs,
  draft,
  errors,
  onChange,
}: {
  specs: readonly ParamSpec[];
  draft: ParamDraft;
  errors: Record<string, string>;
  onChange: (draft: ParamDraft) => void;
}) {
  if (specs.length === 0) return <p className="text-sm text-fg-3">This strategy has no parameters.</p>;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {specs.map((p) =>
        isBool(p) ? (
          <Checkbox
            key={p.name}
            className="sm:col-span-2"
            label={p.title}
            checked={draft[p.name] === true}
            onChange={(e) => onChange({ ...draft, [p.name]: e.target.checked })}
          />
        ) : (
          <Field key={p.name} label={p.title} error={errors[p.name]} {...(rangeHint(p) ? { hint: rangeHint(p) } : {})}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                inputMode={p.type === 'int' ? 'numeric' : 'decimal'}
                value={typeof draft[p.name] === 'string' ? (draft[p.name] as string) : ''}
                placeholder={p.default === null ? '' : String(p.default)}
                onChange={(e) => onChange({ ...draft, [p.name]: e.target.value })}
              />
            )}
          </Field>
        ),
      )}
    </div>
  );
}
