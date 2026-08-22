from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Verdict = Literal["isolated", "watch", "systemic", "insufficient_data"]
RelatedProductRelation = Literal["same_manufacturer", "same_ingredient"]


class RelatedProduct(BaseModel):
    name: str
    manufacturer: str
    relation: RelatedProductRelation
    reason: str


class InvestigationResult(BaseModel):
    recall_number: str
    verdict: Verdict
    recommended_action: str
    summary: str
    evidence: list[str]
    related_products: list[RelatedProduct]
    open_questions: list[str]
