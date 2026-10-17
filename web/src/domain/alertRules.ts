import type { PriceAlert } from './alerts';

/**
 * True when the move from `previous` to `current` crosses the alert level in
 * the alert's direction. Touching the level counts; starting beyond it does not
 * (an alert fires on a crossing, not on a state).
 */
export function crossesLevel(alert: Pick<PriceAlert, 'condition' | 'price'>, previous: number, current: number): boolean {
  return alert.condition === 'crosses_above' ? previous < alert.price && current >= alert.price : previous > alert.price && current <= alert.price;
}
