import { motion, AnimatePresence } from "framer-motion";
import { Clock, FileCheck2, Loader2 } from "lucide-react";
import type { ToolCallEvent } from "../lib/types";
import { TOOL_META } from "../lib/toolMeta";

interface Props {
  queryLabel: string;
  trace: ToolCallEvent[];
  elapsed: number;
}

function fmtElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

/** The main thing on screen while an investigation runs. The step-by-step
 * trace below is real and available, but nobody should have to read it to
 * know the tool is working and a plain-language answer is coming -- this
 * card is that reassurance, updated live from the same trace data plus a
 * heartbeat-driven elapsed-time counter, so a slow step and a frozen page
 * never look identical: the clock either keeps ticking or it doesn't. */
export default function ProgressStatus({ queryLabel, trace, elapsed }: Props) {
  const last = trace[trace.length - 1];
  const currentLabel = last ? TOOL_META[last.name]?.label ?? last.name : "Starting investigation";
  // Real per-turn timing data (see AI_USAGE.md): a turn with genuine reasoning to do
  // routinely takes 15-35s on its own, so 30-90s is normal mid-investigation, not slow.
  const slow = elapsed >= 30;
  const verySlow = elapsed >= 90;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="panel rounded-lg p-4"
    >
      <div className="flex items-center gap-3">
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--color-accent)]" strokeWidth={2} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-semibold text-[var(--color-text)]">
            Investigating {queryLabel}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={currentLabel}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="mt-0.5 flex items-center gap-1 text-[12.5px] text-[var(--color-text-dim)]"
            >
              {currentLabel}…
              {trace.length > 0 && (
                <span className="mono text-[var(--color-text-faint)]">
                  · {trace.length} check{trace.length === 1 ? "" : "s"} so far
                </span>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
        <div
          className={`mono flex shrink-0 items-center gap-1 rounded border px-2 py-1 text-[11px] transition-colors ${
            verySlow
              ? "border-[var(--color-watch)]/40 text-[var(--color-watch)]"
              : "border-[var(--color-border)] text-[var(--color-text-faint)]"
          }`}
          title="Time elapsed -- if this stops climbing, something is genuinely stuck"
        >
          <Clock className="h-3 w-3" />
          {fmtElapsed(elapsed)}
        </div>
      </div>

      {verySlow ? (
        <div className="mt-3 flex items-start gap-1.5 border-t border-[var(--color-border)] pt-3 text-[11.5px] text-[var(--color-watch)]">
          <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Still working — the model does real step-by-step reasoning before each move, which
          can genuinely take a couple of minutes on a firm with a lot of history. It'll finish
          or time out on its own; no need to do anything.
        </div>
      ) : (
        <div className="mt-3 flex items-start gap-1.5 border-t border-[var(--color-border)] pt-3 text-[11.5px] text-[var(--color-text-faint)]">
          <FileCheck2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          A plain-language summary and a recommended action will appear here as soon as this
          finishes{slow ? " — each step involves real reasoning, not a lookup, so this is normal" : ""}.
        </div>
      )}
    </motion.div>
  );
}
