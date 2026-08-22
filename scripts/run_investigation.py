#!/usr/bin/env python3
"""CLI entry point.

Usage:
    python scripts/run_investigation.py --recall-number D-1178-2018
    python scripts/run_investigation.py --firm "Westminster Pharmaceuticals"
    python scripts/run_investigation.py --recall-number D-0620-2026 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from agent.investigator import run_investigation_sync  # noqa: E402

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--recall-number")
    group.add_argument("--firm")
    parser.add_argument("--model", default=None)
    parser.add_argument("--json", action="store_true", help="print only the final JSON verdict")
    args = parser.parse_args()

    query = {"recall_number": args.recall_number} if args.recall_number else {"firm": args.firm}

    def on_tool_call(record):
        if args.json:
            return
        console.print(f"[bold cyan]-> {record.name}[/bold cyan]({json.dumps(record.arguments)})")
        result_str = json.dumps(record.result, indent=2) if not isinstance(record.result, str) else record.result
        console.print(Panel(result_str[:1500], border_style="dim"))

    model_kwargs = {"model": args.model} if args.model else {}
    trace = run_investigation_sync(query, on_tool_call=on_tool_call, **model_kwargs)

    if args.json:
        print(json.dumps(trace.final_json, indent=2) if trace.final_json else trace.final_text)
        return

    console.print(f"\n[bold]{len(trace.turns)} tool calls made[/bold]\n")
    if trace.final_json:
        console.print(Panel(json.dumps(trace.final_json, indent=2), title="Verdict", border_style="green"))
    else:
        console.print(Panel(trace.final_text, title="Final output (not parsed as JSON)", border_style="red"))


if __name__ == "__main__":
    main()
