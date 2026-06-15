from __future__ import annotations

import re

from app.models import ContextPackage, EvaluationResult, QuestionSpec


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _contains(text: str, fragment: str) -> bool:
    return _normalize(fragment) in _normalize(text)


def evaluate_answer(
    question: QuestionSpec, answer: str, context_package: ContextPackage
) -> EvaluationResult:
    normalized_answer = _normalize(answer)
    expected = question.expected_answer
    scoring = question.scoring

    entity_match = _contains(normalized_answer, expected.entity)
    entity_score = 40 if entity_match else 0

    matched_required = [
        term for term in scoring.required_terms if _contains(normalized_answer, term)
    ]
    matched_bonus = [
        term for term in scoring.bonus_terms if _contains(normalized_answer, term)
    ]
    hallucinated_terms = [
        term for term in scoring.hallucination_terms if _contains(normalized_answer, term)
    ]

    evidence_score = 0
    if scoring.required_terms:
        evidence_score = round(30 * len(matched_required) / len(scoring.required_terms))

    adherence_ratio = 0.0
    total_alignment_terms = len(scoring.required_terms) + len(scoring.bonus_terms)
    if total_alignment_terms:
        adherence_ratio = (len(matched_required) + len(matched_bonus)) / total_alignment_terms

    adherence_score = round(min(1.0, adherence_ratio) * 20)
    if entity_match:
        adherence_score += 10

    hallucination_penalty = min(15, 5 * len(hallucinated_terms))
    quality_score = max(0, min(100, entity_score + evidence_score + adherence_score - hallucination_penalty))

    notes: list[str] = []
    if entity_match:
        notes.append("A resposta identificou a entidade esperada.")
    else:
        notes.append("A resposta não apontou a entidade esperada com clareza.")

    if matched_required:
        notes.append(
            f"Termos centrais encontrados: {', '.join(matched_required[:4])}."
        )
    else:
        notes.append("As evidências-chave do gabarito não apareceram na resposta.")

    if hallucinated_terms:
        notes.append(
            f"Possível alucinação ou desvio detectado em: {', '.join(hallucinated_terms)}."
        )

    if context_package.strategy.value == "none" and "falt" in normalized_answer:
        notes.append("A resposta reconheceu a ausência de contexto, o que reduz risco de invenção.")

    verdict = "supports_h1" if quality_score >= 70 else "weak_or_noisy"

    return EvaluationResult(
        quality_score=quality_score,
        adherence_score=adherence_score,
        evidence_score=evidence_score,
        hallucination_penalty=hallucination_penalty,
        hallucinated_terms=hallucinated_terms,
        matched_required_terms=matched_required,
        matched_bonus_terms=matched_bonus,
        verdict=verdict,
        notes=notes,
    )

