import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import AgentPulse from "./AgentPulse";
import type { ToolCallEvent } from "../lib/types";

interface Props {
  trace: ToolCallEvent[];
  running: boolean;
  pulseLabel: string;
  expanded: boolean;
  onToggleExpanded: () => void;
}

/** The agent's step-by-step reasoning trail. Expanded by default -- the unfolding
 * chain of tool calls is meant to be watched live, not hidden behind a click. It
 * renders below ProgressStatus (while running) and below VerdictCard (once done),
 * so the summary is always the first thing on screen either way, with the full
 * trace right underneath it for anyone who wants to follow along or audit it. The
 * toggle still lets someone collapse it if they'd rather not see it. */
export default function InvestigationLog({ trace, running, pulseLabel, expanded, onToggleExpanded }: Props) {
  if (trace.length === 0 && !running) return null;

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={onToggleExpanded}
        className="flex w-fit items-center gap-1.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-faint)] transition-colors hover:text-[var(--color-text-dim)]"
      >
        <ChevronRight
          className={`h-3 w-3 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
        />
        Investigation log
        {trace.length > 0 && (
          <span className="mono normal-case tracking-normal text-[var(--color-text-faint)]">
            · {trace.length} step{trace.length === 1 ? "" : "s"}
            {running ? " so far" : ""}
          </span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="log"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-2 pb-1">
              <AnimatePresence initial={false}>
                {trace.map((event, i) => (
                  <ToolCallCard key={i} event={event} index={i} />
                ))}
                {running && (
                  <motion.div key="pulse" layout>
                    <AgentPulse label={pulseLabel} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
