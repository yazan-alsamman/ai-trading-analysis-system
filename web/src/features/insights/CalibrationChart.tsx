import { useId } from 'react';
import type { CalibrationBin } from '@/domain/predictions';
import { formatPercent } from '@/lib/format';

/**
 * Reliability diagram: predicted probability (x) vs observed hit rate (y).
 * Points on the dashed diagonal = well calibrated. Point area ∝ sample size.
 * A data table alternative is provided for screen readers.
 */
export function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const titleId = useId();
  const W = 330;
  const H = 240;
  const pad = { l: 58, r: 12, t: 12, b: 40 };
  const x = (v: number) => pad.l + ((v - 0.4) / 0.6) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - v * (H - pad.t - pad.b);
  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  const xTicks = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1];
  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <figure className="flex flex-col gap-3">
      {/* Rendered 1:1 (not scaled) so axis text stays at the 12px minimum. */}
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={titleId} width={W} height={H} className="max-w-none shrink-0">
        <title id={titleId}>Calibration: predicted probability versus observed rate of reaching the target</title>
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="stroke-line" strokeWidth={1} />
            <text x={pad.l - 6} y={y(t)} textAnchor="end" dominantBaseline="middle" className="fill-fg-3 text-xs">
              {formatPercent(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={`x${t}`} x={x(t)} y={H - pad.b + 16} textAnchor="middle" className="fill-fg-3 text-xs">
            {formatPercent(t)}
          </text>
        ))}
        <line x1={x(0.4)} y1={y(0.4)} x2={x(1)} y2={y(1)} className="stroke-fg-3" strokeDasharray="4 4" strokeWidth={1} />
        <text x={x(0.97)} y={y(0.97) - 8} textAnchor="end" className="fill-fg-3 text-xs">
          perfect calibration
        </text>
        {bins.map((b) => (
          <circle
            key={b.from}
            cx={x(b.meanPredicted)}
            cy={y(b.observedRate)}
            r={4 + 8 * Math.sqrt(b.count / maxCount)}
            className="fill-forecast/35 stroke-forecast"
            strokeWidth={1.5}
          />
        ))}
        <text x={(pad.l + W - pad.r) / 2} y={H - 4} textAnchor="middle" className="fill-fg-2 text-xs">
          Predicted probability
        </text>
        <text transform={`translate(12 ${(pad.t + H - pad.b) / 2}) rotate(-90)`} textAnchor="middle" className="fill-fg-2 text-xs">
          Observed hit rate
        </text>
      </svg>
      <details className="text-sm">
        <summary className="cursor-pointer text-xs text-fg-2 hover:text-fg">Show calibration data table</summary>
        <table className="mt-2 w-full max-w-md text-xs">
          <thead>
            <tr className="text-fg-3">
              <th className="py-1 text-left font-medium">Probability bin</th>
              <th className="py-1 text-right font-medium">Predictions</th>
              <th className="py-1 text-right font-medium">Mean predicted</th>
              <th className="py-1 text-right font-medium">Observed</th>
            </tr>
          </thead>
          <tbody className="num">
            {bins.map((b) => (
              <tr key={b.from} className="border-t border-line">
                <td className="py-1">
                  {formatPercent(b.from)}–{formatPercent(b.to)}
                </td>
                <td className="py-1 text-right">{b.count}</td>
                <td className="py-1 text-right">{formatPercent(b.meanPredicted, 1)}</td>
                <td className="py-1 text-right">{formatPercent(b.observedRate, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
