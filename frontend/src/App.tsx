import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Background from "./components/Background";
import Header from "./components/Header";
import Welcome from "./components/Welcome";
import type { Role } from "./components/Welcome";
import InvestigateForm from "./components/InvestigateForm";
import type { ExternalQuery } from "./components/InvestigateForm";
import RecentRecalls from "./components/RecentRecalls";
import ProgressStatus from "./components/ProgressStatus";
import InvestigationLog from "./components/InvestigationLog";
import VerdictCard from "./components/VerdictCard";
import ErrorCard from "./components/ErrorCard";
import CaseHeader from "./components/CaseHeader";
import FirmRecallPicker from "./components/FirmRecallPicker";
import { extractProductName } from "./lib/format";
import type {
  CaseSnapshot,
  Examples,
  RecallFeedItem,
  StreamEvent,
  ToolCallEvent,
  VerdictResult,
} from "./lib/types";

type Phase = "idle" | "picker" | "running" | "done" | "error";
type PickerKind = "firm" | "product";

const IDENTIFIED_KEY = "ri_identified";

export default function App() {
  const [identified, setIdentified] = useState(() => {
    try {
      return localStorage.getItem(IDENTIFIED_KEY) === "1";
    } catch {
      return false;
    }
  });

  function handleIdentify(role: Role, detail?: string) {
    setIdentified(true);
    try {
      localStorage.setItem(IDENTIFIED_KEY, "1");
    } catch {
      // ignore -- private browsing / storage disabled shouldn't block the app
    }
    fetch("/api/identify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, detail }),
    }).catch(() => {});
  }

  const [examples, setExamples] = useState<Examples>({ recall: [], firm: [] });
  const [feed, setFeed] = useState<RecallFeedItem[]>([]);
  const [feedLoading, setFeedLoading] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [trace, setTrace] = useState<ToolCallEvent[]>([]);
  const [verdict, setVerdict] = useState<VerdictResult | null>(null);
  const [caseSnapshot, setCaseSnapshot] = useState<CaseSnapshot | null>(null);
  const [error, setError] = useState<{ message: string; raw?: string } | null>(null);
  const [activeRecallNumber, setActiveRecallNumber] = useState<string | null>(null);
  const [externalQuery, setExternalQuery] = useState<ExternalQuery | null>(null);
  const [logExpanded, setLogExpanded] = useState(true);
  const [queryLabel, setQueryLabel] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [pickerKind, setPickerKind] = useState<PickerKind>("firm");
  const [pickerLabel, setPickerLabel] = useState("");
  const [pickerItems, setPickerItems] = useState<RecallFeedItem[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const phaseRef = useRef<Phase>("idle");

  function loadFeed() {
    setFeedLoading(true);
    fetch("/api/recent-recalls")
      .then((r) => r.json())
      .then(setFeed)
      .catch(() => {})
      .finally(() => setFeedLoading(false));
  }

  useEffect(() => {
    fetch("/api/examples")
      .then((r) => r.json())
      .then(setExamples)
      .catch(() => {});
    loadFeed();
    return () => esRef.current?.close();
  }, []);

  const lastQueryRef = useRef<{ recall_number?: string; firm?: string } | null>(null);

  function runInvestigation(query: { recall_number?: string; firm?: string }) {
    lastQueryRef.current = query;
    esRef.current?.close();
    setTrace([]);
    setVerdict(null);
    setCaseSnapshot(null);
    setError(null);
    setPhase("running");
    phaseRef.current = "running";
    setLogExpanded(true);
    setQueryLabel(query.recall_number ?? query.firm ?? "");
    setActiveRecallNumber(query.recall_number ?? null);
    setElapsed(0);

    const params = new URLSearchParams(query as Record<string, string>);
    const es = new EventSource(`/api/investigate?${params.toString()}`);
    esRef.current = es;

    es.onmessage = (msg) => {
      const evt: StreamEvent = JSON.parse(msg.data);
      if (evt.type === "tool_call") {
        setTrace((t) => [...t, evt]);
        // Populate the case header the moment the recall itself is fetched, rather
        // than waiting for the final verdict -- if the investigation times out
        // later, these facts (already retrieved and real) shouldn't disappear
        // along with it.
        if (evt.name === "get_recall") {
          const result = evt.result as { found?: boolean; recall?: Record<string, unknown> } | undefined;
          const recall = result?.found ? result.recall : undefined;
          if (recall) {
            const description = (recall.product_description as string) ?? "";
            setCaseSnapshot({
              firm: (recall.recalling_firm as string) ?? null,
              drug_name: extractProductName(description) || null,
              product: description || null,
              classification: (recall.classification as string) ?? null,
              date: (recall.recall_initiation_date as string) ?? null,
              reason: (recall.reason_for_recall as string) ?? null,
              status: (recall.status as string) ?? null,
            });
          }
        }
      } else if (evt.type === "heartbeat") {
        setElapsed(evt.elapsed);
      } else if (evt.type === "verdict") {
        setVerdict(evt.verdict);
        setCaseSnapshot(evt.case);
        setActiveRecallNumber(evt.verdict.recall_number);
        setPhase("done");
        phaseRef.current = "done";
        es.close();
      } else if (evt.type === "error") {
        setError({ message: evt.message, raw: evt.raw });
        setPhase("error");
        phaseRef.current = "error";
        es.close();
      }
    };

    es.onerror = () => {
      if (phaseRef.current === "running") {
        setError({ message: "Connection to the agent was lost." });
        setPhase("error");
        phaseRef.current = "error";
      }
      es.close();
    };
  }

  function selectFromFeed(item: RecallFeedItem) {
    if (phase === "running") return;
    setExternalQuery({ recallNumber: item.recall_number, nonce: Date.now() });
    runInvestigation({ recall_number: item.recall_number });
  }

  // Shared by both entry points below: a firm or a product name can match
  // many recalls, so jumping straight into a full investigation off a bare
  // name risked the agent picking a different one than the user meant. List
  // what's on file first and let them pick the specific recall_number, then
  // that drives the normal single-case run.
  function runPickerSearch(kind: PickerKind, value: string) {
    if (phase === "running") return;
    esRef.current?.close();
    setPhase("picker");
    phaseRef.current = "picker";
    setPickerKind(kind);
    setPickerLabel(value);
    setPickerItems([]);
    setPickerError(null);
    setPickerLoading(true);
    const endpoint = kind === "firm" ? "firm-recalls?firm=" : "product-recalls?product=";
    fetch(`/api/${endpoint}${encodeURIComponent(value)}`)
      .then((r) => r.json())
      .then((items: RecallFeedItem[]) => setPickerItems(items))
      .catch(() => setPickerError("Couldn't reach the server. Try again."))
      .finally(() => setPickerLoading(false));
  }

  function searchFirm(firm: string) {
    setExternalQuery({ firm, nonce: Date.now() });
    runPickerSearch("firm", firm);
  }

  // Related products aren't recalled themselves -- they're flagged only for
  // sharing a manufacturer or ingredient with something that was. This checks
  // whether the product itself has any recall history of its own, across any
  // manufacturer, rather than re-searching the whole firm.
  function checkProductHistory(product: string) {
    runPickerSearch("product", product);
  }

  function submitQuery(query: { recall_number?: string; firm?: string }) {
    if (query.firm) searchFirm(query.firm);
    else runInvestigation(query);
  }

  // Deliberately does not push item.recall_number into the search box via
  // externalQuery -- the user searched a firm/product and picked one of the
  // results below; the box should keep showing what they typed, not swap it
  // for an opaque D-####-#### code they never entered.
  function pickFromPicker(item: RecallFeedItem) {
    runInvestigation({ recall_number: item.recall_number });
  }

  const pulseLabel = trace.length === 0 ? "Starting investigation…" : "Deciding next step…";

  return (
    <AnimatePresence>
      {!identified ? (
        <Welcome key="welcome" onComplete={handleIdentify} />
      ) : (
        <motion.div
          key="main"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="relative min-h-screen"
        >
          <Background />

          <main className="mx-auto max-w-6xl px-5">
            <Header />

            <div className="grid grid-cols-1 items-start gap-6 py-6 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div className="flex flex-col gap-4">
                <InvestigateForm
                  examples={examples}
                  loading={phase === "running"}
                  onSubmit={submitQuery}
                  externalQuery={externalQuery}
                />

                {phase === "picker" && (
                  <FirmRecallPicker
                    kind={pickerKind}
                    queryLabel={pickerLabel}
                    items={pickerItems}
                    loading={pickerLoading}
                    error={pickerError}
                    onSelect={pickFromPicker}
                    onCancel={() => {
                      setPhase("idle");
                      phaseRef.current = "idle";
                    }}
                  />
                )}

                {phase === "running" && (
                  <ProgressStatus queryLabel={queryLabel} trace={trace} elapsed={elapsed} />
                )}

                {phase === "error" && error && (
                  <>
                    {caseSnapshot?.firm && (
                      <div className="panel overflow-hidden rounded-lg">
                        <CaseHeader caseSnapshot={caseSnapshot} />
                      </div>
                    )}
                    <ErrorCard
                      message={error.message}
                      raw={error.raw}
                      partial={!!caseSnapshot?.firm}
                      onRetry={() => lastQueryRef.current && runInvestigation(lastQueryRef.current)}
                    />
                  </>
                )}

                {phase === "done" && verdict && caseSnapshot && (
                  <VerdictCard result={verdict} caseSnapshot={caseSnapshot} onCheckProduct={checkProductHistory} />
                )}

                <InvestigationLog
                  trace={trace}
                  running={phase === "running"}
                  pulseLabel={pulseLabel}
                  expanded={logExpanded}
                  onToggleExpanded={() => setLogExpanded((v) => !v)}
                />

                {phase === "idle" && (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.15, duration: 0.3 }}
                    className="mt-6 text-[13px] text-[var(--color-text-faint)]"
                  >
                    Enter a recall number or firm, click one of the examples above, or select an item
                    from the recall list to begin.
                  </motion.p>
                )}
              </div>

              <RecentRecalls
                items={feed}
                loading={feedLoading}
                activeRecallNumber={activeRecallNumber}
                disabled={phase === "running"}
                onSelect={selectFromFeed}
                onRefresh={loadFeed}
              />
            </div>

            <footer className="border-t border-[var(--color-border)] py-4 text-[11px] text-[var(--color-text-faint)]">
              Data: openFDA drug enforcement &amp; adverse event APIs. Architecture: MCP tool server +
              Claude tool-use agent.
            </footer>
          </main>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
