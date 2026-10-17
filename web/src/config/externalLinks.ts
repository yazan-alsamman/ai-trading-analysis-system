/**
 * External destinations shown in the public footer — the ONE place to update them.
 *
 * Every value here must be a verified, official destination. Nothing is
 * guessed: when a destination does not exist yet, it stays `null` (or the list
 * stays empty) and the UI shows an honest "not available yet" state instead of
 * a dead or invented link. See docs/PUBLIC_SITE_CONTENT.md §4.
 *
 * Status on 17 Oct 2026 (checked in the repository):
 *  - Mobile apps: `mobile/` contains only a README (Flutter app not yet in the
 *    repository); no store listing, app ID or bundle ID exists → not published.
 *  - Social accounts: none referenced anywhere in the project → none listed.
 *  - Contact: no public contact address is configured → no contact link.
 */

export type StoreId = 'google-play' | 'app-store';

export interface StoreLink {
  id: StoreId;
  store: string;
  platform: string;
  /** Verified public listing URL, or null while the app is not published. */
  url: string | null;
}

export const APP_STORES: readonly StoreLink[] = [
  { id: 'google-play', store: 'Google Play', platform: 'Android', url: null },
  { id: 'app-store', store: 'App Store', platform: 'iOS', url: null },
];

export type SocialNetwork = 'instagram' | 'facebook' | 'linkedin' | 'youtube' | 'x' | 'telegram';

export interface SocialLink {
  network: SocialNetwork;
  label: string;
  /** Verified official profile URL. */
  url: string;
}

/** Official social profiles. Empty until the brand's accounts are confirmed. */
export const SOCIAL_LINKS: readonly SocialLink[] = [];

/** Public contact address, or null when none has been published. */
export const CONTACT_EMAIL: string | null = null;

/** Only http(s) URLs are ever rendered as external links. */
export function isSafeExternalUrl(url: string | null): url is string {
  if (!url) return false;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:';
  } catch {
    return false;
  }
}
