import { CloudCheck, Server } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { SourceTag } from '@/components/ui/SourceTag';
import type { Instrument } from '@/domain/instruments';
import type { Timeframe } from '@/domain/market';
import { ACCOUNT_CURRENCIES, type AccountCurrency, type RiskProfile, type TradeRisk } from '@/domain/risk';
import { useResource } from '@/hooks/useResource';
import { formatMoney, formatNumber, formatPct } from '@/lib/format';
import { userMessage } from '@/services/errors';
import type { ServerPositionPlan } from '@/services/types';
import { profilesMatch } from './serverProfile';

/**
 * Backend mode: the risk profile also lives on the server. When it differs from
 * this browser's, the user decides — values are never overwritten silently.
 */
export function ServerProfileBanner() {
  const services = useServices();
  const { prefs, setRiskProfile } = usePreferences();
  const res = useResource('server-risk-profile', (signal) => services.riskProfile.get({ signal }));
  const server = res.data;
  if (!server || profilesMatch(prefs.riskProfile, server)) return null;
  // The browser profile only supports its own account currencies (crypto accounts such as USDT are not offered).
  const currencyOk = (ACCOUNT_CURRENCIES as readonly string[]).includes(server.currency);

  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-xl border border-info/40 bg-info-soft px-4 py-3 text-sm">
      <Server aria-hidden className="size-4 shrink-0 text-info" />
      <p className="min-w-0 flex-1 text-fg-2">
        Your <span className="font-medium text-fg">server</span> risk profile differs from this browser’s:{' '}
        <span className="num text-fg">{currencyOk ? formatMoney(server.capital, server.currency) : `${formatNumber(server.capital, 2)} ${server.currency}`}</span>
        {server.riskPerTradePct !== null && <> at {formatPct(server.riskPerTradePct)} per trade</>}
        {server.dailyLossLimitPct !== null && <>, daily limit {formatPct(server.dailyLossLimitPct)}</>}.
      </p>
      {currencyOk && (
        <Button
          size="sm"
          onClick={() =>
            setRiskProfile({
              ...prefs.riskProfile,
              capital: server.capital,
              currency: server.currency as AccountCurrency,
              ...(server.riskPerTradePct !== null ? { maxRiskPerTradePct: server.riskPerTradePct } : {}),
              ...(server.dailyLossLimitPct !== null ? { dailyLossLimitPct: server.dailyLossLimitPct } : {}),
            })
          }
        >
          Use server values
        </Button>
      )}
    </div>
  );
}

/**
 * Backend mode: asks the server to size the same trade (POST /risk/position-size)
 * and shows both results. The browser calculation stays the primary display;
 * the server applies its own rules (fees, maximum position size), so small
 * differences are expected and explained, not hidden.
 */
export function ServerCrossCheck({ instrument, timeframe, risk, entry, stop, profile, riskPct }: { instrument: Instrument; timeframe: Timeframe; risk: TradeRisk; entry: number; stop: number; profile: RiskProfile; riskPct: number }) {
  const services = useServices();
  const [plan, setPlan] = useState<ServerPositionPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The server sizes in the instrument's quote currency: compare only when no conversion is involved.
  const comparable = profile.capital !== null && instrument.quote === profile.currency;

  const run = async () => {
    if (!comparable || profile.capital === null) return;
    setBusy(true);
    setError(null);
    try {
      setPlan(
        await services.riskProfile.positionSize({
          symbol: instrument.symbol,
          timeframe,
          side: risk.direction === 'long' ? 'buy' : 'sell',
          entry,
          stop,
          capital: profile.capital,
          riskPct,
        }),
      );
    } catch (e) {
      setPlan(null);
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="server-check-title" className="rounded-xl border border-line bg-inset p-4">
      <div className="flex flex-wrap items-center gap-2">
        <CloudCheck aria-hidden className="size-4 text-fg-2" />
        <h3 id="server-check-title" className="text-sm font-semibold text-fg">
          Server cross-check
        </h3>
        <SourceTag kind="live" className="ml-auto" />
      </div>
      {!comparable ? (
        <p className="mt-2 text-xs text-fg-3">
          Available when capital is set and the account currency equals the instrument’s quote currency ({instrument.quote}); the server sizes in that currency.
        </p>
      ) : (
        <>
          <p className="mt-1 text-xs text-fg-3">Ask the server to size this trade with your server-side rules. It applies its own fees and position cap.</p>
          <Button size="sm" className="mt-3" onClick={run} loading={busy}>
            Cross-check with the server
          </Button>
        </>
      )}
      {error && (
        <p role="alert" className="mt-3 text-xs text-danger">
          {error}
        </p>
      )}
      {plan && (
        <dl aria-live="polite" className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-fg-3">Server quantity</dt>
            <dd className="num text-fg">{plan.quantity !== null ? formatNumber(plan.quantity, 4) : '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-3">This browser</dt>
            <dd className="num text-fg">{formatNumber(risk.units, 4)}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-3">Server risk amount</dt>
            <dd className="num text-fg">{plan.riskAmount !== null ? formatMoney(plan.riskAmount, profile.currency) : '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-fg-3">Browser loss at stop</dt>
            <dd className="num text-fg">{formatMoney(risk.monetaryRisk, profile.currency)}</dd>
          </div>
          {plan.invalidReason && <p className="col-span-full text-xs text-warning">Server: {plan.invalidReason}</p>}
        </dl>
      )}
    </section>
  );
}
