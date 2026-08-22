#!/usr/bin/env python3
"""Run the agent against eval/cases.py and diff its verdict against the
hand-researched ground truth in ground_truth_research.md. Writes a full
transcript (every tool call, every result, the final verdict) per case to
eval/results/<case_id>.json as receipts -- not just pass/fail.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from agent.investigator import run_investigation_sync  # noqa: E402

from cases import CASES  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    passed = 0

    for case in CASES:
        print(f"\n=== {case['id']} ({case['recall_number']}) ===")
        print(f"expected: {case['expected_verdict']}")

        calls = []
        trace = run_investigation_sync(
            {"recall_number": case["recall_number"]},
            on_tool_call=lambda r: calls.append(asdict(r)),
        )

        actual = (trace.final_json or {}).get("verdict")
        acceptable = set(case.get("acceptable_verdicts", [case["expected_verdict"]]))
        ok = actual in acceptable
        passed += ok
        print(f"actual:   {actual}  {'PASS' if ok else 'FAIL'}")

        (RESULTS_DIR / f"{case['id']}.json").write_text(
            json.dumps(
                {
                    "case": case,
                    "actual_verdict": actual,
                    "pass": ok,
                    "tool_calls": calls,
                    "final_json": trace.final_json,
                    "final_text_raw": trace.final_text,
                },
                indent=2,
                default=str,
            )
        )

    print(f"\n{passed}/{len(CASES)} passed. Full transcripts in {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
