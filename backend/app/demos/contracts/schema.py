from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ClauseKind(str, Enum):
    """Declaration order is display order."""

    termination = "termination"
    renewal = "renewal"
    payment = "payment"
    liability = "liability"
    indemnity = "indemnity"
    confidentiality = "confidentiality"
    intellectual_property = "intellectual_property"
    governing_law = "governing_law"
    dispute_resolution = "dispute_resolution"
    non_compete = "non_compete"
    other = "other"


Severity = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    page: int
    quote: str = Field(min_length=1)
    # Never trusted from the model: verify_evidence sets it.
    verified: bool = False


class Party(BaseModel):
    name: str
    role: str


class KeyTerm(BaseModel):
    label: str
    value: str
    evidence: Evidence


class Clause(BaseModel):
    kind: ClauseKind
    title: str
    plain_english: str
    evidence: Evidence


class Risk(BaseModel):
    severity: Severity
    title: str
    explanation: str
    evidence: Evidence


class ContractReview(BaseModel):
    summary: str
    contract_type: str
    parties: list[Party]
    key_terms: list[KeyTerm]
    clauses: list[Clause]
    risks: list[Risk]
