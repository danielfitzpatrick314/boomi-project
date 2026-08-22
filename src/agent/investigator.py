"""The investigating agent: a Claude tool-use loop wired to the FDA MCP server.

Deliberately not a fixed pipeline. The system prompt below describes an
investigation *protocol* (what to check, in what order, what counts as
evidence) but leaves it to the model to decide which tool to call next
based on what the previous call returned -- that branching is the actual
agentic part of this build. A fixed script that always calls the same five
tools in the same order regardless of findings would not need to be an
agent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from anthropic import AsyncAnthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

from fda_mcp.models import InvestigationResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Deliberately not relying on ambient root-logger config: uvicorn's own startup
    # logging setup disables any logger that already exists at the time it runs (this
    # module is imported by src/web/api.py before uvicorn configures logging), which
    # silently swallowed these logs the first time -- httpx's logger worked only
    # because it's created lazily, after uvicorn's setup runs. Own handler avoids
    # depending on import order at all.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(_handler)
    logger.propagate = False

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"
MAX_TURNS = 16
REQUEST_TIMEOUT_SECONDS = 120.0
REQUEST_MAX_RETRIES = 1
"""Sized from real per-turn timing data (logged below), not a guess: a normal turn once
there's real reasoning to do -- weighing a verdict, picking related products worth
flagging -- routinely runs 15-35s on its own, with 500-1000+ tokens of it extended
thinking the model does by default on this ID, not something this code requests or can
turn off. An earlier version of this timeout was tightened to 40s/95s total on the
theory that anything slower must be stuck; that theory was never actually checked
against real data and was wrong -- it was cutting off legitimately-working turns, not
rescuing stuck ones. This value and the overall ceiling in src/web/api.py were
recalibrated after actually instrumenting turn duration and token usage (see
AI_USAGE.md) rather than guessing again. Still bounded, in case a call is genuinely
stuck rather than just working -- see INVESTIGATION_TIMEOUT_SECONDS in src/web/api.py
for the overall backstop."""

SYSTEM_PROMPT = """\
You are investigating a single FDA drug recall for a pharmaceutical quality/regulatory manager \
who needs to decide how urgently to act on it -- and, just as importantly, what ELSE they should \
be watching because of it. A recall is a signal about a manufacturer and an ingredient, not just \
about one product. Do not stop at "is this one recall isolated or systemic" -- the downstream \
question (what other drugs does this put at risk, and why) is the main point of this investigation, \
not an optional extra. You have tools to query FDA recall history, adverse-event reports (FAERS), \
and the FDA's directory of currently-marketed products. You do not have a browser or any other \
source -- only these tools.

If you were asked to investigate a FIRM rather than a specific recall number, first check that \
firm's recall history. If it has NO recalls on record at all, stop here -- do not try to force the \
rest of this protocol onto a recall that doesn't exist (find_related_products and the adverse-event \
tools all key off a specific recalled product, so they don't apply). Instead, report immediately: \
verdict "isolated" (meaning: no FDA recall history found, nothing to escalate), recommended_action \
something like "No FDA recall on record for this firm; no action needed based on this data source," \
summary stating plainly that no recall was found, related_products and evidence as empty arrays, and \
recall_number set to a short descriptive string like "No FDA recall found for <firm>" since there is \
no real recall number to report. This is a normal, common, and useful outcome -- do not treat it as \
an error or keep searching for something that isn't there.

Investigation protocol for a firm that DOES have a recall to investigate (use judgment on order and \
depth, this is not a fixed script):
1. Pull the recall's full detail: firm, product, classification, stated reason, date.
2. Check the recalling firm's full recall history. Look for repetition, and specifically \
whether prior recalls share a related root cause (e.g. two "contamination" recalls is a \
stronger pattern than one "contamination" and one unrelated "mislabeling").
3. ALWAYS call find_related_products, on every investigation regardless of verdict. It surfaces \
other currently-marketed drugs worth flagging: other products from the same manufacturer (shared \
facility/QC risk), and other products from other manufacturers sharing the recalled product's \
active ingredient (shared raw-material supply chain, or a class-wide chemical issue). From what \
it returns, select the handful that are genuinely worth a person's attention -- not a dump of \
everything -- and write a specific, concrete reason for each (e.g. "Made by the same manufacturer \
as the recalled product, so shares the same facility and quality-control history" or "Contains \
the same active ingredient, so may share the same raw-material supplier implicated in this \
recall"). If it finds nothing (the tool's own caveat explains this happens for older/OTC products \
not in the current NDC directory), say so plainly rather than omitting the topic -- "no other \
currently-marketed products could be identified as related" is itself useful information, not a \
gap to hide.
4. Look for adverse events plausibly linked to this specific product. Pay close attention to \
the `confidence` and `caveat` fields the tools return -- a "low confidence" match (e.g. \
manufacturer-name-only linkage) is weak evidence and should be treated and described as such, \
not cited as if it were solid. Prefer high/medium confidence links.
5. If you have event data, check whether reaction terms plausibly connect to the recall's \
stated reason, and note whether the events cluster before the recall (a signal that was missed) \
or after (real-world consequence of the defect reaching patients).
6. Decide on a verdict:
   - "isolated": one-off, no pattern in firm history, no meaningfully linked adverse events.
   - "watch": some signal (repeat firm history OR plausibly linked events) but not both, or the \
evidence is present but low-confidence/ambiguous.
   - "systemic": clear repeated pattern with a related root cause AND/OR credible (medium+ \
confidence) linked adverse events consistent with the recall's stated reason.
   - "insufficient_data": the recall is too recent, or the data available (firm history, event \
linkage) genuinely doesn't support a confident call either way. Prefer this over guessing. \
Specifically: if this is the firm's ONLY recall on record AND it was initiated within roughly \
the last 6 months, prefer "insufficient_data" over "isolated" -- a firm with one recent recall \
and a firm with one recall and a decade of clean history afterward look identical in the data \
right now, and it is dishonest to call the former "isolated" when there simply hasn't been time \
for a track record (or a FAERS signal) to develop either way.

Do not inflate confidence. If a tool result carries a caveat about data quality, carry that \
caveat into your reasoning and into limitations if it affects your verdict.

You are writing for a working quality/regulatory manager, not a developer. They will never see \
your tool calls -- only this final report. So:
- Never mention a tool name, function name, or internal field name (no "find_related_adverse_events", \
no "manufacturer_name", no "confidence: low" as jargon). Translate every finding into what a \
person would actually write in a case note: "No adverse events could be confidently linked to \
this product" not "find_related_adverse_events returned 0 via manufacturer_name (low confidence)".
- Do cite concrete, checkable facts: recall numbers, dates, counts, classifications. Specificity \
is what makes this trustworthy -- vagueness is not the same as plain language.
- recommended_action is the single most important line you write. It is the one thing a busy \
manager reads if they read nothing else. Make it one concrete sentence telling them what to do \
next, calibrated to the verdict: "isolated" usually means standard recall response and no further \
escalation; "watch" usually means flag it and set a re-check point; "systemic" usually means \
escalate now and look at the manufacturer's broader product line; "insufficient_data" usually \
means treat it as standard process for now and revisit once more time has passed. Adjust for the \
specifics of the case rather than reusing these verbatim.
- Keep limitations to the 2-3 that would actually change someone's decision if resolved -- not \
every gap in the data.

When your investigation is complete, call the submit_report tool with your findings -- that is \
the only way your findings reach the user. Do not describe your conclusions in a plain-text \
response instead of calling it, and do not call it more than once.
"""

SUBMIT_REPORT_TOOL = {
    "name": "submit_report",
    "description": (
        "Submit your completed investigation report. Call this exactly once, as your final "
        "action, once you've finished investigating. This is the only way your findings reach "
        "the user -- a plain-text response is not seen by anyone."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recall_number": {
                "type": "string",
                "description": (
                    "The recall number being investigated. If no FDA recall exists for the "
                    "queried firm, use a short descriptive string instead, e.g. 'No FDA recall "
                    "found for <firm>'."
                ),
            },
            "verdict": {
                "type": "string",
                "enum": ["isolated", "watch", "systemic", "insufficient_data"],
            },
            "recommended_action": {
                "type": "string",
                "description": "One concrete sentence: what should this person do next.",
            },
            "summary": {
                "type": "string",
                "description": (
                    "2-4 sentences, plain language, for a quality manager who has not seen the "
                    "raw data."
                ),
            },
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Plain-language findings, each citing a recall number, count, or date. "
                    "Never mention a tool name or internal field name."
                ),
            },
            "related_products": {
                "type": "array",
                "description": (
                    "0-6 entries. Empty only if find_related_products genuinely found nothing -- "
                    "never fabricate an entry, and never skip calling that tool."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "manufacturer": {"type": "string"},
                        "relation": {"type": "string", "enum": ["same_manufacturer", "same_ingredient"]},
                        "reason": {
                            "type": "string",
                            "description": (
                                "One specific sentence: why this is worth watching because of "
                                "THIS recall."
                            ),
                        },
                    },
                    "required": ["name", "manufacturer", "relation", "reason"],
                },
            },
            "open_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The 2-3 gaps that would actually change the decision, in plain language.",
            },
        },
        "required": [
            "recall_number",
            "verdict",
            "recommended_action",
            "summary",
            "evidence",
            "related_products",
            "open_questions",
        ],
    },
}


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict
    result: dict | str


@dataclass
class InvestigationTrace:
    turns: list[ToolCallRecord] = field(default_factory=list)
    final_text: str = ""
    final_json: dict | None = None
    case_snapshot: dict | None = None
    """Deterministic recall facts (firm, product, classification, date, ...) taken directly
    from the get_recall tool result -- not from the model's prose -- so the UI can render a
    header a user can trust without relying on the LLM to transcribe a firm name correctly."""


def _mcp_tools_to_anthropic(tools) -> list[dict]:
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
        for t in tools
    ]


def _extract_tool_result(result) -> dict | str:
    if not result.content:
        return {}
    block = result.content[0]
    text = getattr(block, "text", None)
    if text is None:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _parse_final_json(text: str) -> dict | None:
    """Tries a few progressively more forgiving strategies before giving up --
    the model is instructed to emit bare JSON, but a markdown fence or a stray
    `//` comment slipping in on some fraction of runs shouldn't turn a good
    investigation into a dropped result the user just sees as 'no summary'."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    for candidate in (text, re.sub(r"(?m)^\s*//.*$", "", text)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


_LEAKED_TAG_RE = re.compile(r"</\w+>|<parameter\b", re.IGNORECASE)
"""Matches fragments like `</summary>` or `<parameter name="...">` -- observed once in
production: the model can emit a submit_report call that's structurally valid JSON (so
pydantic validation alone doesn't catch it) but has other fields' content leaked as escaped
text inside one string field, as if it briefly switched to an XML-style tool-call format
mid-generation. Content-level sanity check, not just a schema check."""


def _validate_report(payload: dict) -> InvestigationResult:
    """Raises ValidationError (missing/mistyped fields) or ValueError (leaked-tag
    corruption) if `payload` isn't a report worth trusting. Both are caught by the
    caller and turned into a tool_result error so the model can resubmit -- Anthropic's
    tool-use schema is a strong hint to the model, not a server-enforced contract, so a
    required field can still come back missing or a string field can still come back
    corrupted, and both are worth catching before they reach a user as "the summary."""
    result = InvestigationResult.model_validate(payload)
    for field in (result.summary, result.recommended_action, *result.evidence, *result.open_questions):
        if _LEAKED_TAG_RE.search(field):
            raise ValueError(f"a text field contains a leaked tag fragment: {field[:120]!r}")
    return result


async def run_investigation(
    query: dict,
    model: str = DEFAULT_MODEL,
    max_turns: int = MAX_TURNS,
    on_tool_call=None,
) -> InvestigationTrace:
    """query: {"recall_number": "..."} or {"firm": "..."} -- becomes the user's opening message."""
    if "recall_number" in query:
        opening = f"Investigate recall {query['recall_number']}."
        query_label = query["recall_number"]
    elif "firm" in query:
        opening = f"Investigate the most relevant recent recall from firm '{query['firm']}'."
        query_label = query["firm"]
    else:
        raise ValueError("query must contain 'recall_number' or 'firm'")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fda_mcp.server"],
        cwd=str(Path(__file__).resolve().parent.parent),
    )

    anthropic = AsyncAnthropic(timeout=REQUEST_TIMEOUT_SECONDS, max_retries=REQUEST_MAX_RETRIES)
    trace = InvestigationTrace()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            tools = _mcp_tools_to_anthropic(mcp_tools) + [SUBMIT_REPORT_TOOL]

            messages: list[dict] = [{"role": "user", "content": opening}]

            for turn_index in range(max_turns):
                turn_started = time.monotonic()
                response = await anthropic.messages.create(
                    model=model,
                    max_tokens=8192,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                )
                duration = time.monotonic() - turn_started
                usage = response.usage
                logger.info(
                    "[%s] turn %d: %.1fs, stop_reason=%s, input_tokens=%s, output_tokens=%s, "
                    "thinking_tokens=%s, cache_read=%s",
                    query_label,
                    turn_index,
                    duration,
                    response.stop_reason,
                    usage.input_tokens,
                    usage.output_tokens,
                    getattr(usage.output_tokens_details, "thinking_tokens", None)
                    if usage.output_tokens_details
                    else None,
                    usage.cache_read_input_tokens,
                )

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                text_blocks = [b.text for b in response.content if b.type == "text"]

                messages.append({"role": "assistant", "content": response.content})

                # The model's final answer arrives as a tool call, not freeform text -- tool
                # arguments are always syntactically valid JSON by construction, which rules
                # out the stray-bracket class of bug a freeform "respond with JSON" prompt
                # shipped once (see AI_USAGE.md). That alone isn't a full guarantee though:
                # the schema's `required` fields are a strong hint to the model, not something
                # the API enforces, so a submission can still come back incomplete, or -- seen
                # once in production -- with another field's content leaked as escaped text
                # inside a string. Both are checked below and, if invalid, turned into a
                # tool_result error so the model gets a chance to resubmit instead of a bad
                # report reaching the user silently.
                report_call = next((c for c in tool_uses if c.name == "submit_report"), None)
                report_error: str | None = None
                if report_call:
                    try:
                        validated = _validate_report(report_call.input)
                    except (ValidationError, ValueError) as exc:
                        report_error = str(exc)
                    else:
                        trace.final_json = validated.model_dump()
                        trace.final_text = json.dumps(trace.final_json, indent=2)
                        break

                if not tool_uses:
                    trace.final_text = "\n".join(text_blocks)
                    trace.final_json = _parse_final_json(trace.final_text)
                    break

                tool_results = []
                for call in tool_uses:
                    if call.name == "submit_report":
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": call.id,
                                "content": f"Report rejected, fix and resubmit: {report_error}",
                                "is_error": True,
                            }
                        )
                        continue
                    result = await asyncio.wait_for(
                        session.call_tool(call.name, arguments=call.input), timeout=30.0
                    )
                    parsed = _extract_tool_result(result)
                    record = ToolCallRecord(name=call.name, arguments=call.input, result=parsed)
                    trace.turns.append(record)
                    if call.name == "get_recall" and isinstance(parsed, dict) and parsed.get("found"):
                        trace.case_snapshot = parsed.get("recall")
                    if on_tool_call:
                        on_tool_call(record)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": json.dumps(parsed) if not isinstance(parsed, str) else parsed,
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
            else:
                trace.final_text = "(max turns reached without a final verdict)"

    return trace


def run_investigation_sync(query: dict, model: str = DEFAULT_MODEL, on_tool_call=None) -> InvestigationTrace:
    return asyncio.run(run_investigation(query, model=model, on_tool_call=on_tool_call))
