import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, FlaskConical, Radar, Stethoscope, UserRound } from "lucide-react";

export type Role = "pharmacist" | "researcher" | "other";

const ROLES: { id: Role; label: string; desc: string; icon: typeof Stethoscope }[] = [
  {
    id: "pharmacist",
    label: "Pharmacist",
    desc: "I make dispensing, inventory, or recall-response decisions.",
    icon: Stethoscope,
  },
  {
    id: "researcher",
    label: "Researcher",
    desc: "I study drug safety, quality, or regulatory data.",
    icon: FlaskConical,
  },
  {
    id: "other",
    label: "Other",
    desc: "Something else — tell us in one line.",
    icon: UserRound,
  },
];

export default function Welcome({ onComplete }: { onComplete: (role: Role, detail?: string) => void }) {
  const [selected, setSelected] = useState<Role | null>(null);
  const [detail, setDetail] = useState("");

  function choose(role: Role) {
    setSelected(role);
    if (role !== "other") {
      onComplete(role);
    }
  }

  function submitOther(e?: React.FormEvent) {
    e?.preventDefault();
    onComplete("other", detail.trim() || undefined);
  }

  return (
    <motion.div
      key="welcome"
      exit={{ opacity: 0, scale: 1.03, filter: "blur(8px)" }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[var(--color-bg)] px-6"
    >
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="mb-2 flex items-center gap-2.5"
      >
        <div className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-text-dim)]">
          <Radar className="h-4.5 w-4.5" strokeWidth={1.75} />
        </div>
        <span className="serif text-[19px] font-semibold text-[var(--color-text)]">Recall Investigator</span>
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.5, ease: "easeOut" }}
        className="serif mt-7 text-center text-[32px] font-semibold leading-tight text-[var(--color-text)]"
      >
        Who's asking?
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.22, duration: 0.5 }}
        className="mt-2.5 max-w-sm text-center text-[13.5px] leading-relaxed text-[var(--color-text-dim)]"
      >
        Helps us understand who finds this useful. Takes two seconds.
      </motion.p>

      <div className="mt-10 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
        {ROLES.map((r, i) => (
          <motion.button
            key={r.id}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.32 + i * 0.09, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            whileHover={{ y: -3 }}
            whileTap={{ y: 0 }}
            onClick={() => choose(r.id)}
            className={`panel flex flex-col items-start gap-2.5 rounded-lg p-5 text-left transition-colors ${
              selected === r.id
                ? "border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]"
                : "hover:border-[var(--color-border-hover)]"
            }`}
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--color-accent-soft)] text-[var(--color-accent)]">
              <r.icon className="h-4.5 w-4.5" strokeWidth={1.75} />
            </div>
            <div className="text-[14.5px] font-semibold text-[var(--color-text)]">{r.label}</div>
            <div className="text-[12px] leading-snug text-[var(--color-text-faint)]">{r.desc}</div>
          </motion.button>
        ))}
      </div>

      {selected === "other" && (
        <motion.form
          onSubmit={submitOther}
          initial={{ opacity: 0, y: -6, height: 0 }}
          animate={{ opacity: 1, y: 0, height: "auto" }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="mt-4 flex w-full max-w-2xl gap-2 overflow-hidden"
        >
          <input
            autoFocus
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            placeholder="What do you do?"
            className="panel min-w-0 flex-1 rounded-lg px-3.5 py-2.5 text-[14px] text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] focus:border-[var(--color-accent)] focus:outline-none"
          />
          <button
            type="submit"
            className="flex shrink-0 items-center gap-1.5 rounded-lg bg-[var(--color-accent)] px-4 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--color-accent)]/85"
          >
            Continue <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </motion.form>
      )}

      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6, duration: 0.5 }}
        onClick={() => onComplete("other")}
        className="mt-8 text-[12px] text-[var(--color-text-faint)] underline-offset-4 transition-colors hover:text-[var(--color-text-dim)] hover:underline"
      >
        Skip for now
      </motion.button>
    </motion.div>
  );
}
