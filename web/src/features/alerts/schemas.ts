import { z } from 'zod';
import { getInstrument, INSTRUMENT_SYMBOLS } from '@/domain/instruments';
import { formatPrice } from '@/lib/format';

/** Max distance of an alert level from the current price — catches typos like 10.85 for 1.085. */
export const MAX_ALERT_DISTANCE = 0.3;

const decimals = (value: number) => {
  const text = String(value);
  return text.includes('e-') ? Number(text.split('e-')[1]) : (text.split('.')[1]?.length ?? 0);
};

/**
 * Price alert form (SF16). Built per call because two rules depend on the
 * live price: the level must lie in the direction of the condition, and
 * within ±30% of the current price.
 */
export function priceAlertSchema(currentPrice: (symbol: (typeof INSTRUMENT_SYMBOLS)[number]) => number | undefined) {
  return z
    .object({
      symbol: z.enum(INSTRUMENT_SYMBOLS),
      condition: z.enum(['crosses_above', 'crosses_below']),
      price: z.number({ error: 'Enter a price level.' }).positive('The price level must be greater than zero.'),
      channels: z.array(z.enum(['app', 'email', 'telegram'])).min(1, 'Choose at least one delivery channel.'),
      note: z.string().trim().max(120, 'Keep the note under 120 characters.'),
    })
    .superRefine((v, ctx) => {
      const inst = getInstrument(v.symbol);
      if (decimals(v.price) > inst.pricePrecision) {
        ctx.addIssue({ code: 'custom', path: ['price'], message: `${inst.display} is quoted to ${inst.pricePrecision} decimal places.` });
        return;
      }
      const current = currentPrice(v.symbol);
      if (current === undefined) return;
      if (Math.abs(v.price - current) / current > MAX_ALERT_DISTANCE) {
        ctx.addIssue({ code: 'custom', path: ['price'], message: `The level is more than 30% from the current price (${formatPrice(current, inst.pricePrecision)}). Check for a typo.` });
      } else if (v.condition === 'crosses_above' && v.price <= current) {
        ctx.addIssue({ code: 'custom', path: ['price'], message: `For “crosses above”, choose a level above the current price (${formatPrice(current, inst.pricePrecision)}).` });
      } else if (v.condition === 'crosses_below' && v.price >= current) {
        ctx.addIssue({ code: 'custom', path: ['price'], message: `For “crosses below”, choose a level below the current price (${formatPrice(current, inst.pricePrecision)}).` });
      }
    });
}

export type PriceAlertFormValues = z.infer<ReturnType<typeof priceAlertSchema>>;

/** Opportunity notification preferences (SF2). */
export const opportunityPrefsSchema = z.object({
  enabled: z.boolean(),
  minProbability: z.number().min(0.5).max(0.95),
  symbols: z.array(z.enum(INSTRUMENT_SYMBOLS)).min(1, 'Choose at least one instrument.'),
  timeframes: z.array(z.enum(['15m', '1h', '4h'])).min(1, 'Choose at least one timeframe.'),
  directions: z.array(z.enum(['long', 'short'])).min(1, 'Choose at least one direction.'),
  channels: z.array(z.enum(['app', 'email', 'telegram'])).min(1, 'Choose at least one delivery channel.'),
});
