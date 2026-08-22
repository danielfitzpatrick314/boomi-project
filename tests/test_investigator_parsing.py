"""Unit tests for the agent's final-JSON parsing -- no live API or model call.

The parser needs to be forgiving because the model occasionally deviates from
"bare JSON, no comments" despite explicit instructions (a real bug this repo
shipped once: the system prompt's own schema example contained `//` comments,
which risked the model echoing that pattern into its actual output and
silently dropping the result -- see AI_USAGE.md)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from agent.investigator import _parse_final_json, _validate_report  # noqa: E402

VALID = '{"verdict": "isolated", "recall_number": "D-1"}'

GOOD_REPORT = {
    "recall_number": "D-1",
    "verdict": "isolated",
    "recommended_action": "No action needed.",
    "summary": "A clean, well-formed summary.",
    "evidence": ["Recall D-1 initiated 2024-01-01."],
    "related_products": [],
    "open_questions": [],
}


def test_parses_bare_json():
    assert _parse_final_json(VALID) == {"verdict": "isolated", "recall_number": "D-1"}


def test_strips_markdown_fence():
    assert _parse_final_json(f"```json\n{VALID}\n```") == {"verdict": "isolated", "recall_number": "D-1"}


def test_strips_stray_line_comments():
    text = '{\n  "verdict": "isolated",\n  // a stray comment the model shouldn\'t emit but might\n  "recall_number": "D-1"\n}'
    assert _parse_final_json(text) == {"verdict": "isolated", "recall_number": "D-1"}


def test_extracts_json_from_surrounding_prose():
    text = f"Here is my final answer:\n{VALID}\nLet me know if you need more."
    assert _parse_final_json(text) == {"verdict": "isolated", "recall_number": "D-1"}


def test_returns_none_for_genuinely_broken_output():
    assert _parse_final_json("I couldn't find a recall for that.") is None


# -- submit_report validation --------------------------------------------------------
# The tool schema's `required` fields are a strong hint to the model, not something
# the Anthropic API enforces server-side -- a submission can come back missing a
# field, or (observed once in production) with one field's content leaked as escaped
# text inside another field, e.g. a stray `</summary><parameter name="evidence">`
# fragment. _validate_report exists to catch both before they reach a user.


def test_validate_report_accepts_well_formed_report():
    result = _validate_report(GOOD_REPORT)
    assert result.recall_number == "D-1"


def test_validate_report_rejects_missing_required_field():
    bad = {k: v for k, v in GOOD_REPORT.items() if k != "evidence"}
    with pytest.raises(ValidationError):
        _validate_report(bad)


def test_validate_report_rejects_leaked_tag_in_summary():
    bad = dict(GOOD_REPORT, summary='Some text</summary>\n<parameter name="evidence">leaked')
    with pytest.raises(ValueError, match="leaked tag"):
        _validate_report(bad)


def test_validate_report_rejects_leaked_tag_in_evidence_item():
    bad = dict(GOOD_REPORT, evidence=["A fine finding.", "Another one</evidence> stray"])
    with pytest.raises(ValueError, match="leaked tag"):
        _validate_report(bad)
