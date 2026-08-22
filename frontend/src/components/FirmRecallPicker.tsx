import { motion } from "framer-motion";
import { Building2, ChevronRight, Pill, X } from "lucide-react";
import type { RecallFeedItem } from "../lib/types";
import { classColor, classLabel, fmtFdaDate } from "../lib/classification";
import { reasonHeadline } from "../lib/format";

interface Props {
  kind: "firm" | "product";
  queryLabel: string;
  items: RecallFeedItem[];
  loading: boolean;
  error: string | null;
  onSelect: (item: RecallFeedItem) => void;
  onCancel: () => void;
}

/** Neither a firm nor a product name jumps straight into a full agent
 * investigation -- either can match several recalls, and picking the wrong
 * one silently would be worse than making the user pick the right one. This
 * lists what openFDA has so a specific recall_number can be chosen, then that
 * recall number drives the normal single-case investigation. */
export default function FirmRecallPicker({ kind, queryLabel, items, loading, error, onSelect, onCancel }: Props) {
  const Icon = kind === "firm" ? Building2 : Pill;
  const noun = kind === "firm" ? "firm" : "product";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="panel overflow-hidden rounded-lg"
    >
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex min-w-0 items-center gap-2 text-[13px] font-semibold text-[var(--color-text)]">
          <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--color-text-dim)]" />
          <span className="truncate">
            {loading ? "Searching" : `${items.length} recall${items.length === 1 ? "" : "s"} found`} for "
            {queryLabel}"
          </span>
        </div>
        <button
          onClick={onCancel}
          className="shrink-0 rounded p-1 text-[var(--color-text-faint)] transition-colors hover:text-[var(--color-text)]"
          title="Cancel"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading && (
        <div className="flex flex-col gap-1 p-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-[60px] animate-pulse rounded bg-black/[0.03]" />
          ))}
        </div>
      )}

      {!loading && error && (
        <p className="p-4 text-[13px] text-[var(--color-text-dim)]">{error}</p>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="p-4 text-[13px] text-[var(--color-text-dim)]">
          No recalls found for {noun} "{queryLabel}" in openFDA's enforcement data
          {kind === "firm"
            ? ' -- check the spelling, or try a shorter version of the name (e.g. drop "Inc." / "LLC").'
            : " -- that's consistent with it being flagged only as a watch item, not a confirmed problem."}
        </p>
      )}

      {!loading && items.length > 0 && (
        <ul className="flex flex-col divide-y divide-[var(--color-border)]">
          {items.map((item) => {
            const color = classColor(item.classification);
            return (
              <li key={item.recall_number}>
                <button
                  onClick={() => onSelect(item)}
                  className="group flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-black/[0.025]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span
                        className="mono rounded border px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wide"
                        style={{ color, borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}
                      >
                        {classLabel(item.classification)}
                      </span>
                      <span className="mono text-[10.5px] text-[var(--color-text-faint)]">
                        {fmtFdaDate(item.date)}
                      </span>
                      <span className="mono text-[10.5px] text-[var(--color-text-faint)]">{item.recall_number}</span>
                    </div>
                    <div className="mt-1 text-[13px] font-semibold leading-snug text-[var(--color-text)]">
                      {item.drug_name}
                    </div>
                    {kind === "product" && (
                      <div className="mt-0.5 text-[11px] text-[var(--color-text-faint)]">{item.firm}</div>
                    )}
                    <div className="mt-0.5 line-clamp-1 text-[11.5px] text-[var(--color-text-dim)]">
                      {reasonHeadline(item.reason)}
                    </div>
                  </div>
                  <span className="mt-1 flex shrink-0 items-center gap-1 text-[10.5px] font-medium text-[var(--color-accent)] opacity-0 transition-opacity group-hover:opacity-100">
                    Investigate <ChevronRight className="h-2.5 w-2.5" />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </motion.div>
  );
}
