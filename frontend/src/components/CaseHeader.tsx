import { ExternalLink } from "lucide-react";
import type { CaseSnapshot } from "../lib/types";
import { classColor, classLabel, fmtFdaDate } from "../lib/classification";
import { newsSearchUrl } from "../lib/format";

interface Props {
  caseSnapshot: CaseSnapshot;
}

/** Deterministic recall facts (firm, product, classification, date) pulled
 * straight from the get_recall result, not the model's prose. Shared by
 * VerdictCard (finished) and the running/error states -- it's set the moment
 * get_recall streams in, so a timeout doesn't erase facts already in hand. */
export default function CaseHeader({ caseSnapshot }: Props) {
  if (!caseSnapshot?.firm) return null;

  return (
    <div className="border-b border-[var(--color-border)] bg-black/[0.02] px-5 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div>
          {caseSnapshot.drug_name && (
            <div className="text-[15px] font-semibold leading-snug text-[var(--color-text)]">{caseSnapshot.drug_name}</div>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <span className="text-[12.5px] text-[var(--color-text-dim)]">{caseSnapshot.firm}</span>
            {caseSnapshot.classification && (
              <span
                className="mono rounded border px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wide"
                style={{
                  color: classColor(caseSnapshot.classification),
                  borderColor: `color-mix(in srgb, ${classColor(caseSnapshot.classification)} 45%, transparent)`,
                }}
              >
                {classLabel(caseSnapshot.classification)}
              </span>
            )}
            <span className="mono text-[11px] text-[var(--color-text-faint)]">{fmtFdaDate(caseSnapshot.date)}</span>
            {caseSnapshot.status && (
              <span className="text-[11px] text-[var(--color-text-faint)]">{caseSnapshot.status}</span>
            )}
          </div>
        </div>
        <a
          href={newsSearchUrl(caseSnapshot.firm, caseSnapshot.drug_name ?? "")}
          target="_blank"
          rel="noopener noreferrer"
          title="Search for news coverage of this recall"
          className="flex shrink-0 items-center gap-1 rounded border border-[var(--color-border)] px-2 py-1 text-[10.5px] text-[var(--color-text-faint)] transition-colors hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
        >
          <ExternalLink className="h-3 w-3" /> Coverage
        </a>
      </div>
      {caseSnapshot.product && (
        <p className="mt-1.5 line-clamp-1 text-[12.5px] text-[var(--color-text-dim)]">{caseSnapshot.product}</p>
      )}
    </div>
  );
}
