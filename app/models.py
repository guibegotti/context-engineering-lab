from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AppBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class ModelChoice(str, Enum):
    medium = "medium"
    strong = "strong"


class ContextStrategy(str, Enum):
    none = "none"
    minimum = "minimum"
    relevant = "relevant"
    abundant = "abundant"


class SupportingEvidence(AppBaseModel):
    doc: str
    detail: str


class ExpectedAnswer(AppBaseModel):
    entity: str
    answer: str
    rationale: str
    evidence: list[SupportingEvidence]


class ScoringSpec(AppBaseModel):
    required_terms: list[str] = Field(default_factory=list)
    bonus_terms: list[str] = Field(default_factory=list)
    hallucination_terms: list[str] = Field(default_factory=list)
    candidate_terms: dict[str, list[str]] = Field(default_factory=dict)


class QuestionSpec(AppBaseModel):
    id: str
    title: str
    question: str
    relevant_documents: list[str]
    expected_answer: ExpectedAnswer
    scoring: ScoringSpec


class ContextDocument(AppBaseModel):
    name: str
    content: str


class ContextPackage(AppBaseModel):
    strategy: ContextStrategy
    question_id: str
    documents: list[ContextDocument]
    prompt: str
    document_names: list[str]
    token_estimate: int


class UsageMetrics(AppBaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    provider: str
    model_name: str


class LLMResult(AppBaseModel):
    answer: str
    usage: UsageMetrics


class EvaluationResult(AppBaseModel):
    quality_score: int
    adherence_score: int
    evidence_score: int
    hallucination_penalty: int
    hallucinated_terms: list[str]
    matched_required_terms: list[str]
    matched_bonus_terms: list[str]
    verdict: str
    notes: list[str]


class ExperimentRequest(AppBaseModel):
    question_id: str
    model_choice: ModelChoice
    strategy: ContextStrategy


class ExperimentResponse(AppBaseModel):
    run_id: str
    created_at: datetime
    question_id: str
    question: str
    model_choice: ModelChoice
    strategy: ContextStrategy
    answer: str
    context_documents: list[str]
    context_preview: str
    usage: UsageMetrics
    evaluation: EvaluationResult
    expected_entity: str
    mode: str


class RecentResult(AppBaseModel):
    run_id: str
    created_at: datetime
    question_id: str
    model_choice: str
    strategy: str
    quality_score: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    provider: str
