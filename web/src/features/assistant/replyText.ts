/** The demo composer appends this note as a blockquote; the reply card shows it as its own callout. */
const SIMULATED_NOTE = /\n*>\s*Simulated data:\s*([^\n]+)\s*$/;

export function splitSimulatedNote(content: string): { body: string; note: string | null } {
  const m = SIMULATED_NOTE.exec(content);
  return m ? { body: content.slice(0, m.index).trimEnd(), note: m[1]?.trim() ?? null } : { body: content, note: null };
}
