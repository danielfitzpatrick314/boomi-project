import { motion } from "framer-motion";
import { Newspaper, RefreshCw, ChevronRight, ExternalLink } from "lucide-react";
import type { RecallFeedItem } from "../lib/types";
import { formatRelative, newsSearchUrl, reasonHeadline } from "../lib/format";
import { classColor, classLabel } from "../lib/classification";

interface Props {
  items: RecallFeedItem[];
  loading: boolean;
  activeRecallNumber: string | null;
  disabled: boolean;
  onSelect: (item: RecallFeedItem) => void;
  onRefresh: () => void;
}

export default function RecentRecalls({ items, loading, activeRecallNumber, disabled, onSelect, onRefresh }: Props) {
  return (
    <motion.aside
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, delay: 0.1, ease: "easeOut" }}
      className="flex max-h-[calc(100vh-3rem)] w-full flex-col lg:sticky lg:top-6"
    >
      <div className="mb-2.5 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-text)]">
          <Newspaper className="h-3.5 w-3.5 text-[var(--color-text-dim)]" strokeWidth={1.75} />
          Recent recalls
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded p-1 text-[var(--color-text-faint)] transition-colors hover:text-[var(--color-text)] disabled:opacity-40"
          title="Refresh"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="panel flex-1 overflow-y-auto rounded-lg p-1">
        {items.length === 0 && loading && (
          <div className="flex flex-col gap-1 p-1.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-[72px] animate-pulse rounded bg-black/[0.03]" />
            ))}
          </div>
        )}

        <ul className="flex flex-col divide-y divide-[var(--color-border)]">
          {items.map((item) => {
            const active = item.recall_number === activeRecallNumber;
            const color = classColor(item.classification);
            return (
              <li key={item.recall_number} className="group relative">
                <button
                  onClick={() => onSelect(item)}
                  disabled={disabled}
                  className={`flex w-full flex-col gap-1 px-2.5 py-2.5 pr-7 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                    active ? "bg-[var(--color-accent-soft)]" : "hover:bg-black/[0.025]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className="mono rounded border px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wide"
                      style={{ color, borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}
                    >
                      {classLabel(item.classification)}
                    </span>
                    <span className="mono shrink-0 text-[10.5px] text-[var(--color-text-faint)]">
                      {formatRelative(item.date)}
                    </span>
                  </div>

                  <span className="line-clamp-2 text-[13px] font-semibold leading-snug text-[var(--color-text)]">
                    {item.drug_name}
                  </span>
                  <span className="truncate text-[11px] text-[var(--color-text-faint)]">{item.firm}</span>
                  <span className="line-clamp-2 text-[11.5px] leading-snug text-[var(--color-text-dim)]">
                    {reasonHeadline(item.reason)}
                  </span>

                  <span className="mt-0.5 flex items-center gap-1 text-[10.5px] font-medium text-[var(--color-accent)] opacity-0 transition-opacity group-hover:opacity-100">
                    Investigate <ChevronRight className="h-2.5 w-2.5" />
                  </span>
                </button>

                <a
                  href={newsSearchUrl(item.firm, item.drug_name)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Search for news coverage of this recall"
                  className="absolute right-2 top-2.5 rounded p-1 text-[var(--color-text-faint)] opacity-0 transition-opacity hover:text-[var(--color-accent)] group-hover:opacity-100"
                >
                  <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            );
          })}
        </ul>
      </div>

      <a
        href="https://www.fda.gov/drugs/drug-safety-and-availability/drug-recalls"
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 flex items-center justify-center gap-1.5 rounded-lg border border-[var(--color-border)] px-2.5 py-2 text-[11px] text-[var(--color-text-faint)] transition-colors hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
        title="This list is sourced from openFDA's weekly enforcement report, which can lag FDA.gov by days to weeks"
      >
        See the full, most current list on FDA.gov <ExternalLink className="h-3 w-3" />
      </a>
    </motion.aside>
  );
}
