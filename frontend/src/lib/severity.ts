import type { Verdict } from "./types";

export type SeverityTier = "low" | "moderate" | "high" | "critical";

export interface Severity {
  tier: SeverityTier;
  label: string;
  /** 1-3, position along the gauge -- not shown directly, just drives the marker. */
  score: number;
  explanation: string;
}

const CLASS_WEIGHT: Record<string, number> = { "Class I": 3, "Class II": 2, "Class III": 1 };
const VERDICT_WEIGHT: Record<Verdict, number> = { systemic: 3, watch: 2, isolated: 1, insufficient_data: 0 };

export const SEVERITY_META: Record<SeverityTier, { label: string; color: string; soft: string }> = {
  low: { label: "Low priority", color: "var(--color-isolated)", soft: "var(--color-isolated-soft)" },
  moderate: { label: "Moderate priority", color: "var(--color-watch)", soft: "var(--color-watch-soft)" },
  high: { label: "High priority", color: "var(--color-high)", soft: "var(--color-high-soft)" },
  critical: { label: "Critical priority", color: "var(--color-systemic)", soft: "var(--color-systemic-soft)" },
};

/** Combines two independent, already-trusted signals into one read on how
 * much this finding deserves attention: the FDA's own classification (how
 * dangerous *this* recall is) and our verdict (whether it's an isolated
 * event or part of a firm-level pattern). Deliberately not model-generated --
 * both inputs are deterministic, so the gauge can't be talked into a
 * different answer by the summary's prose. Returns null for
 * insufficient_data: there isn't enough signal yet for a meaningful reading,
 * and showing a gauge position would overstate what's actually known. */
export function computeSeverity(classification: string | null | undefined, verdict: Verdict): Severity | null {
  if (verdict === "insufficient_data") return null;

  const classWeight = (classification && CLASS_WEIGHT[classification]) ?? 1.5;
  const verdictWeight = VERDICT_WEIGHT[verdict];
  const score = (classWeight + verdictWeight) / 2;

  let tier: SeverityTier;
  if (score >= 2.75) tier = "critical";
  else if (score >= 2.1) tier = "high";
  else if (score >= 1.4) tier = "moderate";
  else tier = "low";

  const classPart = classification ? `${classification} recall` : "unclassified recall";
  const verdictPart =
    verdict === "systemic"
      ? "part of a systemic firm-level pattern"
      : verdict === "watch"
        ? "with some pattern signal worth watching"
        : "an isolated, one-off event";

  return { tier, label: SEVERITY_META[tier].label, score, explanation: `${classPart}, ${verdictPart}.` };
}
