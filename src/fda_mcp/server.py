"""MCP server exposing openFDA drug-recall investigation tools.

Run standalone for debugging: `python -m fda_mcp.server`
The investigator agent (src/agent/investigator.py) spawns this over stdio.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .openfda_client import OpenFDAClient
from .resolver import find_related_adverse_events as link_adverse_events
from .resolver import find_related_products as link_related_products
from .resolver import fuzzy_match_firm

mcp = MCPServer("fda-recall-investigator")
_client = OpenFDAClient()


def _recall_summary(r: dict) -> dict:
    return {
        "recall_number": r.get("recall_number"),
        "status": r.get("status"),
        "classification": r.get("classification"),
        "recalling_firm": r.get("recalling_firm"),
        "product_description": r.get("product_description"),
        "reason_for_recall": r.get("reason_for_recall"),
        "recall_initiation_date": r.get("recall_initiation_date"),
        "voluntary_mandated": r.get("voluntary_mandated"),
        "distribution_pattern": r.get("distribution_pattern"),
    }


@mcp.tool()
def get_recall(recall_number: str) -> dict:
    """Fetch the full detail record for one drug recall by its recall_number (e.g. 'D-1178-2018')."""
    recall = _client.get_recall(recall_number)
    if not recall:
        return {"found": False, "recall_number": recall_number}
    return {"found": True, "recall": recall}


@mcp.tool()
def search_recalls(
    firm: str | None = None,
    product: str | None = None,
    classification: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> dict:
    """Search drug recalls (enforcement actions).

    firm: recalling firm name (phrase match, e.g. 'Pfizer Inc.')
    product: text to match against the product description
    classification: 'Class I' | 'Class II' | 'Class III'
    date_from, date_to: YYYYMMDD, both required together, filters recall_initiation_date
    """
    result = _client.search_recalls(
        firm=firm, product=product, classification=classification,
        date_from=date_from, date_to=date_to, limit=limit,
    )
    return {"total": result.total, "recalls": [_recall_summary(r) for r in result.results]}


@mcp.tool()
def search_recalls_by_firm(firm_name: str, limit: int = 20) -> dict:
    """Get a firm's recall history, oldest first -- use this to check whether a recall is
    a one-off or part of a pattern for that manufacturer. `total` reflects the firm's real
    full count even when it exceeds `limit`; the returned list is capped to keep response
    size reasonable for firms with very large histories -- 20 real examples is plenty to
    judge a pattern from, and it's the count and root-cause repetition that matter, not
    seeing every single record."""
    result = _client.search_recalls_by_firm(firm_name, limit=limit)
    return {"total": result.total, "recalls": [_recall_summary(r) for r in result.results]}


@mcp.tool()
def find_related_adverse_events(recall_number: str, limit: int = 5) -> dict:
    """Find adverse-event reports plausibly linked to a specific recall.

    Tries, in order of trustworthiness: the product's NDC (extracted from the
    recall text), then generic name, then brand name, then manufacturer name
    as a last resort. Returns which method matched, a confidence level, and
    a caveat explaining that method's limitations -- manufacturer-name
    matches in particular are known to overcount badly on this dataset and
    should be treated as weak signal, not proof.
    """
    recall = _client.get_recall(recall_number)
    if not recall:
        return {"found": False, "recall_number": recall_number}
    linked = link_adverse_events(_client, recall)
    return {
        "found": True,
        "recall_number": recall_number,
        "method": linked.method,
        "confidence": linked.confidence,
        "caveat": linked.caveat,
        "query_value": linked.query_value,
        "total_events": linked.total,
        "sample_events": [
            {
                "receivedate": e.get("receivedate"),
                "serious": e.get("serious"),
                "reactions": [x.get("reactionmeddrapt") for x in e.get("patient", {}).get("reaction", [])],
            }
            for e in linked.sample
        ],
    }


@mcp.tool()
def search_adverse_events(
    generic_name: str | None = None,
    brand_name: str | None = None,
    manufacturer_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> dict:
    """Directly search FAERS adverse-event reports by product name and/or manufacturer,
    optionally windowed by receivedate (YYYYMMDD). Use this for open-ended exploration
    when find_related_adverse_events isn't specific enough (e.g. checking a date window
    before vs. after a recall). manufacturer_name-only queries are unreliable on this
    dataset -- prefer generic_name or brand_name when you have them."""
    result = _client.search_events(
        generic_name=generic_name, brand_name=brand_name, manufacturer_name=manufacturer_name,
        date_from=date_from, date_to=date_to, limit=limit,
    )
    return {
        "total": result.total,
        "events": [
            {
                "receivedate": e.get("receivedate"),
                "serious": e.get("serious"),
                "companynumb": e.get("companynumb"),
                "reactions": [x.get("reactionmeddrapt") for x in e.get("patient", {}).get("reaction", [])],
            }
            for e in result.results
        ],
    }


def _product_list(products: list) -> list[dict]:
    return [
        {
            "name": p.brand_name or p.generic_name,
            "generic_name": p.generic_name,
            "manufacturer": p.manufacturer,
            "dosage_form": p.dosage_form,
        }
        for p in products
    ]


@mcp.tool()
def find_related_products(recall_number: str, limit: int = 6) -> dict:
    """Find other currently-marketed drugs worth flagging because of this recall:
    other products from the same manufacturer (shared facility/QC risk), and other
    products from ANY manufacturer that share the recalled product's active
    ingredient (shared raw-material supply chain, or a class-wide issue). This is
    the tool for surfacing downstream risk beyond the one recalled item -- use it
    on every investigation, not just as an afterthought.

    Coverage is incomplete: this is based on the FDA's *current* NDC directory,
    which only lists actively-marketed products. Older, discontinued, or some
    OTC-monograph products won't appear even though they're real. An empty result
    means "not found in this directory," not "nothing else is at risk."
    """
    recall = _client.get_recall(recall_number)
    if not recall:
        return {"found": False, "recall_number": recall_number}
    related = link_related_products(_client, recall, limit=limit)
    return {
        "found": True,
        "recall_number": recall_number,
        "recalled_product_resolved": related.own_product is not None,
        "ingredient_used_for_cross_reference": related.ingredient_used,
        "same_manufacturer": _product_list(related.same_manufacturer),
        "same_ingredient": _product_list(related.same_ingredient),
        "caveat": related.caveat,
    }


@mcp.tool()
def resolve_firm_name_match(name_a: str, name_b: str) -> dict:
    """Score whether two manufacturer/firm name strings likely refer to the same
    legal entity (handles LLC/Inc/Corp suffix noise and word order, not subsidiaries
    or DBAs). Use when you need to decide if two differently-formatted firm names
    from different endpoints are the same company."""
    match = fuzzy_match_firm(name_a, name_b)
    return {
        "name_a": match.query,
        "name_b": match.candidate,
        "similarity_score": match.score,
        "confidence": match.confidence,
    }


if __name__ == "__main__":
    mcp.run()
