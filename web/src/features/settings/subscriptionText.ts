import type { PlanPerks } from '@/domain/social';

/** "19.00 USD / month" — the server's decimal string, never re-rounded. */
export const priceText = (price: string, currency: string, interval: string) => `${price} ${currency} / ${interval}`;

export function perksText(perks: PlanPerks): string {
  const list = [perks.premiumPosts && 'premium posts', perks.chat && 'chat', perks.signalsFeed && 'signal feed'].filter(Boolean);
  return list.length ? list.join(', ') : 'no extra perks';
}
