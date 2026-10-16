import { FlaskConical, History, PlugZap, Radio, SlidersHorizontal, Sparkles, type LucideIcon } from 'lucide-react';
import { Badge, type BadgeTone } from './Badge';

/**
 * Where a value comes from. The interface must always distinguish these six
 * kinds (product brief §3), so every surface uses this one component rather
 * than ad-hoc wording.
 */
export type SourceKind = 'live' | 'historical' | 'model' | 'user' | 'demo' | 'unavailable';

const SOURCES: Record<SourceKind, { label: string; icon: LucideIcon; tone: BadgeTone; detail: string }> = {
  live: { label: 'Live', icon: Radio, tone: 'neutral', detail: 'Verified market data from the connected backend feed.' },
  historical: { label: 'Historical', icon: History, tone: 'neutral', detail: 'Recorded past data. It does not change.' },
  model: { label: 'Model output', icon: Sparkles, tone: 'forecast', detail: 'Produced by the AI model: a probabilistic estimate, not an observed price or a guarantee.' },
  user: { label: 'Your input', icon: SlidersHorizontal, tone: 'accent', detail: 'A parameter you entered. The platform does not verify it.' },
  demo: { label: 'Simulated', icon: FlaskConical, tone: 'demo', detail: 'Demo data generated in the browser — not real market data or model output.' },
  unavailable: { label: 'Not connected', icon: PlugZap, tone: 'warning', detail: 'This needs a backend service that is not connected yet.' },
};

export function SourceTag({ kind, label, detail, className }: { kind: SourceKind; label?: string; detail?: string; className?: string }) {
  const s = SOURCES[kind];
  const Icon = s.icon;
  return (
    <Badge tone={s.tone} title={detail ?? s.detail} {...(className ? { className } : {})}>
      <Icon aria-hidden className="size-3" />
      <span>{label ?? s.label}</span>
    </Badge>
  );
}

export const SOURCE_DEFINITIONS = Object.entries(SOURCES).map(([kind, s]) => ({ kind: kind as SourceKind, label: s.label, detail: s.detail }));
