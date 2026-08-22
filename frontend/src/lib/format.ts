/** openFDA dates are YYYYMMDD strings. */
export function parseFdaDate(d: string): Date | null {
  if (!d || d.length !== 8) return null;
  return new Date(Number(d.slice(0, 4)), Number(d.slice(4, 6)) - 1, Number(d.slice(6, 8)));
}

export function formatRelative(d: string): string {
  const date = parseFdaDate(d);
  if (!date) return d;
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days < 0) return "upcoming";
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

/** A search-results link, not a claim that a specific article exists -- openFDA
 * has no news/press-coverage field, so this is the honest version of "link out
 * to coverage": always a real, working URL, never a guessed article link. */
export function newsSearchUrl(firm: string, drugName: string): string {
  const q = `${firm} ${drugName} recall`;
  return `https://www.google.com/search?q=${encodeURIComponent(q)}&tbm=nws`;
}

/** Pulls a human-readable drug name from a recall's free-text
 * product_description. Ports the same paren-depth-aware comma split as
 * src/fda_mcp/resolver.py::extract_product_name -- used here to build a
 * usable case header the moment get_recall's raw result streams in, before
 * the agent finishes, so a timeout doesn't wipe out facts already in hand. */
export function extractProductName(description: string | null | undefined): string {
  if (!description) return "";
  let depth = 0;
  for (let i = 0; i < description.length; i++) {
    const ch = description[i];
    if (ch === "(") depth++;
    else if (ch === ")") depth = Math.max(0, depth - 1);
    else if (ch === "," && depth === 0) return description.slice(0, i).trim();
  }
  return description.trim();
}

/** First clause of the reason string, up to the first colon -- openFDA reasons
 * are usually "Category: long explanation", and the category alone reads
 * cleanly as a feed headline. */
export function reasonHeadline(reason: string): string {
  const idx = reason.indexOf(":");
  return idx > 0 && idx < 60 ? reason.slice(0, idx) : reason;
}
