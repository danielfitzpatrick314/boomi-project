"""FastAPI backend for the Recall Investigator frontend.

Streams the agent's tool calls and final verdict to the browser over SSE as
they happen, reusing the tested investigator.run_investigation loop
unchanged -- this file only bridges its synchronous on_tool_call callback
onto an async queue so a single HTTP request can stream incrementally.

Run from src/: `uvicorn web.api:app --reload --port 8000`
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import re  # noqa: E402

from agent.investigator import DEFAULT_MODEL, run_investigation  # noqa: E402
from fda_mcp.openfda_client import OpenFDAClient  # noqa: E402
from fda_mcp.resolver import extract_product_name, fuzzy_match_firm  # noqa: E402

app = FastAPI(title="Recall Investigator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Real, hand-verified cases from eval/cases.py -- offered as one-click examples
# in the UI so a reviewer doesn't have to know a real recall_number to try it.
# Split by mode so the examples shown always match what the active tab (Recall #
# vs Firm) actually does with a click, instead of one list that only works for
# one of the two modes.
RECALL_EXAMPLES = [
    {
        "id": "westminster-systemic",
        "recall_number": "D-1178-2018",
        "label": "D-1178-2018 — Levothyroxine/Liothyronine Thyroid Tablets",
        "hint": "Repeat offender — 10 recalls across 3 episodes since 2018",
    },
    {
        "id": "nanomaterials-isolated",
        "recall_number": "D-0455-2023",
        "label": "D-0455-2023 — Snowy Range Hand Sanitizer",
        "hint": "One recall on record, ever",
    },
    {
        "id": "beekeepers-insufficient-data",
        "recall_number": "D-0620-2026",
        "label": "D-0620-2026 — Beekeeper's Naturals Nasal Spray",
        "hint": "Very recent recall — too early to have a track record",
    },
]

FIRM_EXAMPLES = [
    {
        "id": "westminster-firm",
        "firm": "Westminster Pharmaceuticals",
        "label": "Westminster Pharmaceuticals",
        "hint": "10 recalls on file across 3 episodes since 2018",
    },
    {
        "id": "glaxosmithkline-firm",
        "firm": "GlaxoSmithKline",
        "label": "GlaxoSmithKline",
        "hint": "Major manufacturer — dozens of recalls on file",
    },
    {
        "id": "nanomaterials-firm",
        "firm": "Nanomaterials Discovery Corp.",
        "label": "Nanomaterials Discovery Corp.",
        "hint": "One recall on record, ever",
    },
]


@app.get("/api/examples")
def get_examples():
    return {"recall": RECALL_EXAMPLES, "firm": FIRM_EXAMPLES}


@app.get("/api/health")
def health():
    return {"ok": True}


# -- who's using this thing -------------------------------------------------
# The welcome screen asks once per browser (tracked client-side via
# localStorage) which persona a visitor identifies as. Persisted here as an
# append-only JSONL log -- real data on a real disk, not a cosmetic UI gesture
# with nothing behind it. Not a database: fine for this build's scope, and
# genuinely inspectable (cat the file, or hit /api/identify/summary).
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
IDENTIFICATIONS_FILE = DATA_DIR / "identifications.jsonl"


class IdentifyRequest(BaseModel):
    role: Literal["pharmacist", "researcher", "other"]
    detail: str | None = None


@app.post("/api/identify")
def identify(payload: IdentifyRequest):
    DATA_DIR.mkdir(exist_ok=True)
    record = {
        "id": str(uuid.uuid4()),
        "role": payload.role,
        "detail": (payload.detail or "").strip()[:200] or None,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with IDENTIFICATIONS_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"ok": True}


@app.get("/api/identify/summary")
def identify_summary():
    if not IDENTIFICATIONS_FILE.exists():
        return {"total": 0, "by_role": {}}
    counts: Counter = Counter()
    total = 0
    for line in IDENTIFICATIONS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        total += 1
        counts[json.loads(line).get("role", "unknown")] += 1
    return {"total": total, "by_role": dict(counts)}


_openfda = OpenFDAClient()


def _to_feed_item(r: dict) -> dict:
    description = r.get("product_description") or ""
    return {
        "recall_number": r.get("recall_number"),
        "firm": r.get("recalling_firm"),
        "drug_name": extract_product_name(description) or "(drug name unavailable)",
        "product": description,
        "reason": r.get("reason_for_recall"),
        "classification": r.get("classification"),
        "date": r.get("recall_initiation_date"),
    }


@app.get("/api/recent-recalls")
def recent_recalls(limit: int = 20):
    """Most recent drug recalls, for the live feed sidebar. Over-fetches and
    de-dupes on (firm, reason, date) -- a single incident (e.g. 5 strengths of
    the same product recalled the same day for the same reason) should read
    as one feed item, not five near-identical ones.

    This reads openFDA's drug enforcement endpoint, which is sourced from FDA's
    weekly Enforcement Report -- it lags FDA.gov's own recall page (which
    posts as press releases go out) by anywhere from days to a few weeks.
    That's a real gap in the underlying data, not something more fetching or
    de-duping here can close; the frontend links out to FDA.gov for the
    complete, most current list."""
    result = _openfda.search_recalls(limit=100)
    seen: set[tuple] = set()
    items = []
    for r in result.results:
        key = (r.get("recalling_firm"), r.get("reason_for_recall"), r.get("recall_initiation_date"))
        if key in seen:
            continue
        seen.add(key)
        items.append(_to_feed_item(r))
        if len(items) >= limit:
            break
    return items


# Shared by both firm and product search: corporate-suffix noise ("LLC", "Inc")
# for firm names, plus generic dosage-form/packaging/route words ("capsules",
# "extended", "release") for product names -- a word this generic matches so
# many unrelated recalls that using it as a wildcard-search anchor produces
# noise, not signal (confirmed: searching "Acetazolamide Extended-Release
# Capsules" without filtering these out returned skin cream and dietary
# supplements that merely also happened to say "capsules").
_SEARCH_STOPWORDS = {
    "inc", "incorporated", "llc", "corp", "corporation", "ltd", "limited", "co", "company", "dba", "the", "and",
    "capsule", "capsules", "tablet", "tablets", "injection", "injectable", "solution", "suspension",
    "extended", "release", "immediate", "delayed", "oral", "topical", "cream", "gel", "spray", "syrup",
    "ointment", "patch", "powder", "chewable", "usp", "vial", "bottle", "count", "dose", "for", "only",
    "sterile", "nonsterile", "sodium", "hydrochloride", "hcl",
}


def _significant_words(value: str) -> list[str]:
    seen: list[str] = []
    for word in re.findall(r"[a-zA-Z]{3,}", value.lower()):
        if word not in _SEARCH_STOPWORDS and word not in seen:
            seen.append(word)
    return seen


def _fuzzy_field_search(field: str, value: str, limit: int) -> list[dict]:
    """Exact-phrase search on `field` is brittle: a misspelling, a compound
    name typed as separate words (e.g. "Glaxo Smith Klein" vs openFDA's
    "GlaxoSmithKline"), or a short product name that's really just a fragment
    of the long free-text `product_description` recalls actually store, all
    return zero hits even for a real match. Falls back to a substring-wildcard
    search per significant word, intersected across words so a single
    coincidentally-shared word (e.g. "Smith" also matching "Smith Drug
    Company") doesn't pull in an unrelated result, then ranks whatever's left
    by fuzzy string similarity to the original query."""
    words = _significant_words(value)
    if not words:
        return []
    pool: dict[str, dict] = {}
    hit_sets: list[set[str]] = []
    for word in words:
        hits: set[str] = set()
        for r in _openfda.search_recalls_field_wildcard(field, word, limit=50).results:
            num = r.get("recall_number")
            if num:
                pool[num] = r
                hits.add(num)
        hit_sets.append(hits)
    matched = set.intersection(*hit_sets) if len(hit_sets) > 1 else hit_sets[0]
    if not matched:
        matched = set.union(*hit_sets) if hit_sets else set()
    candidates = [pool[n] for n in matched]
    candidates.sort(key=lambda r: fuzzy_match_firm(value, r.get(field) or "").score, reverse=True)
    return candidates[:limit]


@app.get("/api/firm-recalls")
def firm_recalls(firm: str, limit: int = 15):
    """Every recall on record for one firm, most recent first -- the list a user
    picks from before drilling into a specific recall_number investigation."""
    raw_results = _openfda.search_recalls(firm=firm, limit=limit).results
    if not raw_results:
        raw_results = _fuzzy_field_search("recalling_firm", firm, limit=limit)
    seen: set[tuple] = set()
    items = []
    for r in raw_results:
        key = (r.get("reason_for_recall"), r.get("recall_initiation_date"))
        if key in seen:
            continue
        seen.add(key)
        items.append(_to_feed_item(r))
    return items


@app.get("/api/product-recalls")
def product_recalls(product: str, limit: int = 15):
    """Recall history for one product name, across any manufacturer -- lets a
    user check whether a "related product to watch" (flagged only because it
    shares a manufacturer or ingredient with something that WAS recalled, not
    because it has any history itself) actually has a recall record of its
    own. Product names here come from the NDC directory ("Gabapentin
    Capsules") which rarely appears verbatim inside a recall's long free-text
    product_description ("Gabapentin Capsules USP 300mg, 100-count bottles,
    Rx only, Manufactured by..."), so this goes straight to the fuzzy fallback
    rather than trying an exact phrase match first."""
    raw_results = _fuzzy_field_search("product_description", product, limit=limit)
    seen: set[tuple] = set()
    items = []
    for r in raw_results:
        key = (r.get("recalling_firm"), r.get("reason_for_recall"), r.get("recall_initiation_date"))
        if key in seen:
            continue
        seen.add(key)
        items.append(_to_feed_item(r))
    return items


# Per-model-call timeouts inside investigator.py bound any *single* step, but a
# handful of steps each coming in just under their own limit -- or a retry silently
# compounding -- can still add up to a multi-minute silent wait with nothing to show
# for it (observed directly: a real investigation stalled for 3.5+ minutes with zero
# backend activity after its 4th tool call, well past any single-call timeout, with
# the SSE stream just... not sending anything, and the UI unable to tell "slow" from
# "dead"). This is the unconditional backstop: whatever the underlying cause, the
# whole investigation gets one hard ceiling, so a stuck request becomes a clear error
# in the UI within a bounded, known time instead of indefinite silence.
INVESTIGATION_TIMEOUT_SECONDS = 240.0
"""Previously 95s, tightened down from an initial 150s on the theory that nothing was
self-recovering past 90s -- that theory was wrong, and was never actually checked
against real per-turn data. Instrumenting agent/investigator.py's tool-use loop (see
AI_USAGE.md) showed individual turns routinely taking 15-35s once there's real
reasoning to do (the model does substantial extended thinking by default on this
model ID), and a normal 5-turn investigation legitimately totaling ~80-90s -- right at
the old ceiling. The 95s value wasn't catching stuck requests, it was cutting off
working ones. This is sized with real headroom above an observed ~5-turn/~85s case for
runs that need more turns (broader searches, more related-product cross-referencing),
while still being a genuine backstop against an actual multi-minute hang."""
HEARTBEAT_INTERVAL_SECONDS = 3.0

# Observed directly in production logs: two overlapping /api/investigate calls
# for the identical recall_number ran concurrently, their turn-by-turn logs
# interleaved, each competing for the same event loop and Anthropic API
# capacity -- a very plausible contributor to a timeout that otherwise looks
# unexplained. This can happen from a genuine double-click, but also silently
# from EventSource's own auto-reconnect-on-drop behavior replaying the same
# GET request while the original run is still alive server-side. Rather than
# trying to eliminate every possible cause, this makes a second concurrent
# request for the same query a clean, immediate error instead of a second,
# competing agent loop.
_INFLIGHT: set[str] = set()


def _query_key(query: dict) -> str:
    return f"recall:{query['recall_number']}" if "recall_number" in query else f"firm:{query['firm'].strip().lower()}"


async def _event_stream(query: dict, model: str):
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    start = asyncio.get_event_loop().time()
    key = _query_key(query)

    if key in _INFLIGHT:
        yield f"data: {json.dumps({'type': 'error', 'message': 'An investigation for this exact query is already running -- wait for it to finish rather than starting a duplicate.'})}\n\n"
        return
    _INFLIGHT.add(key)

    def on_tool_call(record):
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "tool_call", **asdict(record)},
        )

    async def heartbeat():
        # Independent of whatever run() is awaiting -- proves the connection itself
        # is alive and gives the frontend a real elapsed-time signal, rather than
        # static "..." dots that look identical whether the tool is at 5 seconds or
        # 5 minutes.
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            elapsed = asyncio.get_event_loop().time() - start
            await queue.put({"type": "heartbeat", "elapsed": round(elapsed, 1)})

    async def run():
        try:
            trace = await asyncio.wait_for(
                run_investigation(query, model=model, on_tool_call=on_tool_call),
                timeout=INVESTIGATION_TIMEOUT_SECONDS,
            )
            if trace.final_json:
                snapshot = trace.case_snapshot or {}
                description = snapshot.get("product_description") or ""
                case = {
                    "firm": snapshot.get("recalling_firm"),
                    "drug_name": extract_product_name(description) if description else None,
                    "product": description or None,
                    "classification": snapshot.get("classification"),
                    "date": snapshot.get("recall_initiation_date"),
                    "reason": snapshot.get("reason_for_recall"),
                    "status": snapshot.get("status"),
                }
                await queue.put({"type": "verdict", "verdict": trace.final_json, "case": case})
            else:
                await queue.put(
                    {
                        "type": "error",
                        "message": "The agent finished without a parseable verdict.",
                        "raw": trace.final_text,
                    }
                )
        except asyncio.TimeoutError:
            await queue.put(
                {
                    "type": "error",
                    "message": (
                        f"Investigation timed out after {int(INVESTIGATION_TIMEOUT_SECONDS)}s "
                        "without finishing. Normal investigations complete well under this -- "
                        "if you're hitting the ceiling itself, something is likely genuinely "
                        "stuck. Try again."
                    ),
                }
            )
        except Exception as exc:  # surfaced to the UI rather than a dropped connection
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    run_task = asyncio.create_task(run())
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"
    finally:
        heartbeat_task.cancel()
        if not run_task.done():
            run_task.cancel()
        _INFLIGHT.discard(key)


@app.get("/api/investigate")
async def investigate(recall_number: str | None = None, firm: str | None = None, model: str | None = None):
    if not recall_number and not firm:
        raise HTTPException(400, "Provide recall_number or firm")
    query = {"recall_number": recall_number} if recall_number else {"firm": firm}
    return StreamingResponse(
        _event_stream(query, model or DEFAULT_MODEL),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
