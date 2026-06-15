from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WORLD_DIR = DATA_DIR / "rpg_world"
DEFAULT_DB_PATH = PROJECT_ROOT / "results" / "context_lab.db"


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str
    base_url: str
    app_url: str
    app_title: str
    model_medium: str
    model_strong: str
    medium_input_cost_per_million: float
    medium_output_cost_per_million: float
    strong_input_cost_per_million: float
    strong_output_cost_per_million: float
    results_db_path: Path


def get_settings() -> Settings:
    load_dotenv()

    return Settings(
        provider=os.getenv("LLM_PROVIDER", "openai"),
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        app_url=os.getenv("OPENAI_APP_URL", ""),
        app_title=os.getenv("OPENAI_APP_TITLE", "Context Engineering Lab"),
        model_medium=os.getenv("MODEL_MEDIUM", "gpt-4.1-mini"),
        model_strong=os.getenv("MODEL_STRONG", "gpt-4.1"),
        medium_input_cost_per_million=float(
            os.getenv("MODEL_MEDIUM_INPUT_COST_PER_MILLION", "0.40")
        ),
        medium_output_cost_per_million=float(
            os.getenv("MODEL_MEDIUM_OUTPUT_COST_PER_MILLION", "1.60")
        ),
        strong_input_cost_per_million=float(
            os.getenv("MODEL_STRONG_INPUT_COST_PER_MILLION", "2.00")
        ),
        strong_output_cost_per_million=float(
            os.getenv("MODEL_STRONG_OUTPUT_COST_PER_MILLION", "8.00")
        ),
        results_db_path=Path(os.getenv("RESULTS_DB_PATH", str(DEFAULT_DB_PATH))),
    )

