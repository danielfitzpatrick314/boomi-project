import {
  FileSearch,
  History,
  Network,
  Stethoscope,
  Search,
  ShieldQuestion,
  type LucideIcon,
} from "lucide-react";
import type { ToolCallEvent } from "./types";

export const TOOL_META: Record<string, { label: string; icon: LucideIcon }> = {
  get_recall: { label: "Pulling recall detail", icon: FileSearch },
  search_recalls: { label: "Searching recalls", icon: Search },
  search_recalls_by_firm: { label: "Checking firm's recall history", icon: History },
  find_related_products: { label: "Cross-referencing related products", icon: Network },
  find_related_adverse_events: { label: "Linking adverse events", icon: Stethoscope },
  search_adverse_events: { label: "Searching adverse events", icon: Stethoscope },
  resolve_firm_name_match: { label: "Resolving firm name match", icon: ShieldQuestion },
};

function fmtDate(d?: string): string {
  if (!d || d.length !== 8) return d ?? "";
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
}

/** A short, human synopsis of a tool result -- what a reviewer skimming the
 * trace should see at a glance, before expanding the raw JSON. */
export function summarize(event: ToolCallEvent): string {
  const r = event.result as any;
  switch (event.name) {
    case "get_recall": {
      if (!r?.found) return `No recall found for ${event.arguments.recall_number}`;
      const rec = r.recall;
      return `${rec.classification} · ${rec.recalling_firm} · ${fmtDate(rec.recall_initiation_date)}`;
    }
    case "search_recalls_by_firm":
      return r?.total === 1
        ? "Exactly 1 recall on record — no history"
        : `${r?.total ?? 0} recalls on record for this firm`;
    case "search_recalls":
      return `${r?.total ?? 0} matching recalls found`;
    case "find_related_products": {
      if (!r?.found) return "Recall not found";
      const n = (r.same_manufacturer?.length ?? 0) + (r.same_ingredient?.length ?? 0);
      return n > 0 ? `${n} related product${n === 1 ? "" : "s"} found` : "No related products identified";
    }
    case "find_related_adverse_events": {
      if (!r?.found) return "Recall not found";
      const conf = r.confidence as string;
      return `${r.total_events?.toLocaleString?.() ?? r.total_events} events via ${r.method} (${conf} confidence)`;
    }
    case "search_adverse_events":
      return `${r?.total ?? 0} adverse events matched`;
    case "resolve_firm_name_match":
      return `${r?.similarity_score}% similar (${r?.confidence} confidence)`;
    default:
      return "";
  }
}

/** For find_related_adverse_events specifically, surface the caveat -- this is
 * the field most worth putting in front of a human, not buried in raw JSON. */
export function caveatFor(event: ToolCallEvent): string | null {
  const r = event.result as any;
  if (event.name === "find_related_adverse_events" && r?.caveat) {
    return r.caveat as string;
  }
  return null;
}
