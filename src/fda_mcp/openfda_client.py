"""Thin client over the openFDA drug endpoints.

openFDA quirks this file deliberately works around (learned by querying the
live API while building this, not from the docs):

- Text-field search without `.exact` does per-token matching, not phrase
  matching, on some fields. `patient.drug.openfda.manufacturer_name` (no
  `.exact`) matched 1.68M of ~2.2M adverse event records for a single small
  manufacturer name -- the field is effectively useless unqualified.
- Even `.exact` on `manufacturer_name` overcounts badly: openFDA associates
  *every* manufacturer ever linked to a given NDC/ingredient with the
  event record, not just the reporting company. A generic drug name can
  fan out to 1M+ "matches" per manufacturer. See resolver.py for how this
  is handled -- manufacturer-based adverse-event linkage is treated as a
  low-confidence fallback, not a primary signal.
- Date range queries need the field in bracket-range Lucene syntax:
  `field:[YYYYMMDD TO YYYYMMDD]`, unencoded when built and URL-encoded by
  requests/httpx -- building it with raw string interpolation and letting
  the HTTP client encode it is more reliable than hand-encoding brackets.
- A search with zero hits returns HTTP 404 with an error body, not an empty
  200. This file normalizes that to an empty list so "no results" is data,
  not an exception.
- `skip` + `limit` cap out at 1000 combined per openFDA's pagination limit;
  this client does not auto-paginate past that today (see README "cut").
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

import httpx

BASE_URL = "https://api.fda.gov"
DRUG_ENFORCEMENT = f"{BASE_URL}/drug/enforcement.json"
DRUG_EVENT = f"{BASE_URL}/drug/event.json"
DRUG_NDC = f"{BASE_URL}/drug/ndc.json"

MAX_LIMIT = 100  # per-request cap this client will ask for; openFDA allows up to 1000


class OpenFDAError(RuntimeError):
    pass


@dataclass
class SearchResult:
    total: int
    results: list[dict]


def _quote(value: str) -> str:
    """Quote a value for a Lucene phrase match, escaping embedded quotes."""
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


class OpenFDAClient:
    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        self.api_key = api_key or os.environ.get("FDA_API_KEY")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenFDAClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, url: str, search: str | None, limit: int, skip: int = 0, sort: str | None = None) -> SearchResult:
        params: dict[str, str | int] = {"limit": min(limit, MAX_LIMIT), "skip": skip}
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if self.api_key:
            params["api_key"] = self.api_key

        for attempt in range(3):
            resp = self._client.get(url, params=params)
            if resp.status_code == 404:
                # openFDA's way of saying "zero results", not a real error.
                return SearchResult(total=0, results=[])
            if resp.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code >= 500:
                time.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code != 200:
                raise OpenFDAError(f"openFDA returned {resp.status_code}: {resp.text[:300]}")
            body = resp.json()
            meta = body.get("meta", {}).get("results", {})
            return SearchResult(total=meta.get("total", 0), results=body.get("results", []))

        raise OpenFDAError(f"openFDA request failed after retries: {url} search={search!r}")

    # -- drug enforcement (recalls) -----------------------------------

    def get_recall(self, recall_number: str) -> dict | None:
        search = f"recall_number:{_quote(recall_number)}"
        result = self._get(DRUG_ENFORCEMENT, search, limit=1)
        return result.results[0] if result.results else None

    def search_recalls(
        self,
        firm: str | None = None,
        product: str | None = None,
        classification: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 10,
        sort: str | None = "recall_initiation_date:desc",
    ) -> SearchResult:
        clauses = []
        if firm:
            clauses.append(f"recalling_firm:{_quote(firm)}")
        if product:
            clauses.append(f"product_description:{_quote(product)}")
        if classification:
            clauses.append(f'classification:{_quote(classification)}')
        if date_from and date_to:
            clauses.append(f"recall_initiation_date:[{date_from} TO {date_to}]")
        search = " AND ".join(clauses) if clauses else None
        return self._get(DRUG_ENFORCEMENT, search, limit=limit, sort=sort)

    def search_recalls_by_firm(self, firm_name: str, limit: int = 20) -> SearchResult:
        search = f"recalling_firm:{_quote(firm_name)}"
        return self._get(DRUG_ENFORCEMENT, search, limit=limit, sort="recall_initiation_date:asc")

    def search_recalls_field_wildcard(self, field: str, word: str, limit: int = 50) -> SearchResult:
        """Substring match on a single word within one field, for when an exact
        phrase match on the full value comes back empty -- a misspelling, a
        compound legal name typed as separate words (e.g. "Glaxo Smith Klein"
        vs openFDA's "GlaxoSmithKline"), or a short product name that's really
        just a fragment of the long free-text `product_description` recalls
        actually store. Confirmed against the live API: a bare Lucene wildcard
        like `*glaxo*` matches "GlaxoSmithKline Inc" where a phrase match on
        the full typo'd name returns nothing. `field` is trusted -- callers
        pass a fixed field name, never user input, so it's not sanitized."""
        token = re.sub(r"[^a-zA-Z0-9]", "", word)
        if not token:
            return SearchResult(total=0, results=[])
        return self._get(DRUG_ENFORCEMENT, f"{field}:*{token}*", limit=limit)

    # -- drug adverse events (FAERS) -----------------------------------

    def search_events_by_ndc(self, product_ndc: str, limit: int = 10) -> SearchResult:
        search = f"patient.drug.openfda.product_ndc.exact:{_quote(product_ndc)}"
        return self._get(DRUG_EVENT, search, limit=limit, sort="receivedate:desc")

    def search_events_by_generic_name(self, generic_name: str, limit: int = 10) -> SearchResult:
        search = f"patient.drug.openfda.generic_name.exact:{_quote(generic_name.upper())}"
        return self._get(DRUG_EVENT, search, limit=limit, sort="receivedate:desc")

    def search_events_by_brand_name(self, brand_name: str, limit: int = 10) -> SearchResult:
        search = f"patient.drug.openfda.brand_name.exact:{_quote(brand_name.upper())}"
        return self._get(DRUG_EVENT, search, limit=limit, sort="receivedate:desc")

    def search_events_by_manufacturer(self, manufacturer_name: str, limit: int = 10) -> SearchResult:
        search = f"patient.drug.openfda.manufacturer_name.exact:{_quote(manufacturer_name)}"
        return self._get(DRUG_EVENT, search, limit=limit, sort="receivedate:desc")

    def search_events(
        self,
        generic_name: str | None = None,
        brand_name: str | None = None,
        manufacturer_name: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 10,
    ) -> SearchResult:
        clauses = []
        if generic_name:
            clauses.append(f"patient.drug.openfda.generic_name.exact:{_quote(generic_name.upper())}")
        if brand_name:
            clauses.append(f"patient.drug.openfda.brand_name.exact:{_quote(brand_name.upper())}")
        if manufacturer_name:
            clauses.append(f"patient.drug.openfda.manufacturer_name.exact:{_quote(manufacturer_name)}")
        if date_from and date_to:
            clauses.append(f"receivedate:[{date_from} TO {date_to}]")
        if not clauses:
            raise OpenFDAError("search_events requires at least one filter")
        search = " AND ".join(clauses)
        return self._get(DRUG_EVENT, search, limit=limit, sort="receivedate:desc")

    # -- NDC directory (currently-marketed products) -----------------------
    # Note: this directory reflects *currently marketed* listings only --
    # older or discontinued products (common among older recalls) frequently
    # 404 here even though they're real, historical products. Treat a miss
    # as "not in the current directory," not "doesn't exist."

    def get_ndc_product(self, product_ndc: str) -> dict | None:
        search = f"product_ndc:{_quote(product_ndc)}"
        result = self._get(DRUG_NDC, search, limit=1)
        return result.results[0] if result.results else None

    def search_ndc_by_manufacturer(self, labeler_name: str, limit: int = 20) -> SearchResult:
        search = f"labeler_name:{_quote(labeler_name)}"
        return self._get(DRUG_NDC, search, limit=limit)

    def search_ndc_by_active_ingredient(self, ingredient_name: str, limit: int = 20) -> SearchResult:
        search = f"active_ingredients.name:{_quote(ingredient_name.upper())}"
        return self._get(DRUG_NDC, search, limit=limit)

    def search_ndc_by_generic_name(self, generic_name: str, limit: int = 20) -> SearchResult:
        search = f"generic_name:{_quote(generic_name)}"
        return self._get(DRUG_NDC, search, limit=limit)
