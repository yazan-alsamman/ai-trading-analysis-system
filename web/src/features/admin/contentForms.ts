/** Validation helpers of the admin Content page (limits from docs/news-ingestion.md). */

export const SOURCE_KEY = /^[a-z0-9_.-]{2,64}$/;

/** "XAU/USD:0.8, EUR" → tags; relevance defaults to 1 and must be 0..1. */
export function parseTags(text: string): { tags: { symbol: string; relevance: number }[]; error: string | null } {
  const tags: { symbol: string; relevance: number }[] = [];
  for (const raw of text.split(/[,\n]/).map((t) => t.trim()).filter(Boolean)) {
    const [symbol = '', rel] = raw.split(':').map((x) => x.trim());
    const relevance = rel === undefined || rel === '' ? 1 : Number(rel);
    if (symbol.length < 2 || symbol.length > 32) return { tags: [], error: `“${raw}”: the symbol must have 2–32 characters.` };
    if (!Number.isFinite(relevance) || relevance < 0 || relevance > 1) return { tags: [], error: `“${raw}”: relevance must be between 0 and 1.` };
    tags.push({ symbol, relevance });
  }
  if (tags.length > 20) return { tags: [], error: 'At most 20 instrument tags.' };
  return { tags, error: null };
}

/** A `datetime-local` value read as UTC → ISO 8601 with Z, or null when empty/invalid. */
export function localUtcToIso(value: string): string | null {
  if (!value) return null;
  const t = Date.parse(value.length === 16 ? `${value}:00Z` : `${value}Z`);
  return Number.isFinite(t) ? new Date(t).toISOString() : null;
}

export const isHttpUrl = (v: string) => /^https?:\/\/\S+$/i.test(v.trim());
