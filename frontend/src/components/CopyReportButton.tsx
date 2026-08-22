import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Copy } from "lucide-react";
import type { CaseSnapshot, VerdictResult } from "../lib/types";
import { toMarkdown } from "../lib/report";

interface Props {
  result: VerdictResult;
  caseSnapshot: CaseSnapshot;
}

export default function CopyReportButton({ result, caseSnapshot }: Props) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(toMarkdown(result, caseSnapshot));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard permission denied or unavailable -- fail silently, button just won't confirm
    }
  }

  return (
    <button
      onClick={handleCopy}
      title="Copy this finding as Markdown"
      className="flex shrink-0 items-center gap-1 rounded border border-[var(--color-border)] px-2 py-1 text-[10.5px] text-[var(--color-text-faint)] transition-colors hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
    >
      <AnimatePresence mode="wait" initial={false}>
        {copied ? (
          <motion.span
            key="copied"
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.15 }}
            className="flex items-center gap-1"
            style={{ color: "var(--color-isolated)" }}
          >
            <Check className="h-3 w-3" /> Copied
          </motion.span>
        ) : (
          <motion.span
            key="copy"
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.15 }}
            className="flex items-center gap-1"
          >
            <Copy className="h-3 w-3" /> Copy report
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  );
}
