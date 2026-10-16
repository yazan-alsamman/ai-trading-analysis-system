import { useEffect } from 'react';

const APP = 'AI Trading Assistance';

/** Public site origin for canonical/Open Graph URLs. Set VITE_SITE_URL in production. */
function siteOrigin(): string {
  const env = import.meta.env.VITE_SITE_URL;
  return (env && /^https?:\/\//.test(env) ? env : window.location.origin).replace(/\/+$/, '');
}

function setMeta(attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.content = content;
}

function setCanonical(href: string | null) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!href) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement('link');
    el.rel = 'canonical';
    document.head.appendChild(el);
  }
  el.href = href;
}

/**
 * Per-page title, description, Open Graph and canonical for PUBLIC pages.
 * Application pages call it with `noindex` so they never appear in search.
 */
export function useDocumentMeta({ title, description, path, noindex = false }: { title: string; description?: string; path?: string; noindex?: boolean }): void {
  useEffect(() => {
    const full = title === APP ? APP : `${title} · ${APP}`;
    document.title = full;
    setMeta('name', 'robots', noindex ? 'noindex, nofollow' : 'index, follow');
    if (description) {
      setMeta('name', 'description', description);
      setMeta('property', 'og:description', description);
    }
    setMeta('property', 'og:title', full);
    setMeta('property', 'og:type', 'website');
    setMeta('property', 'og:site_name', APP);
    const url = path && !noindex ? `${siteOrigin()}${path}` : null;
    if (url) setMeta('property', 'og:url', url);
    setCanonical(url);
  }, [title, description, path, noindex]);
}

/** Application and account pages: never indexed, no canonical (titles stay per page). */
export function useNoIndex(): void {
  useEffect(() => {
    setMeta('name', 'robots', 'noindex, nofollow');
    setCanonical(null);
  }, []);
}
