import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fda_mcp.resolver import extract_ndc, extract_product_name, fuzzy_match_firm  # noqa: E402


def test_extract_ndc_basic():
    text = "Levothyroxine 100-count bottles, NDC 69367-156-04."
    assert extract_ndc(text) == "69367-156"


def test_extract_ndc_no_ndc_present():
    text = "SkinGuard 24 All-Day Hand Sanitizer 8 oz. bottle with foam pump, UPC 793573147125"
    assert extract_ndc(text) is None


def test_extract_ndc_alternate_prefix_spacing():
    text = "Some Product, NDC:12345-678-9, distributed nationwide"
    assert extract_ndc(text) == "12345-678"


def test_fuzzy_match_firm_same_entity_different_suffix():
    match = fuzzy_match_firm("Westminster Pharmaceuticals LLC", "Westminster Pharmaceuticals, LLC")
    assert match.confidence == "high"


def test_fuzzy_match_firm_unrelated_names():
    match = fuzzy_match_firm("Pfizer Inc.", "Nanomaterials Discovery Corporation")
    assert match.confidence == "low"


def test_fuzzy_match_firm_suffix_noise_ignored():
    match = fuzzy_match_firm("Acme Pharma Corp", "ACME PHARMA")
    assert match.score >= 90


def test_extract_product_name_simple_comma():
    text = "Azelaic Acid Gel, 15%, 50 gram tubes, For Topical Use only, Rx only"
    assert extract_product_name(text) == "Azelaic Acid Gel"


def test_extract_product_name_paren_with_internal_comma():
    text = "Levothyroxine and Liothyronine (Thyroid Tablets, USP), 1 grain (60 mg), 100-count bottles"
    assert extract_product_name(text) == "Levothyroxine and Liothyronine (Thyroid Tablets, USP)"


def test_extract_product_name_no_comma():
    text = "SkinGuard 24 All-Day Hand Sanitizer"
    assert extract_product_name(text) == text
