import { motion } from "framer-motion";
import { Gauge } from "lucide-react";
import { computeSeverity, SEVERITY_META, type SeverityTier } from "../lib/severity";
import type { Verdict } from "../lib/types";

interface Props {
  classification: string | null | undefined;
  verdict: Verdict;
}

const TIERS: SeverityTier[] = ["low", "moderate", "high", "critical"];

/** How urgently this finding deserves attention, combining the recall's own
 * FDA classification with our verdict -- two signals that are each useful
 * alone but more useful together (a Class I recall that's still isolated
 * reads very differently from a Class III recall that's part of a systemic
 * pattern). Purely computed, not model-authored -- see lib/severity.ts. */
export default function SeverityGauge({ classification, verdict }: Props) {
  const severity = computeSeverity(classification, verdict);

  if (!severity) {
    return (
      <div className="flex items-center gap-2 rounded border border-[var(--color-border)] bg-black/[0.02] px-3.5 py-2.5 text-[12px] text-[var(--color-text-faint)]">
        <Gauge className="h-3.5 w-3.5 shrink-0" />
        Not enough data yet to gauge priority -- see limitations below.
      </div>
    );
  }

  const meta = SEVERITY_META[severity.tier];
  const markerPct = ((severity.score - 1) / 2) * 100; // score is 1-3

  return (
    <div className="rounded border border-[var(--color-border)] px-3.5 py-3" style={{ background: meta.soft }}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[12.5px] font-semibold" style={{ color: meta.color }}>
          <Gauge className="h-3.5 w-3.5" />
          {meta.label.toUpperCase()}
        </div>
        <span className="text-[11px] text-[var(--color-text-faint)]">{severity.explanation}</span>
      </div>

      <div className="relative mt-2.5 h-1.5 w-full overflow-visible rounded-full bg-[var(--color-border)]">
        <div className="flex h-full w-full overflow-hidden rounded-full">
          {TIERS.map((t) => (
            <div key={t} className="h-full flex-1" style={{ background: SEVERITY_META[t].color, opacity: 0.35 }} />
          ))}
        </div>
        <motion.div
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-white shadow-sm"
          style={{ background: meta.color }}
          initial={{ left: "0%", opacity: 0 }}
          animate={{ left: `${markerPct}%`, opacity: 1 }}
          transition={{ duration: 0.5, ease: "easeOut", delay: 0.15 }}
        />
      </div>
    </div>
  );
}
