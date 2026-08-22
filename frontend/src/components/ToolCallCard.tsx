import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, TriangleAlert } from "lucide-react";
import type { ToolCallEvent } from "../lib/types";
import { TOOL_META, summarize, caveatFor } from "../lib/toolMeta";

export default function ToolCallCard({ event, index }: { event: ToolCallEvent; index: number }) {
  const [open, setOpen] = useState(false);
  const meta = TOOL_META[event.name] ?? { label: event.name, icon: ChevronDown };
  const Icon = meta.icon;
  const synopsis = summarize(event);
  const caveat = caveatFor(event);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut", delay: index === 0 ? 0 : 0.02 }}
      className="panel overflow-hidden rounded-lg"
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left transition-colors hover:bg-black/[0.02]"
      >
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-[var(--color-border)] text-[var(--color-text-dim)]">
          <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-[13px] font-medium text-[var(--color-text)]">{meta.label}</span>
            <span className="mono truncate text-[11px] text-[var(--color-text-faint)]">
              {event.name}({Object.values(event.arguments)[0] as string})
            </span>
          </div>
          {synopsis && <p className="mt-0.5 truncate text-[12.5px] text-[var(--color-text-dim)]">{synopsis}</p>}
        </div>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-[var(--color-text-faint)] transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {caveat && (
        <div className="mx-3.5 mb-3 flex gap-2 rounded border-l-2 border-[var(--color-watch)] bg-[var(--color-watch-soft)] px-3 py-2 text-[11.5px] text-[var(--color-text-dim)]">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-watch)]" />
          <span>{caveat}</span>
        </div>
      )}

      <motion.div
        initial={false}
        animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="overflow-hidden"
      >
        <pre className="mono mx-3.5 mb-3.5 max-h-72 overflow-auto rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-[11px] leading-relaxed text-[var(--color-text-dim)]">
          {JSON.stringify(event.result, null, 2)}
        </pre>
      </motion.div>
    </motion.div>
  );
}
