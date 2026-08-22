import { motion } from "framer-motion";
import { Radar } from "lucide-react";

export default function Header() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] py-5"
    >
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-text-dim)]">
          <Radar className="h-4 w-4" strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="serif text-[18px] font-semibold leading-tight text-[var(--color-text)]">
            Recall Investigator
          </h1>
          <p className="text-[12px] leading-tight text-[var(--color-text-faint)]">
            Recall-pattern analysis for FDA-regulated drug products
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 rounded border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-dim)]">
        <span className="relative flex h-1.5 w-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-isolated)] animate-breathe" />
        </span>
        <span className="mono tabular">openFDA · live</span>
      </div>
    </motion.header>
  );
}
