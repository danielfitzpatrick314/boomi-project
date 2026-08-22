import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Loader2 } from "lucide-react";
import type { Examples } from "../lib/types";

type Mode = "recall_number" | "firm";

/** Bump `nonce` any time a query should be pushed into the form from outside
 * (a click in the recall feed sidebar, or on a related-product manufacturer) --
 * a plain prop change alone wouldn't re-trigger if the same value is clicked twice. */
export interface ExternalQuery {
  recallNumber?: string;
  firm?: string;
  nonce: number;
}

interface Props {
  examples: Examples;
  loading: boolean;
  onSubmit: (query: { recall_number?: string; firm?: string }) => void;
  externalQuery?: ExternalQuery | null;
}

export default function InvestigateForm({ examples, loading, onSubmit, externalQuery }: Props) {
  const [mode, setMode] = useState<Mode>("recall_number");
  const [value, setValue] = useState("");

  useEffect(() => {
    if (externalQuery?.recallNumber) {
      setMode("recall_number");
      setValue(externalQuery.recallNumber);
    } else if (externalQuery?.firm) {
      setMode("firm");
      setValue(externalQuery.firm);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalQuery?.nonce]);

  function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!value.trim() || loading) return;
    onSubmit(mode === "recall_number" ? { recall_number: value.trim() } : { firm: value.trim() });
  }

  function pickRecallExample(ex: Examples["recall"][number]) {
    setValue(ex.recall_number);
    onSubmit({ recall_number: ex.recall_number });
  }

  function pickFirmExample(ex: Examples["firm"][number]) {
    setValue(ex.firm);
    onSubmit({ firm: ex.firm });
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="panel w-full rounded-lg p-1.5"
    >
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="flex shrink-0 gap-0.5 rounded-md bg-black/[0.04] p-0.5">
          {(
            [
              ["recall_number", "Recall #"],
              ["firm", "Firm"],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`relative rounded px-3 py-2 text-[13px] font-medium transition-colors ${
                mode === m ? "text-white" : "text-[var(--color-text-faint)] hover:text-[var(--color-text-dim)]"
              }`}
            >
              {mode === m && (
                <motion.div
                  layoutId="mode-pill"
                  className="absolute inset-0 rounded bg-[var(--color-accent)]"
                  transition={{ duration: 0.18, ease: "easeOut" }}
                />
              )}
              <span className="relative">{label}</span>
            </button>
          ))}
        </div>

        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={mode === "recall_number" ? "e.g. D-1178-2018" : "e.g. Westminster Pharmaceuticals"}
          className="mono min-w-0 flex-1 bg-transparent px-3 py-2.5 text-[14px] text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] focus:outline-none"
          disabled={loading}
        />

        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="flex shrink-0 items-center justify-center gap-1.5 rounded-md bg-[var(--color-accent)] px-4 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--color-accent)]/85 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Investigating
            </>
          ) : mode === "firm" ? (
            <>
              List recalls <ArrowRight className="h-3.5 w-3.5" />
            </>
          ) : (
            <>
              Investigate <ArrowRight className="h-3.5 w-3.5" />
            </>
          )}
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-1.5 px-2 pb-1.5 pt-2.5">
        {mode === "recall_number" ? (
          <>
            <span className="text-[11px] text-[var(--color-text-faint)]">Examples:</span>
            {examples.recall.map((ex) => (
              <button
                key={ex.id}
                type="button"
                disabled={loading}
                onClick={() => pickRecallExample(ex)}
                title={ex.hint}
                className="rounded border border-[var(--color-border)] px-2.5 py-1 text-[11px] text-[var(--color-text-dim)] transition-colors hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-35"
              >
                {ex.label}
              </button>
            ))}
          </>
        ) : (
          <>
            <span className="text-[11px] text-[var(--color-text-faint)]">Example firms:</span>
            {examples.firm.map((ex) => (
              <button
                key={ex.id}
                type="button"
                disabled={loading}
                onClick={() => pickFirmExample(ex)}
                title={ex.hint}
                className="rounded border border-[var(--color-border)] px-2.5 py-1 text-[11px] text-[var(--color-text-dim)] transition-colors hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-35"
              >
                {ex.label}
              </button>
            ))}
          </>
        )}
      </div>
    </motion.div>
  );
}
