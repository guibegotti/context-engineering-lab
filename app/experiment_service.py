from __future__ import annotations

from datetime import datetime, timezone

from app.context_builder import build_context
from app.data_loader import get_question, list_questions
from app.evaluator import evaluate_answer
from app.llm_client import LLMClient
from app.metrics import init_db, new_run_id, save_experiment
from app.models import ContextStrategy, ExperimentResponse, ModelChoice, QuestionSpec


class ExperimentService:
    def __init__(self) -> None:
        init_db()
        self.client = LLMClient()

    def list_questions(self) -> list[QuestionSpec]:
        return list_questions()

    def run(
        self,
        question_id: str,
        model_choice: ModelChoice,
        strategy: ContextStrategy,
    ) -> ExperimentResponse:
        question = get_question(question_id)
        context_package = build_context(question, strategy)
        llm_result, mode = self.client.generate(question, context_package, model_choice)
        evaluation = evaluate_answer(question, llm_result.answer, context_package)

        response = ExperimentResponse(
            run_id=new_run_id(),
            created_at=datetime.now(timezone.utc),
            question_id=question.id,
            question=question.question,
            model_choice=model_choice,
            strategy=strategy,
            answer=llm_result.answer,
            context_documents=context_package.document_names,
            context_preview=context_package.prompt,
            usage=llm_result.usage,
            evaluation=evaluation,
            expected_entity=question.expected_answer.entity,
            mode=mode,
        )
        save_experiment(response)
        return response

