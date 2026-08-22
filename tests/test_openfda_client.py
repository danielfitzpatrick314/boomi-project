"""Integration tests against the live openFDA API (no key required, but needs
network). Skipped automatically if the network is unreachable so `pytest` still
works offline for the resolver unit tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fda_mcp.openfda_client import OpenFDAClient  # noqa: E402
from fda_mcp.resolver import find_related_adverse_events, find_related_products  # noqa: E402


@pytest.fixture(scope="module")
def client():
    c = OpenFDAClient()
    try:
        c.search_recalls(limit=1)
    except Exception:
        pytest.skip("openFDA unreachable from this environment")
    yield c
    c.close()


def test_get_known_recall(client):
    recall = client.get_recall("D-1178-2018")
    assert recall is not None
    assert recall["recalling_firm"] == "Westminster Pharmaceuticals LLC"
    assert recall["classification"] == "Class I"


def test_get_unknown_recall_returns_none(client):
    assert client.get_recall("D-NOT-A-REAL-RECALL-9999") is None


def test_search_recalls_by_firm_history(client):
    result = client.search_recalls_by_firm("Westminster Pharmaceuticals")
    assert result.total == 10


def test_search_recalls_by_firm_single_recall_firm(client):
    result = client.search_recalls_by_firm("Nanomaterials Discovery Corporation")
    assert result.total == 1


def test_search_events_by_manufacturer_overcounts(client):
    """Documents the data-quality issue resolver.py works around: manufacturer-name
    matching on FAERS massively overcounts. This test pins that behavior so a future
    change to resolver.py's fallback ordering is a deliberate choice, not a regression
    nobody noticed."""
    result = client.search_events_by_manufacturer("Westminster Pharmaceuticals, LLC", limit=1)
    assert result.total > 500_000  # a firm with 10 recalls should not have this many "matches"


def test_search_events_by_brand_name_is_sane(client):
    result = client.search_events_by_brand_name("LYRICA", limit=1)
    assert 0 < result.total < 1_000_000


def test_find_related_adverse_events_no_ndc_hit_falls_back_correctly(client):
    """D-1178-2018's NDC (69367-156) has no FAERS hits, and its openfda block is empty
    (no generic/brand name to try), so this should fall all the way to the punctuation-
    corrected manufacturer_name fallback rather than silently reporting zero."""
    recall = client.get_recall("D-1178-2018")
    linked = find_related_adverse_events(client, recall)
    assert linked.method == "manufacturer_name"
    assert linked.confidence == "low"
    assert linked.total > 0
    assert "overcount" in linked.caveat


def test_find_related_products_same_manufacturer(client):
    """Westminster has ~180 other NDC-listed products -- this is the 'other drugs
    from the same manufacturer' signal the related-products feature is built on."""
    recall = client.get_recall("D-1178-2018")
    related = find_related_products(client, recall, limit=6)
    assert len(related.same_manufacturer) > 0
    assert all(p.generic_name != "Levothyroxine and Liothyronine" for p in related.same_manufacturer)


def test_find_related_products_same_ingredient_cross_manufacturer(client):
    """The recalled product's own 2018 NDC has since expired out of the directory
    (own_product is None), so this exercises the free-text fallback path -- it
    should still surface other manufacturers making the same drug combination."""
    recall = client.get_recall("D-1178-2018")
    related = find_related_products(client, recall, limit=6)
    assert related.own_product is None
    assert len(related.same_ingredient) > 0
    manufacturers = {p.manufacturer for p in related.same_ingredient}
    assert "Westminster Pharmaceuticals, LLC" not in manufacturers
