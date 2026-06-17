from __future__ import annotations

import re

from app.models import ContextPackage, EvaluationResult, NamedTermGroup, QuestionSpec, RubricCheck


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _contains(text: str, fragment: str) -> bool:
    return _normalize(fragment) in _normalize(text)


def _split_segments(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"[\n\r\.\!\?;:]+", text) if segment.strip()]


def _rubric_match_score(answer: str, check: RubricCheck) -> tuple[int, bool]:
    if not check.terms:
        return 0, False

    matched_terms = [term for term in check.terms if _contains(answer, term)]
    match_ratio = len(matched_terms) / len(check.terms)
    score = round(check.weight * match_ratio)
    return score, match_ratio >= 0.5


def _classify_false_leads(
    answer: str, false_leads: list[NamedTermGroup], rejection_markers: list[str]
) -> tuple[list[str], list[str]]:
    accepted: list[str] = []
    rejected: list[str] = []
    segments = _split_segments(answer)
    normalized_markers = [_normalize(marker) for marker in rejection_markers]

    for false_lead in false_leads:
        related_segments = [
            segment
            for segment in segments
            if any(_contains(segment, term) for term in false_lead.terms)
        ]
        if not related_segments:
            continue

        if any(
            any(marker in _normalize(segment) for marker in normalized_markers)
            for segment in related_segments
        ):
            rejected.append(false_lead.label)
        else:
            accepted.append(false_lead.label)

    return accepted, rejected


def evaluate_answer(
    question: QuestionSpec, answer: str, context_package: ContextPackage
) -> EvaluationResult:
    normalized_answer = _normalize(answer)
    expected = question.expected_answer
    scoring = question.scoring

    entity_match = _contains(normalized_answer, expected.entity)
    entity_score = 40 if entity_match else 0
    if scoring.rubric_checks:
        entity_score = 20 if entity_match else 0

    matched_required = [
        term for term in scoring.required_terms if _contains(normalized_answer, term)
    ]
    matched_bonus = [
        term for term in scoring.bonus_terms if _contains(normalized_answer, term)
    ]
    hallucinated_terms = [
        term for term in scoring.hallucination_terms if _contains(normalized_answer, term)
    ]
    accepted_false_leads, rejected_false_leads = _classify_false_leads(
        normalized_answer,
        scoring.false_leads,
        scoring.rejection_markers,
    )
    uncertainty_markers = [
        marker
        for marker in scoring.uncertainty_markers
        if _contains(normalized_answer, marker)
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

    matched_rubric_checks: list[str] = []
    rubric_score = 0
    for check in scoring.rubric_checks:
        check_score, check_matched = _rubric_match_score(normalized_answer, check)
        rubric_score += check_score
        if check_matched:
            matched_rubric_checks.append(check.label)

    evidence_score = min(60, evidence_score + rubric_score)

    if scoring.rubric_checks:
        adherence_score = min(30, adherence_score)
        if uncertainty_markers:
            adherence_score = min(35, adherence_score + 5)
        if rejected_false_leads:
            adherence_score = min(40, adherence_score + min(10, 5 * len(rejected_false_leads)))

    hallucination_penalty = min(
        30,
        (5 * len(hallucinated_terms)) + (5 * len(accepted_false_leads)),
    )
    quality_score = max(
        0,
        min(100, entity_score + evidence_score + adherence_score - hallucination_penalty),
    )

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

    if matched_rubric_checks:
        notes.append(
            f"Critérios adicionais atendidos: {', '.join(matched_rubric_checks[:4])}."
        )

    if hallucinated_terms:
        notes.append(
            f"Possível alucinação ou desvio detectado em: {', '.join(hallucinated_terms)}."
        )

    if rejected_false_leads:
        notes.append(
            f"A resposta rejeitou pistas falsas importantes: {', '.join(rejected_false_leads[:3])}."
        )

    if accepted_false_leads:
        notes.append(
            f"A resposta tratou pistas falsas como verdade: {', '.join(accepted_false_leads[:3])}."
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
        matched_rubric_checks=matched_rubric_checks,
        accepted_false_leads=accepted_false_leads,
        rejected_false_leads=rejected_false_leads,
        verdict=verdict,
        notes=notes,
    )
