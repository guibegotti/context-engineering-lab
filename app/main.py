from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.exceptions import ExperimentExecutionError
from app.experiment_service import ExperimentService
from app.metrics import list_recent_results
from app.models import ExperimentRequest


app = FastAPI(title="Context Engineering Lab", version="0.1.0")
service = ExperimentService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/questions")
def questions() -> list[dict[str, str]]:
    return [
        {"id": item.id, "title": item.title, "question": item.question}
        for item in service.list_questions()
    ]


@app.get("/results/recent")
def recent_results(limit: int = 20):
    return [item.model_dump() for item in list_recent_results(limit=limit)]


@app.post("/experiment")
def run_experiment(request: ExperimentRequest):
    try:
        return service.run(
            question_id=request.question_id,
            model_choice=request.model_choice,
            strategy=request.strategy,
            execution_mode=request.execution_mode,
        ).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExperimentExecutionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.user_message,
                "details": exc.details,
            },
        ) from exc
