import { motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Factory,
  FlaskConical,
  Network,
  Search,
  ShieldAlert,
  Eye,
  ShieldCheck,
} from "lucide-react";
import type { CaseSnapshot, VerdictResult } from "../lib/types";
import { VERDICT_META } from "../lib/types";
import CaseHeader from "./CaseHeader";
import SeverityGauge from "./SeverityGauge";
import CopyReportButton from "./CopyReportButton";

const VERDICT_ICON = {
  isolated: ShieldCheck,
  watch: Eye,
  systemic: ShieldAlert,
  insufficient_data: CircleHelp,
};

const RELATION_META = {
  same_manufacturer: { label: "Same manufacturer", icon: Factory },
  same_ingredient: { label: "Same ingredient", icon: FlaskConical },
};

interface Props {
  result: VerdictResult;
  caseSnapshot: CaseSnapshot;
  onCheckProduct: (product: string) => void;
}

export default function VerdictCard({ result, caseSnapshot, onCheckProduct }: Props) {
  const meta = VERDICT_META[result.verdict];
  const Icon = VERDICT_ICON[result.verdict];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="panel overflow-hidden rounded-lg border-l-[3px]"
      style={{ borderLeftColor: meta.color }}
    >
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-2.5">
        <span className="mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-faint)]">
          Investigation finding
        </span>
        <div className="flex items-center gap-2.5">
          <CopyReportButton result={result} caseSnapshot={caseSnapshot} />
          <span className="mono max-w-[40%] truncate text-[11px] text-[var(--color-text-faint)]" title={result.recall_number}>
            {result.recall_number}
          </span>
        </div>
      </div>

      <CaseHeader caseSnapshot={caseSnapshot} />

      <div className="p-5">
        <div className="flex items-center gap-2 text-[13px] font-semibold" style={{ color: meta.color }}>
          <Icon className="h-4 w-4" strokeWidth={2} />
          {meta.label.toUpperCase()}
          <span className="font-normal text-[var(--color-text-faint)]">— {meta.description}</span>
        </div>

        <div className="mt-3">
          <SeverityGauge classification={caseSnapshot.classification} verdict={result.verdict} />
        </div>

        {result.recommended_action && (
          <div
            className="mt-4 flex items-start gap-2.5 rounded border-l-2 px-3.5 py-3"
            style={{ borderLeftColor: meta.color, background: meta.soft }}
          >
            <ArrowRight className="mt-0.5 h-4 w-4 shrink-0" style={{ color: meta.color }} />
            <div>
              <div className="mono text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-faint)]">
                Recommended action
              </div>
              <p className="mt-0.5 text-[13.5px] font-medium leading-relaxed text-[var(--color-text)]">
                {result.recommended_action}
              </p>
            </div>
          </div>
        )}

        {result.summary && (
          <div className="mt-4">
            <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-faint)]">
              Summary
            </h3>
            <p className="text-[14px] leading-relaxed text-[var(--color-text-dim)]">{result.summary}</p>
          </div>
        )}

        {result.evidence.length > 0 && (
          <div className="mt-5">
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-faint)]">
              Supporting findings
            </h3>
            <ul className="flex flex-col gap-1.5">
              {result.evidence.map((item, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.08 + i * 0.03, duration: 0.25 }}
                  className="flex items-start gap-2 text-[13px] leading-relaxed text-[var(--color-text-dim)]"
                >
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: meta.color }} />
                  {item}
                </motion.li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-5">
          <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-faint)]">
            <Network className="h-3.5 w-3.5" /> Related products to watch
          </h3>

          {result.related_products.length > 0 ? (
            <ul className="flex flex-col gap-1.5">
              {result.related_products.map((p, i) => {
                const rel = RELATION_META[p.relation];
                const RelIcon = rel?.icon ?? Network;
                return (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 + i * 0.03, duration: 0.25 }}
                  >
                    <button
                      onClick={() => onCheckProduct(p.name)}
                      className="group w-full rounded border border-[var(--color-border)] px-3 py-2.5 text-left transition-colors hover:border-[var(--color-border-hover)] hover:bg-black/[0.02]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                        <div className="flex min-w-0 items-center gap-1.5">
                          <RelIcon className="h-3 w-3 shrink-0 text-[var(--color-text-faint)]" />
                          <span className="truncate text-[13px] font-semibold text-[var(--color-text)]">{p.name}</span>
                        </div>
                        <span className="mono shrink-0 rounded border border-[var(--color-border)] px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-[var(--color-text-faint)]">
                          {rel?.label ?? p.relation}
                        </span>
                      </div>
                      <div className="mt-0.5 text-[11.5px] text-[var(--color-text-faint)]">{p.manufacturer}</div>
                      <p className="mt-1 text-[12.5px] leading-relaxed text-[var(--color-text-dim)]">{p.reason}</p>
                      <span className="mt-1 flex items-center gap-1 text-[10.5px] font-medium text-[var(--color-accent)] opacity-0 transition-opacity group-hover:opacity-100">
                        <Search className="h-2.5 w-2.5" /> Check this product's recall history
                      </span>
                    </button>
                  </motion.li>
                );
              })}
            </ul>
          ) : (
            <p className="text-[12.5px] leading-relaxed text-[var(--color-text-faint)]">
              No other currently-marketed products could be identified as related to this recall.
            </p>
          )}
        </div>

        {result.open_questions.length > 0 && (
          <div className="mt-5 rounded border border-[var(--color-border)] bg-black/[0.025] p-3.5">
            <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-faint)]">
              <CircleHelp className="h-3.5 w-3.5" /> Limitations
            </h3>
            <ul className="flex flex-col gap-1.5">
              {result.open_questions.map((item, i) => (
                <li key={i} className="text-[12.5px] leading-relaxed text-[var(--color-text-faint)]">
                  · {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </motion.div>
  );
}
