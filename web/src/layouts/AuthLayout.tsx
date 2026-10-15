import { Gauge, Layers, ShieldCheck, Sparkles } from 'lucide-react';
import { Link, Outlet } from 'react-router';
import { useServices } from '@/app/contexts';
import { BrandMark } from '@/components/brand/BrandMark';
import { Badge } from '@/components/ui/Badge';

const POINTS = [
  { icon: Layers, title: 'Charts with an AI layer', text: 'Entry, stop-loss and take-profit zones drawn on live candles — 15m, 1h and 4h.' },
  { icon: Sparkles, title: 'Probabilities, explained', text: 'Every opportunity comes with its probability, confidence band and top contributing factors.' },
  { icon: Gauge, title: 'Accuracy you can audit', text: 'Calibration and the outcome of every prediction are published, not hidden.' },
  { icon: ShieldCheck, title: 'Analysis, never execution', text: 'The platform informs decisions. It never places, modifies or closes a trade.' },
];

/** Illustration of the product's visual rule: observed candles, then a dashed AI forecast. */
function ObservedVsForecast() {
  const candles = [
    [12, 64, 52, 70, 46],
    [28, 54, 60, 66, 48],
    [44, 58, 46, 62, 40],
    [60, 46, 50, 56, 40],
    [76, 50, 40, 54, 34],
    [92, 40, 44, 48, 36],
    [108, 44, 34, 46, 28],
  ] as const;
  return (
    <figure className="rounded-lg border border-line bg-inset p-4">
      <svg viewBox="0 0 200 80" aria-hidden className="h-28 w-full">
        {candles.map(([x, open, close, low, high]) => {
          const up = close < open; // y axis is inverted
          return (
            <g key={x} className={up ? 'stroke-up fill-up' : 'stroke-down fill-down'}>
              <line x1={x} x2={x} y1={high} y2={low} strokeWidth="1.2" />
              <rect x={x - 4} y={Math.min(open, close)} width="8" height={Math.max(2, Math.abs(open - close))} rx="1" />
            </g>
          );
        })}
        <line x1="120" x2="120" y1="6" y2="76" className="stroke-fg-3" strokeDasharray="3 3" strokeWidth="1" />
        <path d="M108 34 L126 30 L140 26 L154 24 L168 19 L184 16" fill="none" className="stroke-forecast" strokeWidth="1.6" strokeDasharray="4 3" />
        {[126, 140, 154, 168, 184].map((x, i) => (
          <circle key={x} cx={x} cy={[30, 26, 24, 19, 16][i]} r="1.8" className="fill-forecast" />
        ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-3">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-[2px] bg-up" />
          Observed prices
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-4 border-t-2 border-dashed border-forecast" />
          AI forecast — never shown as a price
        </span>
        <span>Illustration</span>
      </figcaption>
    </figure>
  );
}

export function AuthLayout() {
  const { source } = useServices();
  return (
    <div className="flex min-h-dvh bg-canvas">
      <aside className="hidden w-[min(560px,46vw)] shrink-0 flex-col justify-between border-r border-line bg-surface p-10 lg:flex">
        <Link to="/workspace" aria-label="AI Trading Assistance home" className="self-start">
          <BrandMark />
        </Link>
        <div className="flex flex-col gap-8">
          <div>
            <h2 className="text-xl leading-tight font-semibold tracking-tight text-fg">
              Forex analysis with AI you can <span className="text-forecast">verify</span>.
            </h2>
            <p className="mt-2 max-w-md text-sm text-fg-2">
              Decision support for experienced traders: live charts, transparent AI probabilities and an honest record of how the model performs.
            </p>
          </div>
          <ObservedVsForecast />
          <ul className="grid gap-4 sm:grid-cols-2">
            {POINTS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" />
                <div>
                  <p className="text-sm font-medium text-fg">{title}</p>
                  <p className="mt-0.5 text-xs text-fg-3">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-fg-3">Graduation project · 2026</p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between px-6">
          <Link to="/workspace" aria-label="AI Trading Assistance home" className="lg:invisible">
            <BrandMark />
          </Link>
          {source === 'demo' && <Badge tone="demo">Demo mode</Badge>}
        </header>
        <main id="main" className="flex flex-1 items-start justify-center px-4 py-10 sm:items-center">
          <div className="w-full max-w-sm">
            <Outlet />
          </div>
        </main>
        <footer className="px-6 py-4 text-center text-xs text-fg-3">
          Analysis and decision support only. Not financial advice. This platform does not execute trades.
        </footer>
      </div>
    </div>
  );
}
