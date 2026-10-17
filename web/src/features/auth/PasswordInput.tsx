import { Check, Eye, EyeOff, Minus } from 'lucide-react';
import { useState, type InputHTMLAttributes, type Ref } from 'react';
import { Input } from '@/components/ui/Form';
import { cn } from '@/lib/cn';
import { passwordChecks, passwordStrength } from './schemas';

/** Password field with a visibility toggle and a Caps Lock warning. */
export function PasswordInput({
  ref,
  invalid,
  className,
  onKeyUp,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean; ref?: Ref<HTMLInputElement> }) {
  const [visible, setVisible] = useState(false);
  const [caps, setCaps] = useState(false);
  return (
    <div>
      <div className="relative">
        <Input
          ref={ref}
          type={visible ? 'text' : 'password'}
          invalid={invalid ?? false}
          className={cn('h-11 pr-11', className)}
          onKeyUp={(e) => {
            setCaps(e.getModifierState('CapsLock'));
            onKeyUp?.(e);
          }}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute top-1/2 right-1.5 inline-flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-fg-3 hover:bg-hover hover:text-fg"
        >
          {visible ? <EyeOff aria-hidden className="size-4" /> : <Eye aria-hidden className="size-4" />}
        </button>
      </div>
      {caps && (
        <p role="status" className="mt-1.5 text-xs text-warning">
          Caps Lock is on.
        </p>
      )}
    </div>
  );
}

const STRENGTH = {
  empty: { label: '', bars: 0, cls: 'bg-hover' },
  'too-weak': { label: 'Too weak', bars: 1, cls: 'bg-danger' },
  acceptable: { label: 'Acceptable', bars: 2, cls: 'bg-warning' },
  strong: { label: 'Strong', bars: 3, cls: 'bg-accent' },
} as const;

/** Live feedback against the backend's real rules (required) plus advice (optional). */
export function PasswordStrength({ value, id }: { value: string; id?: string }) {
  const level = passwordStrength(value);
  const s = STRENGTH[level];
  return (
    <div id={id} className="flex flex-col gap-2" aria-live="polite">
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1" aria-hidden>
          {[1, 2, 3].map((i) => (
            <span key={i} className={cn('h-1 flex-1 rounded-full transition-colors', i <= s.bars ? s.cls : 'bg-hover')} />
          ))}
        </div>
        <span className="min-w-20 text-right text-xs whitespace-nowrap text-fg-2">{s.label && `Strength: ${s.label}`}</span>
      </div>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        {passwordChecks(value).map((c) => (
          <li key={c.label} className={cn('flex items-center gap-1.5', c.ok ? 'text-fg-2' : 'text-fg-3')}>
            {c.ok ? <Check aria-hidden className="size-3.5 text-accent" /> : <Minus aria-hidden className="size-3.5" />}
            <span>
              {c.label}
              {!c.required && <span className="text-fg-3"> (advice)</span>}
              <span className="sr-only">{c.ok ? ' — met' : ' — not met'}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
