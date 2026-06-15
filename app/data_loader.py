from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import DATA_DIR, WORLD_DIR
from app.models import ContextDocument, QuestionSpec


QUESTIONS_PATH = DATA_DIR / "questions.json"


@lru_cache(maxsize=1)
def load_questions() -> list[QuestionSpec]:
    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return [QuestionSpec.model_validate(item) for item in payload]


def list_questions() -> list[QuestionSpec]:
    return load_questions()


def get_question(question_id: str) -> QuestionSpec:
    for question in load_questions():
        if question.id == question_id:
            return question
    raise KeyError(f"Unknown question_id: {question_id}")


def load_world_document(filename: str) -> ContextDocument:
    path = WORLD_DIR / filename
    return ContextDocument(name=filename, content=path.read_text(encoding="utf-8"))


def list_world_document_names() -> list[str]:
    return sorted(path.name for path in WORLD_DIR.glob("*.md"))


def world_document_path(filename: str) -> Path:
    return WORLD_DIR / filename

