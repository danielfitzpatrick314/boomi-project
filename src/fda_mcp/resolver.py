"""Links a drug recall to adverse-event data.

The naive approach -- join on manufacturer name -- doesn't work on this
dataset: openFDA's `openfda.manufacturer_name` field on adverse-event
records reflects every manufacturer ever associated with the matched
NDC/ingredient, not the company that actually filed the report. Searching
FAERS for a single small firm's exact manufacturer name returned 1.68
million of ~2.2 million total records in testing -- effectively noise.

So this resolver tries, in order of how much we trust the result:

1. NDC (extracted from the recall's free-text `product_description`) --
   most precise, but the recall's product_description doesn't always
   contain one, and even when it does the exact package NDC often has no
   adverse-event history (recalls skew toward small/older lots that
   pre-date or never generated FAERS reports).
2. generic_name / brand_name from the recall's `openfda` block, when
   openFDA bothered to populate it (it's frequently `{}` -- another real
   gap, not a bug in this code).
3. manufacturer_name -- last resort, explicitly flagged low-confidence
   because of the overcounting above. Anything returned via this path
   should be treated as a weak signal, not evidence.

Each method returns a `confidence` and `caveat` alongside the data so the
agent (and a human reading the trace) can see *why* a number should or
shouldn't be trusted, instead of a bare count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .openfda_client import OpenFDAClient, SearchResult

NDC_RE = re.compile(r"NDC\s*[:#]?\s*(\d{4,5}-\d{3,4}(?:-\d{1,2})?)", re.IGNORECASE)


def extract_ndc(product_description: str) -> str | None:
    """Pull an NDC from recall free text and return the labeler-product (base) segment.

    NDCs in FAERS are indexed at the base (labeler-product) level, not the
    full package NDC, so a recall's "69367-156-04" becomes "69367-156".
    """
    match = NDC_RE.search(product_description or "")
    if not match:
        return None
    segments = match.group(1).split("-")
    if len(segments) < 2:
        return None
    return "-".join(segments[:2])


@dataclass
class LinkedEvents:
    method: str
    confidence: str  # "high" | "medium" | "low" | "none"
    caveat: str
    query_value: str | None
    total: int
    sample: list[dict] = field(default_factory=list)


def find_related_adverse_events(client: OpenFDAClient, recall: dict, limit: int = 5) -> LinkedEvents:
    openfda = recall.get("openfda") or {}
    description = recall.get("product_description", "")

    ndc = extract_ndc(description)
    if ndc:
        result = client.search_events_by_ndc(ndc, limit=limit)
        if result.total > 0:
            return LinkedEvents(
                method="product_ndc",
                confidence="high",
                caveat="Matched on the specific product NDC extracted from the recall text -- the strongest link available.",
                query_value=ndc,
                total=result.total,
                sample=result.results,
            )

    generic_names = openfda.get("generic_name") or []
    for name in generic_names:
        result = client.search_events_by_generic_name(name, limit=limit)
        if result.total > 0:
            return LinkedEvents(
                method="generic_name",
                confidence="medium",
                caveat="Matched on generic drug name, not the specific manufacturer or lot -- events may involve a different maker's version of the same drug.",
                query_value=name,
                total=result.total,
                sample=result.results,
            )

    brand_names = openfda.get("brand_name") or []
    for name in brand_names:
        result = client.search_events_by_brand_name(name, limit=limit)
        if result.total > 0:
            return LinkedEvents(
                method="brand_name",
                confidence="medium",
                caveat="Matched on brand name, not the specific manufacturer or lot -- events may involve a different maker's version of the same product.",
                query_value=name,
                total=result.total,
                sample=result.results,
            )

    firm = recall.get("recalling_firm")
    if firm:
        result = client.search_events_by_manufacturer(firm, limit=limit)
        query_value = firm
        if result.total == 0:
            # .exact matching on this field is punctuation-sensitive across endpoints --
            # "Westminster Pharmaceuticals LLC" (enforcement) vs. "Westminster Pharmaceuticals,
            # LLC" (FAERS) do not match despite being the same entity. One cheap retry with a
            # comma inserted before the corporate suffix catches this specific, observed case;
            # it will not catch every punctuation variant.
            with_comma = _insert_comma_before_suffix(firm)
            if with_comma != firm:
                retry = client.search_events_by_manufacturer(with_comma, limit=limit)
                if retry.total > 0:
                    result, query_value = retry, with_comma
        return LinkedEvents(
            method="manufacturer_name",
            confidence="low",
            caveat=(
                "No NDC or product name match was available, so this falls back to manufacturer name. "
                "openFDA's manufacturer_name field on adverse-event records is known to overcount -- it "
                "associates every manufacturer ever linked to an ingredient/NDC with the event, not just "
                "the reporting company. Treat this count as a weak, likely-inflated signal, not evidence. "
                "It is also punctuation-sensitive (exact match only), so a genuine 0 here can mean 'no "
                "events' or just 'punctuation mismatch' -- not fully disambiguated."
            ),
            query_value=query_value,
            total=result.total,
            sample=result.results,
        )

    return LinkedEvents(
        method="none",
        confidence="none",
        caveat="No NDC, product name, or firm name was usable for linkage.",
        query_value=None,
        total=0,
        sample=[],
    )


@dataclass
class FirmMatch:
    query: str
    candidate: str
    score: float
    confidence: str  # "high" | "medium" | "low"


def fuzzy_match_firm(query: str, candidate: str) -> FirmMatch:
    """Score how likely two firm-name strings refer to the same legal entity.

    Handles the common cases in this data: suffix noise (LLC/Inc/Corp),
    punctuation, and word-order variance -- not true entity resolution
    (subsidiaries, DBAs, and acquisitions will still fool this).
    """
    score = fuzz.token_sort_ratio(_normalize_firm(query), _normalize_firm(candidate))
    if score >= 90:
        confidence = "high"
    elif score >= 75:
        confidence = "medium"
    else:
        confidence = "low"
    return FirmMatch(query=query, candidate=candidate, score=score, confidence=confidence)


_FIRM_SUFFIXES = re.compile(
    r"\b(llc|inc|incorporated|corp|corporation|ltd|limited|co|company|dba)\b\.?", re.IGNORECASE
)


def _insert_comma_before_suffix(name: str) -> str:
    match = _FIRM_SUFFIXES.search(name or "")
    if not match or name[: match.start()].rstrip().endswith(","):
        return name
    prefix = name[: match.start()].rstrip()
    return f"{prefix}, {name[match.start():]}"


def _normalize_firm(name: str) -> str:
    name = _FIRM_SUFFIXES.sub("", name or "")
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()


def extract_product_name(description: str) -> str:
    """Pull a human-readable drug name from a recall's free-text product_description.

    openFDA's structured `openfda.brand_name`/`generic_name` fields are frequently
    empty on enforcement records (see module docstring), so recall listings need a
    text fallback or they show nothing but firm name and legalese. Descriptions are
    consistently "<drug name>, <packaging/dosage detail...>", except the drug name
    itself sometimes contains a parenthetical that also contains a comma (e.g.
    "Levothyroxine and Liothyronine (Thyroid Tablets, USP), 1 grain..."), so a naive
    split on the first comma would cut mid-parenthesis. This splits on the first
    comma that isn't inside parens instead.
    """
    if not description:
        return ""
    depth = 0
    for i, ch in enumerate(description):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            return description[:i].strip()
    return description.strip()


@dataclass
class RelatedProduct:
    generic_name: str | None
    brand_name: str | None
    manufacturer: str | None
    dosage_form: str | None


@dataclass
class RelatedProductsResult:
    own_product: dict | None  # clean {generic_name, brand_name, manufacturer, active_ingredients} if resolved
    same_manufacturer: list[RelatedProduct]
    same_ingredient: list[RelatedProduct]
    ingredient_used: str | None
    caveat: str


def _dedupe_products(results: list[dict], exclude_manufacturer: str | None, limit: int) -> list[RelatedProduct]:
    seen: set[str] = set()
    out: list[RelatedProduct] = []
    for r in results:
        name = (r.get("generic_name") or r.get("brand_name") or "").strip()
        manufacturer = r.get("labeler_name")
        if not name:
            continue
        if exclude_manufacturer and manufacturer and _normalize_firm(manufacturer) == _normalize_firm(exclude_manufacturer):
            continue
        key = f"{name.lower()}|{(manufacturer or '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            RelatedProduct(
                generic_name=r.get("generic_name"),
                brand_name=r.get("brand_name"),
                manufacturer=manufacturer,
                dosage_form=r.get("dosage_form"),
            )
        )
        if len(out) >= limit:
            break
    return out


def find_related_products(client: OpenFDAClient, recall: dict, limit: int = 6) -> RelatedProductsResult:
    """The point of this tool: a recall on one product is a signal about the
    manufacturer and the ingredient, not just that one NDC. Surfaces other
    currently-marketed products worth a second look -- same manufacturer
    (shared facility/QC risk) and same active ingredient (shared supply chain
    or a class-wide issue), each with its own caveat about NDC-directory
    coverage gaps.
    """
    firm = recall.get("recalling_firm")
    description = recall.get("product_description", "")
    ndc = extract_ndc(description)

    own_product = None
    ingredient: str | None = None

    if ndc:
        own_product = client.get_ndc_product(ndc)
        if own_product:
            ingredients = own_product.get("active_ingredients") or []
            if ingredients:
                ingredient = ingredients[0].get("name")

    if not ingredient:
        # Fallback: NDC lookup failed (common for older/delisted or OTC-monograph
        # products) -- guess a searchable name from the free text instead. This is
        # weaker (a phrase match on a guessed name, not a confirmed ingredient) and
        # callers should treat what it finds as lower-confidence. Strip a trailing
        # parenthetical (usually a dosage-form descriptor, e.g. "(Thyroid Tablets,
        # USP)") since the NDC directory's generic_name field won't include it.
        guess = extract_product_name(description)
        guess = re.sub(r"\s*\([^)]*\)\s*$", "", guess).strip()
        if guess:
            ingredient = guess

    own_generic = (own_product.get("generic_name") or "").strip().lower() if own_product else None

    same_manufacturer: list[RelatedProduct] = []
    if firm:
        mfr_result = client.search_ndc_by_manufacturer(firm, limit=40)
        candidates = mfr_result.results
        if own_generic:
            # drop the recalled product itself -- this list is for *other* products
            candidates = [r for r in candidates if (r.get("generic_name") or "").strip().lower() != own_generic]
        same_manufacturer = _dedupe_products(candidates, exclude_manufacturer=None, limit=limit)

    same_ingredient: list[RelatedProduct] = []
    ingredient_confidence_note = ""
    if ingredient:
        if own_product:
            ing_result = client.search_ndc_by_active_ingredient(ingredient, limit=40)
        else:
            ing_result = client.search_ndc_by_generic_name(ingredient, limit=40)
            ingredient_confidence_note = (
                f" (matched by guessing '{ingredient}' from the recall text, not a confirmed active "
                "ingredient -- the recalled product's own NDC record wasn't found)"
            )
        same_ingredient = _dedupe_products(ing_result.results, exclude_manufacturer=firm, limit=limit)

    caveat = (
        "Based on the FDA's current NDC directory, which only lists actively-marketed products -- "
        "older, discontinued, or OTC-monograph products (common among older recalls) are often "
        "missing entirely, so an empty or short list here does not mean nothing else is at risk, "
        "only that nothing else showed up in this directory. Also, 'same manufacturer' here means "
        "same NDC labeler (the marketing/distribution company on file), which is not always the "
        "same as the physical manufacturing site -- a contract manufacturer's facility issue could "
        "affect other labelers' products that this search would not surface." + ingredient_confidence_note
    )

    return RelatedProductsResult(
        own_product=own_product,
        same_manufacturer=same_manufacturer,
        same_ingredient=same_ingredient,
        ingredient_used=ingredient,
        caveat=caveat,
    )
