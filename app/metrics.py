from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.models import ExperimentResponse, RecentResult


def estimate_cost_usd(model_choice: str, prompt_tokens: int, completion_tokens: int) -> float:
    settings = get_settings()

    if model_choice == "strong":
        input_rate = settings.strong_input_cost_per_million
        output_rate = settings.strong_output_cost_per_million
    else:
        input_rate = settings.medium_input_cost_per_million
        output_rate = settings.medium_output_cost_per_million

    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (completion_tokens / 1_000_000) * output_rate
    return round(input_cost + output_cost, 6)


def _can_write_sqlite(db_path: Path) -> bool:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.execute("CREATE TABLE IF NOT EXISTS _write_probe (id INTEGER)")
        connection.commit()
        connection.close()
        return True
    except sqlite3.Error:
        return False


_RESOLVED_DB_PATH: Path | None = None


def resolve_db_path() -> Path:
    global _RESOLVED_DB_PATH
    if _RESOLVED_DB_PATH is not None:
        return _RESOLVED_DB_PATH

    configured_path = get_settings().results_db_path
    if _can_write_sqlite(configured_path):
        _RESOLVED_DB_PATH = configured_path
        return _RESOLVED_DB_PATH

    fallback_path = Path(tempfile.gettempdir()) / "context_lab.db"
    if _can_write_sqlite(fallback_path):
        _RESOLVED_DB_PATH = fallback_path
        return _RESOLVED_DB_PATH

    raise sqlite3.OperationalError("Could not create a writable SQLite database path.")


def _connect() -> sqlite3.Connection:
    db_path = resolve_db_path()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                question_id TEXT NOT NULL,
                model_choice TEXT NOT NULL,
                strategy TEXT NOT NULL,
                quality_score INTEGER NOT NULL,
                adherence_score INTEGER NOT NULL,
                evidence_score INTEGER NOT NULL,
                hallucination_penalty INTEGER NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                latency_ms INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                answer TEXT NOT NULL,
                context_documents TEXT NOT NULL,
                evaluation_json TEXT NOT NULL
            )
            """
        )


def save_experiment(response: ExperimentResponse) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO experiment_runs (
                run_id,
                created_at,
                question_id,
                model_choice,
                strategy,
                quality_score,
                adherence_score,
                evidence_score,
                hallucination_penalty,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                estimated_cost_usd,
                latency_ms,
                provider,
                model_name,
                answer,
                context_documents,
                evaluation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response.run_id,
                response.created_at.isoformat(),
                response.question_id,
                response.model_choice.value,
                response.strategy.value,
                response.evaluation.quality_score,
                response.evaluation.adherence_score,
                response.evaluation.evidence_score,
                response.evaluation.hallucination_penalty,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
                response.usage.estimated_cost_usd,
                response.usage.latency_ms,
                response.usage.provider,
                response.usage.model_name,
                response.answer,
                json.dumps(response.context_documents, ensure_ascii=False),
                response.evaluation.model_dump_json(),
            ),
        )


def list_recent_results(limit: int = 20) -> list[RecentResult]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                run_id,
                created_at,
                question_id,
                model_choice,
                strategy,
                quality_score,
                total_tokens,
                estimated_cost_usd,
                latency_ms,
                provider
            FROM experiment_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        RecentResult(
            run_id=row["run_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            question_id=row["question_id"],
            model_choice=row["model_choice"],
            strategy=row["strategy"],
            quality_score=row["quality_score"],
            total_tokens=row["total_tokens"],
            estimated_cost_usd=row["estimated_cost_usd"],
            latency_ms=row["latency_ms"],
            provider=row["provider"],
        )
        for row in rows
    ]


def new_run_id() -> str:
    return str(uuid4())
