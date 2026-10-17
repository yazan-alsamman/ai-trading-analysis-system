import { ArrowLeft } from 'lucide-react';
import type { CSSProperties } from 'react';
import { Link, Outlet } from 'react-router';
import { useNoIndex } from '@/hooks/useDocumentMeta';
import { useServices } from '@/app/contexts';
import { BrandMark } from '@/components/brand/BrandMark';
import { SourceTag } from '@/components/ui/SourceTag';

const at = (ms: number) => ({ '--at': `${ms}ms` }) as CSSProperties;

const PRINCIPLES = [
  { n: '01', title: 'Observed ≠ projected', text: 'Model levels and projections are drawn apart from real prices — never mistaken for them.' },
  { n: '02', title: 'Probabilities, explained', text: 'Every model output carries its evidence, its invalidation and what is missing.' },
  { n: '03', title: 'Sized to your capital', text: 'Risk is checked against your own limits. Nothing is ever executed.' },
];

/**
 * A restrained market motif: an observed price path, the NOW boundary, the
 * model's levels and a dashed projection. Static and labelled as an
 * illustration — it is not market data.
 */
function Motif() {
  const path = [
    [0, 150], [24, 142], [48, 148], [72, 128], [96, 134], [120, 116], [144, 122], [168, 104], [192, 110], [216, 92], [240, 98], [264, 84], [288, 90], [312, 76],
  ];
  const d = path.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join(' ');
  const proj = [[312, 76], [340, 66], [368, 60], [396, 50], [424, 44]];
  const pd = proj.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join(' ');
  return (
    <figure className="relative">
      <svg viewBox="0 0 500 190" className="h-auto max-h-48 w-full" aria-hidden>
        <defs>
          <linearGradient id="auth-area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x="312" y="10" width="140" height="170" style={{ fill: 'var(--chart-forecast-region)' }} />
        <path d={`${d} L312 180 L0 180 Z`} fill="url(#auth-area)" className="m-fade" style={at(900)} />
        <path d={d} fill="none" pathLength={1} className="m-draw stroke-accent" strokeWidth="2" strokeLinejoin="round" style={{ ...at(300), '--dur': '1300ms', '--len': 1 } as CSSProperties} />
        {[
          [38, 'stroke-up', 'TP'],
          [80, 'stroke-accent', 'Entry'],
          [108, 'stroke-down', 'SL'],
        ].map(([y, cls, label]) => (
          <g key={label as string} className="m-fade" style={at(1750 + Number(y) * 2)}>
            <line x1="300" x2="448" y1={y as number} y2={y as number} className={cls as string} strokeDasharray="4 4" strokeWidth="1" />
            <text x="454" y={(y as number) + 4} fontSize="12" className="fill-fg-3 num">
              {label}
            </text>
          </g>
        ))}
        <path d={pd} fill="none" className="m-fade stroke-forecast" strokeWidth="2" strokeDasharray="6 5" style={at(2100)} />
        {proj.slice(1).map(([x, y], i) => (
          <circle key={x} cx={x} cy={y} r="2.6" className="m-pop fill-forecast" style={at(2150 + i * 110)} />
        ))}
        <g className="m-fade" style={at(1600)}>
          <line x1="312" x2="312" y1="4" y2="180" className="stroke-fg-3" strokeDasharray="2 3" />
          <text x="306" y="186" textAnchor="end" fontSize="12" className="fill-fg-3 num">
            NOW
          </text>
          <circle cx="312" cy="76" r="4" className="fill-fg" />
        </g>
      </svg>
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-3">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full bg-accent" /> Observed
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-4 border-t-2 border-dashed border-forecast" /> Model projection
        </span>
        <span>Illustration — not market data</span>
      </figcaption>
    </figure>
  );
}

export function AuthLayout() {
  const { source } = useServices();
  useNoIndex();
  return (
    <div className="flex min-h-dvh bg-canvas">
      <aside className="atmosphere relative hidden w-[min(640px,50vw)] shrink-0 flex-col justify-between overflow-hidden border-r border-line p-10 lg:flex xl:p-14">
        <Link to="/" viewTransition aria-label="AI Trading Assistance — website" className="self-start" style={{ viewTransitionName: 'brand' }}>
          <BrandMark />
        </Link>
        <div className="reveal flex flex-col gap-8 py-8">
          <div>
            <p className="eyebrow mb-4">Gold &amp; FX research terminal</p>
            <h2 className="display text-d2 text-fg [@media(min-height:960px)]:xl:text-d1">
              Evidence before <em>conviction.</em>
            </h2>
            <p className="mt-4 max-w-md text-md text-fg-2">
              Read price, question the model and size the risk against your own limits — with every number labelled for where it came from.
            </p>
          </div>
          <Motif />
          <ol className="grid grid-cols-3 gap-6 border-t border-line pt-6">
            {PRINCIPLES.map((p) => (
              <li key={p.n}>
                <p className="num text-xs text-accent">{p.n}</p>
                <p className="mt-1.5 text-sm font-medium text-fg">{p.title}</p>
                <p className="mt-1 text-xs text-fg-3">{p.text}</p>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-xs text-fg-3">Graduation project · 2026 · Analysis only, never execution</p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <Link to="/" viewTransition aria-label="AI Trading Assistance — website" className="lg:hidden">
              <BrandMark />
            </Link>
            <Link to="/" viewTransition className="hidden items-center gap-1.5 text-sm text-fg-2 hover:text-fg lg:inline-flex">
              <ArrowLeft aria-hidden className="size-4" /> Back to the website
            </Link>
          </div>
          {source === 'demo' && <SourceTag kind="demo" label="Demo mode" detail="No backend is connected: sign-in creates a local demo session." />}
        </header>
        <main id="main" className="flex flex-1 items-start justify-center px-4 py-8 sm:items-center sm:py-10">
          <div className="w-full max-w-[420px]">
            <Outlet />
          </div>
        </main>
        <footer className="px-6 py-4 text-center text-xs text-fg-3">Analysis and decision support only. Not financial advice. This platform does not execute trades.</footer>
      </div>
    </div>
  );
}
