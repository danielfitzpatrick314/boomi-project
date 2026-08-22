"""Ground-truth eval cases.

Each case's expected_verdict was decided by manually researching the recall
and firm history against the live openFDA API *before* running the agent
(queries and raw output are in eval/ground_truth_research.md). This is
deliberately a small set (3) rather than a large auto-generated one --
picking real, individually-verified cases and checking them by hand is worth
more here than a bigger set I didn't personally verify.
"""

CASES = [
    {
        "id": "westminster-systemic",
        "recall_number": "D-1178-2018",
        "expected_verdict": "systemic",
        "acceptable_verdicts": ["systemic", "watch"],
        "why": (
            "Westminster Pharmaceuticals LLC has 10 recalls on file across three separate "
            "episodes (Aug 2018 adulterated-API/content-uniformity, Oct 2018 NDEA impurity, "
            "Aug 2025 nitrosamine impurity) -- a genuine repeat quality-control pattern spanning "
            "7 years, not a single bad batch. NOTE: on first running the eval, the agent called "
            "this 'watch' rather than 'systemic', on the grounds that the three episodes' root "
            "causes differ (content-uniformity vs. two different nitrosamine impurities) rather "
            "than repeating the *same* failure, and only the 2018 same-day quintuplet recall "
            "should count as one incident rather than five. That's a defensible, arguably more "
            "careful reading than this ground truth's looser 'repeated GMP lapses' framing -- "
            "which is why both verdicts are accepted here rather than treating 'watch' as wrong. "
            "See ground_truth_research.md for the full comparison."
        ),
    },
    {
        "id": "nanomaterials-isolated",
        "recall_number": "D-0455-2023",
        "expected_verdict": "isolated",
        "why": (
            "Nanomaterials Discovery Corporation has exactly one recall on file, ever "
            "(chemical contamination of a hand sanitizer). No firm history pattern, and the "
            "product has no NDC/name match in FAERS."
        ),
    },
    {
        "id": "beekeepers-insufficient-data",
        "recall_number": "D-0620-2026",
        "expected_verdict": "insufficient_data",
        "why": (
            "Recall initiated 2026-06-01, ~2.5 months before this eval was written. Firm has "
            "exactly one recall on file (this one), so there's no history to judge a pattern "
            "from, and a recall this recent has not had time to accumulate a meaningful FAERS "
            "adverse-event trail either way -- the honest answer is 'too early to tell', not "
            "'isolated'."
        ),
    },
]
