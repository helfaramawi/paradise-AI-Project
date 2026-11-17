"""Versioned prompt registry with Pydantic output schemas (structured JSON outputs)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from .guard import SYSTEM_GUARD


class CitedStatement(BaseModel):
    statement: str
    citation_ids: list[str] = Field(default_factory=list)


class EntitlementNarrative(BaseModel):
    summary: str
    why_it_matters: str
    facts: list[CitedStatement]
    assumptions: list[str]
    ambiguities: list[str]
    contradictions: list[str]
    missing_information: list[str]
    recommended_actions: list[str]
    insufficient_evidence: bool


class ContractAnswer(BaseModel):
    answer: str
    citation_ids: list[str]
    insufficient_information: bool
    caveats: list[str]


@dataclass(frozen=True)
class PromptSpec:
    id: str
    version: str
    system: str
    schema: type[BaseModel]
    max_tokens: int = 4000


_BASE = (
    "You are HAQQ, a construction-contracts analyst supporting a contractor's commercial team in Egypt. "
    "You explain; you do not decide. Rules: (1) Use ONLY the supplied excerpts and structured findings. "
    "(2) Every factual statement must cite one or more of the supplied source ids (e.g. C1, D2, E1). Never cite an "
    "id that was not supplied, never invent clause numbers, pages, dates, amounts or deadlines. (3) Separate facts "
    "from assumptions. (4) If the information is insufficient, say so explicitly. (5) Do not state that the "
    "contractor IS entitled or that a claim WILL succeed; use 'may', 'potential', 'subject to'. (6) Do not perform "
    "new financial calculations; refer to the supplied figures only. (7) Answer in the requested language.\n\n"
    + SYSTEM_GUARD
)

PROMPTS: dict[str, PromptSpec] = {
    "entitlement_narrative": PromptSpec(
        id="entitlement_narrative", version="2026-11.1", schema=EntitlementNarrative, max_tokens=6000,
        system=_BASE + "\n\nTask: write an explainable narrative for a POTENTIAL entitlement finding produced by a "
                       "deterministic engine. Identify ambiguous contract wording, potentially applicable exclusions, "
                       "contradictory evidence and missing documents. Remember that absence of evidence is not proof "
                       "that an event did not occur."),
    "contract_qa": PromptSpec(
        id="contract_qa", version="2026-11.1", schema=ContractAnswer, max_tokens=4000,
        system=_BASE + "\n\nTask: answer the user's question about the contract using only the retrieved passages. "
                       "If the passages do not answer the question, set insufficient_information=true."),
}
