const CLASS_COLOR: Record<string, string> = {
  "Class I": "var(--color-systemic)",
  "Class II": "var(--color-watch)",
  "Class III": "var(--color-text-faint)",
};

export function classColor(classification: string | null | undefined): string {
  return (classification && CLASS_COLOR[classification]) ?? "var(--color-text-faint)";
}

/** "Class II" -> "CLASS II RECALL" -- the bare "CLASS II" badge read as an
 * unfamiliar label on its own; spelling out what it's a class *of* makes it
 * legible without having to already know FDA recall terminology. */
export function classLabel(classification: string | null | undefined): string {
  if (!classification) return "UNCLASSIFIED";
  return `${classification.replace("Class ", "CLASS ")} RECALL`;
}

export function fmtFdaDate(d: string | null | undefined): string {
  if (!d || d.length !== 8) return d ?? "—";
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
}
