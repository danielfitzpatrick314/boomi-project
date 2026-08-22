export type Verdict = "isolated" | "watch" | "systemic" | "insufficient_data";

export type RelatedProductRelation = "same_manufacturer" | "same_ingredient";

export interface RelatedProduct {
  name: string;
  manufacturer: string;
  relation: RelatedProductRelation;
  reason: string;
}

export interface VerdictResult {
  recall_number: string;
  verdict: Verdict;
  recommended_action: string;
  summary: string;
  evidence: string[];
  related_products: RelatedProduct[];
  open_questions: string[];
}

/** Deterministic case facts pulled directly from the recall record (not the
 * model's prose), so the header a user reads first is never at the mercy of
 * the LLM transcribing a firm name or date correctly. */
export interface CaseSnapshot {
  firm: string | null;
  drug_name: string | null;
  product: string | null;
  classification: string | null;
  date: string | null;
  reason: string | null;
  status: string | null;
}

export interface ToolCallEvent {
  type: "tool_call";
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
}

export interface VerdictEvent {
  type: "verdict";
  verdict: VerdictResult;
  case: CaseSnapshot;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  raw?: string;
}

/** Sent every few seconds independent of tool-call progress, so the UI can show
 * real elapsed time and prove the connection is alive even mid-step, rather than
 * static "..." dots that look identical whether a step takes 5 seconds or 5 minutes. */
export interface HeartbeatEvent {
  type: "heartbeat";
  elapsed: number;
}

export type StreamEvent = ToolCallEvent | VerdictEvent | ErrorEvent | HeartbeatEvent;

export interface ExampleCase {
  id: string;
  recall_number: string;
  label: string;
  hint: string;
}

export interface FirmExampleCase {
  id: string;
  firm: string;
  label: string;
  hint: string;
}

export interface Examples {
  recall: ExampleCase[];
  firm: FirmExampleCase[];
}

export interface RecallFeedItem {
  recall_number: string;
  firm: string;
  drug_name: string;
  product: string;
  reason: string;
  classification: string;
  date: string;
}

export const VERDICT_META: Record<
  Verdict,
  { label: string; color: string; soft: string; description: string }
> = {
  isolated: {
    label: "Isolated",
    color: "var(--color-isolated)",
    soft: "var(--color-isolated-soft)",
    description: "One-off. No firm pattern, no credible linked signal.",
  },
  watch: {
    label: "Watch",
    color: "var(--color-watch)",
    soft: "var(--color-watch-soft)",
    description: "Some signal present, but not conclusive either way.",
  },
  systemic: {
    label: "Systemic",
    color: "var(--color-systemic)",
    soft: "var(--color-systemic-soft)",
    description: "Repeated, related pattern — escalate.",
  },
  insufficient_data: {
    label: "Insufficient data",
    color: "var(--color-insufficient)",
    soft: "var(--color-insufficient-soft)",
    description: "Too early or too thin to call confidently.",
  },
};
