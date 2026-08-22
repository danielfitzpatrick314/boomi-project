import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

/** The "still working" row at the bottom of the live log. Previous version was a
 * static icon plus three 1px dots barely pulsing in opacity -- easy to mistake for
 * not animating at all, which is exactly what got reported. This one is unmistakably
 * alive: a spinning icon in a breathing halo, plus a classic chat-style bouncing typing
 * indicator, both large enough to actually notice. */
export default function AgentPulse({ label }: { label: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-3 px-3.5 py-2.5 text-[var(--color-text-dim)]"
    >
      <div className="relative flex h-7 w-7 shrink-0 items-center justify-center">
        <motion.span
          className="absolute inset-0 rounded-full bg-[var(--color-accent-soft)]"
          animate={{ scale: [0.85, 1.25, 0.85], opacity: [0.6, 0, 0.6] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="relative flex h-7 w-7 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--color-accent)]" strokeWidth={2.25} />
        </div>
      </div>

      <div className="flex items-center gap-2 text-[12.5px]">
        <span>{label}</span>
        <span className="flex items-end gap-[3px]">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="h-[6px] w-[6px] rounded-full bg-[var(--color-accent)]"
              animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
            />
          ))}
        </span>
      </div>
    </motion.div>
  );
}
