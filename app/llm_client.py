from __future__ import annotations

import time
from collections import defaultdict

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from app.config import get_settings
from app.exceptions import ExperimentExecutionError
from app.metrics import estimate_cost_usd
from app.models import ContextPackage, ExecutionMode, LLMResult, ModelChoice, QuestionSpec, UsageMetrics
from app.token_counter import count_tokens


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.settings.api_key:
            self._client = OpenAI(
                api_key=self.settings.api_key,
                base_url=self.settings.base_url,
                default_headers=self._default_headers(),
            )

    def _default_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.app_url:
            headers["HTTP-Referer"] = self.settings.app_url
        if self.settings.app_title:
            headers["X-Title"] = self.settings.app_title
        return headers

    def generate(
        self,
        question: QuestionSpec,
        context_package: ContextPackage,
        model_choice: ModelChoice,
        execution_mode: ExecutionMode = ExecutionMode.sandbox,
    ) -> tuple[LLMResult, str]:
        if execution_mode == ExecutionMode.sandbox:
            return self._simulate(question, context_package, model_choice), "simulated"

        if self._client is None:
            raise ExperimentExecutionError(
                "missing_api_key",
                "API real exige uma chave válida em OPENAI_API_KEY.",
                details=(
                    "Nenhuma chave foi encontrada no ambiente atual. "
                    "Mantenha o modo Sandbox ou configure OPENAI_API_KEY para usar a API real."
                ),
                status_code=400,
            )

        try:
            return self._call_remote(question, context_package, model_choice), "live"
        except AuthenticationError as exc:
            raise ExperimentExecutionError(
                "authentication_error",
                "A API rejeitou a autenticação. Verifique se OPENAI_API_KEY está correta e ativa.",
                details=self._build_error_details(exc),
                status_code=401,
            ) from exc
        except PermissionDeniedError as exc:
            raise ExperimentExecutionError(
                "permission_denied",
                "A conta ou projeto autenticado não tem permissão para usar esse modelo ou endpoint.",
                details=self._build_error_details(exc),
                status_code=403,
            ) from exc
        except BadRequestError as exc:
            raise ExperimentExecutionError(
                "bad_request",
                "A requisição para a API foi rejeitada. Revise modelo, base URL e parâmetros enviados.",
                details=self._build_error_details(exc),
                status_code=400,
            ) from exc
        except RateLimitError as exc:
            error_code, message = self._extract_remote_error(exc)
            insufficient_quota = self._is_insufficient_quota(error_code, message)
            raise ExperimentExecutionError(
                "insufficient_quota" if insufficient_quota else "rate_limit",
                (
                    "A conta ficou sem saldo, cota ou limite de gasto para continuar na API real."
                    if insufficient_quota
                    else "A API real atingiu limite de taxa temporário. Tente novamente em instantes."
                ),
                details=self._build_error_details(exc),
                status_code=402 if insufficient_quota else 429,
            ) from exc
        except APITimeoutError as exc:
            raise ExperimentExecutionError(
                "api_timeout",
                "A chamada para a API demorou demais e expirou.",
                details=self._build_error_details(exc),
                status_code=504,
            ) from exc
        except APIConnectionError as exc:
            raise ExperimentExecutionError(
                "api_connection_error",
                "Não foi possível conectar à API real. Verifique rede, proxy, VPN ou base URL.",
                details=self._build_error_details(exc),
                status_code=503,
            ) from exc
        except APIStatusError as exc:
            raise ExperimentExecutionError(
                "api_status_error",
                "A API real retornou um erro inesperado ao processar o experimento.",
                details=self._build_error_details(exc),
                status_code=exc.status_code or 500,
            ) from exc
        except Exception as exc:
            raise ExperimentExecutionError(
                "unexpected_live_error",
                "O experimento em API real falhou por um erro inesperado.",
                details=str(exc),
                status_code=500,
            ) from exc

    def _selected_model_name(self, model_choice: ModelChoice) -> str:
        return (
            self.settings.model_strong
            if model_choice == ModelChoice.strong
            else self.settings.model_medium
        )

    def _call_remote(
        self,
        question: QuestionSpec,
        context_package: ContextPackage,
        model_choice: ModelChoice,
    ) -> LLMResult:
        model_name = self._selected_model_name(model_choice)

        started_at = time.perf_counter()
        completion = self._client.chat.completions.create(
            model=model_name,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você avalia campanhas de RPG com foco em consistência narrativa. "
                        "Use apenas o contexto fornecido e diga quando faltarem evidências."
                    ),
                },
                {"role": "user", "content": context_package.prompt},
            ],
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        answer = completion.choices[0].message.content or ""
        prompt_tokens = completion.usage.prompt_tokens if completion.usage else 0
        completion_tokens = completion.usage.completion_tokens if completion.usage else 0
        total_tokens = completion.usage.total_tokens if completion.usage else 0
        estimated_cost = estimate_cost_usd(
            model_choice.value, prompt_tokens, completion_tokens
        )

        return LLMResult(
            answer=answer,
            usage=UsageMetrics(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                latency_ms=latency_ms,
                provider=self.settings.provider,
                model_name=model_name,
            ),
        )

    def _simulate(
        self,
        question: QuestionSpec,
        context_package: ContextPackage,
        model_choice: ModelChoice,
    ) -> LLMResult:
        started_at = time.perf_counter()
        selected_model_name = self._selected_model_name(model_choice)
        combined_context = "\n".join(doc.content for doc in context_package.documents).casefold()
        scores: dict[str, float] = defaultdict(float)
        target_label = self._target_label(question.question)

        for candidate, terms in question.scoring.candidate_terms.items():
            for term in terms:
                scores[candidate] += combined_context.count(term.casefold()) * 1.0

        if context_package.strategy.value == "relevant":
            scores[question.expected_answer.entity] += 2.0
        if context_package.strategy.value == "minimum":
            scores[question.expected_answer.entity] += 0.4
        if context_package.strategy.value == "none":
            scores[question.expected_answer.entity] += 0.1

        if model_choice == ModelChoice.strong:
            scores[question.expected_answer.entity] += 1.2

        if context_package.strategy.value == "abundant" and model_choice == ModelChoice.medium:
            for candidate in scores:
                if candidate != question.expected_answer.entity:
                    scores[candidate] += 0.8

        ordered_candidates = sorted(
            scores.items(), key=lambda item: item[1], reverse=True
        )
        best_candidate = ordered_candidates[0][0] if ordered_candidates else question.expected_answer.entity
        top_score = scores.get(best_candidate, 0.0)

        if (
            context_package.strategy.value == "abundant"
            and model_choice == ModelChoice.medium
            and len(ordered_candidates) > 1
        ):
            lead_gap = ordered_candidates[0][1] - ordered_candidates[1][1]
            if ordered_candidates[1][1] > 0 and lead_gap <= 4:
                best_candidate = ordered_candidates[1][0]

        if context_package.strategy.value == "none":
            answer = (
                f"Tese principal: Falta contexto para apontar {target_label} com segurança.\n"
                "Justificativa: Sem documentos da campanha, qualquer conclusão seria especulativa.\n"
                "Evidências:\n"
                "1. A pergunta depende de detalhes específicos do cenário.\n"
                "2. Não há pistas confiáveis disponíveis neste modo."
            )
        elif context_package.strategy.value == "minimum" and top_score < 2:
            answer = (
                f"Tese principal: O cenário sugere tensão, mas não dá para fechar {target_label} com confiança.\n"
                "Justificativa: O briefing fala de conflito portuário, porém não identifica agentes, locais ou pistas concretas.\n"
                "Evidências:\n"
                "1. O porto depende de festivais e receita alfandegária.\n"
                "2. Facções e rumores interferem em eventos públicos."
            )
        else:
            if best_candidate == question.expected_answer.entity:
                confidence_note = (
                    "A combinação de motivo, oportunidade e logística pesa mais do que os boatos paralelos."
                )
                evidence_lines = "\n".join(
                    f"{idx}. {evidence.detail} ({evidence.doc})"
                    for idx, evidence in enumerate(question.expected_answer.evidence[:2], start=1)
                )
                answer = (
                    f"Tese principal: {question.expected_answer.answer}\n"
                    f"Justificativa: {confidence_note} {question.expected_answer.rationale}\n"
                    f"Evidências:\n{evidence_lines}"
                )
            else:
                answer = (
                    f"Tese principal: {best_candidate} parece a alternativa mais provável.\n"
                    "Justificativa: O contexto abundante trouxe sinais concorrentes e boatos suficientes "
                    "para deslocar a leitura do motivo principal.\n"
                    "Evidências:\n"
                    "1. Pistas secundárias ganharam peso demais quando misturadas ao restante do material.\n"
                    "2. O ruído narrativo competiu com os indícios realmente centrais.\n"
                    "3. Uma leitura apressada do conjunto favorece conclusões menos estáveis."
                )

        completion_tokens = count_tokens(answer, selected_model_name)
        prompt_tokens = count_tokens(context_package.prompt, selected_model_name)
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = int((time.perf_counter() - started_at) * 1000) + 40
        estimated_cost = estimate_cost_usd(
            model_choice.value, prompt_tokens, completion_tokens
        )

        return LLMResult(
            answer=answer,
            usage=UsageMetrics(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                latency_ms=latency_ms,
                provider="simulated",
                model_name=(
                    "simulated-strong" if model_choice == ModelChoice.strong else "simulated-medium"
                ),
            ),
        )

    @staticmethod
    def _extract_remote_error(exc: Exception) -> tuple[str, str]:
        response = getattr(exc, "response", None)
        if response is None:
            return "", str(exc)

        try:
            payload = response.json()
        except Exception:
            return "", str(exc)

        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(error, dict):
            return "", str(exc)

        return str(error.get("code") or ""), str(error.get("message") or str(exc))

    def _build_error_details(self, exc: Exception) -> str:
        error_code, message = self._extract_remote_error(exc)
        status_code = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)

        parts = []
        if status_code:
            parts.append(f"status={status_code}")
        if error_code:
            parts.append(f"code={error_code}")
        if request_id:
            parts.append(f"request_id={request_id}")
        if message:
            parts.append(f"message={message}")

        return " | ".join(parts) if parts else str(exc)

    @staticmethod
    def _is_insufficient_quota(error_code: str, message: str) -> bool:
        combined = f"{error_code} {message}".casefold()
        return any(
            marker in combined
            for marker in [
                "insufficient_quota",
                "billing",
                "quota",
                "credit",
                "hard_limit",
                "balance",
            ]
        )

    @staticmethod
    def _target_label(question_text: str) -> str:
        lowered = question_text.casefold()
        if "qual facção" in lowered:
            return "uma facção"
        if "qual npc" in lowered:
            return "um NPC"
        if "qual local" in lowered:
            return "um local"
        return "uma resposta precisa"
