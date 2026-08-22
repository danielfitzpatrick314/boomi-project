import { motion } from "framer-motion";
import { OctagonAlert, RotateCw } from "lucide-react";

interface Props {
  message: string;
  raw?: string;
  /** True when a case header rendered above this card, or the investigation
   * log below it has real steps in it -- i.e. the run didn't fail before
   * producing anything usable. Softens the framing accordingly. */
  partial?: boolean;
  onRetry?: () => void;
}

export default function ErrorCard({ message, raw, partial, onRetry }: Props) {
  const timedOut = message.toLowerCase().includes("timed out");
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="panel rounded-lg border-l-[3px] p-4"
      style={{ borderLeftColor: "var(--color-systemic)" }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold" style={{ color: "var(--color-systemic)" }}>
          <OctagonAlert className="h-4 w-4" />
          {timedOut ? "Investigation timed out" : "Investigation failed"}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--color-accent)] px-3 py-1.5 text-[12px] font-semibold text-white transition-colors hover:bg-[var(--color-accent)]/85"
          >
            <RotateCw className="h-3 w-3" /> Retry
          </button>
        )}
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--color-text-dim)]">{message}</p>
      {partial && (
        <p className="mt-1.5 text-[12px] leading-relaxed text-[var(--color-text-faint)]">
          The recall itself was found before this happened — see the details above{raw ? "" : " and the full step-by-step log below"}.
        </p>
      )}
      {raw && (
        <pre className="mono mt-2 max-h-40 overflow-auto rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-2 text-[11px] text-[var(--color-text-faint)]">
          {raw}
        </pre>
      )}
    </motion.div>
  );
}
