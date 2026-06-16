from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.experiment_service import ExperimentService
from app.metrics import get_database_debug_info, list_recent_results
from app.models import ContextStrategy, ModelChoice


st.set_page_config(
    page_title="Context Engineering Lab",
    page_icon="🧪",
    layout="wide",
)

service = ExperimentService()
service.ensure_demo_history(minimum_runs=3)
questions = service.list_questions()

QUESTION_LABELS = {
    question.title: question.id
    for question in questions
}
MODEL_ORDER = [ModelChoice.medium, ModelChoice.strong]
STRATEGY_ORDER = [
    ContextStrategy.none,
    ContextStrategy.minimum,
    ContextStrategy.relevant,
    ContextStrategy.abundant,
]


def model_label(model_choice: ModelChoice) -> str:
    return "Modelo médio" if model_choice == ModelChoice.medium else "Modelo forte"


def strategy_label(strategy: ContextStrategy) -> str:
    return {
        ContextStrategy.none: "Sem contexto",
        ContextStrategy.minimum: "Contexto mínimo",
        ContextStrategy.relevant: "Contexto relevante",
        ContextStrategy.abundant: "Contexto abundante/ruidoso",
    }[strategy]


def render_result_card(result) -> None:
    st.subheader("Resposta")
    st.markdown(result.answer)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Qualidade", result.evaluation.quality_score)
    col2.metric("Aderência", result.evaluation.adherence_score)
    col3.metric("Evidências", result.evaluation.evidence_score)
    col4.metric("Alucinação", f"-{result.evaluation.hallucination_penalty}")

    st.caption(
        f"Modo: `{result.mode}` | Modelo: `{result.usage.model_name}` | "
        f"Tokens: `{result.usage.total_tokens}` | "
        f"Latência: `{result.usage.latency_ms} ms` | "
        f"Custo estimado: `${result.usage.estimated_cost_usd:.6f}`"
    )

    st.markdown("**Contexto usado**")
    st.write(result.context_documents or ["Sem documentos"])

    with st.expander("Prompt montado"):
        st.code(result.context_preview, language="markdown")

    with st.expander("Notas da avaliação"):
        for note in result.evaluation.notes:
            st.write(f"- {note}")


def result_summary_row(result) -> dict[str, object]:
    return {
        "model": model_label(result.model_choice),
        "strategy": strategy_label(result.strategy),
        "score": result.evaluation.quality_score,
        "tokens": result.usage.total_tokens,
        "latency_ms": result.usage.latency_ms,
        "cost_usd": result.usage.estimated_cost_usd,
        "mode": result.mode,
    }


st.title("Context Engineering Lab")
st.caption("Teste se contexto relevante supera contexto abundante em tarefas narrativas dependentes de domínio.")

st.markdown(
    """
    **Hipótese:** contexto relevante, suficiente e bem selecionado tende a vencer
    contexto grande, redundante e ruidoso em qualidade por token.
    """
)

with st.sidebar:
    st.header("Configuração")
    selected_question_title = st.selectbox("Pergunta", list(QUESTION_LABELS.keys()))
    model_choice = st.radio(
        "Modelo",
        options=[item.value for item in MODEL_ORDER],
        format_func=lambda item: model_label(ModelChoice(item)),
    )
    strategy = st.radio(
        "Estratégia de contexto",
        options=[item.value for item in STRATEGY_ORDER],
        format_func=lambda item: strategy_label(ContextStrategy(item)),
    )
    run_single = st.button("Executar experimento", use_container_width=True)
    run_full = st.button("Comparar 4 estratégias", use_container_width=True)
    run_matrix = st.button("Comparar modelos x estratégias", use_container_width=True)

selected_question_id = QUESTION_LABELS[selected_question_title]

if run_single:
    result = service.run(
        question_id=selected_question_id,
        model_choice=ModelChoice(model_choice),
        strategy=ContextStrategy(strategy),
    )
    render_result_card(result)

if run_full:
    st.subheader("Comparação")
    columns = st.columns(2)
    all_results = []
    for idx, item in enumerate(STRATEGY_ORDER):
        result = service.run(
            question_id=selected_question_id,
            model_choice=ModelChoice(model_choice),
            strategy=item,
        )
        all_results.append(result)
        with columns[idx % 2]:
            st.markdown(f"### {strategy_label(item)}")
            render_result_card(result)

    st.markdown("### Resumo comparativo")
    st.dataframe(
        [result_summary_row(item) for item in all_results],
        use_container_width=True,
    )

if run_matrix:
    st.subheader("Matriz comparativa")
    matrix_results = []

    for model_item in MODEL_ORDER:
        st.markdown(f"### {model_label(model_item)}")
        columns = st.columns(2)

        for idx, strategy_item in enumerate(STRATEGY_ORDER):
            result = service.run(
                question_id=selected_question_id,
                model_choice=model_item,
                strategy=strategy_item,
            )
            matrix_results.append(result)
            with columns[idx % 2]:
                st.markdown(f"#### {strategy_label(strategy_item)}")
                render_result_card(result)

    st.markdown("### Resumo da matriz")
    st.dataframe(
        [result_summary_row(item) for item in matrix_results],
        use_container_width=True,
    )

st.markdown("---")
st.subheader("Diagnóstico do banco")
db_info = get_database_debug_info()
st.caption(
    f"Banco resolvido: `{db_info['resolved_path']}` | "
    f"Registros em experiment_runs: `{db_info['experiment_runs_count']}`"
)
with st.expander("Detalhes de persistência"):
    st.json(db_info)

st.markdown("---")
st.subheader("Histórico recente")
history = list_recent_results(limit=12)

if history:
    st.dataframe([item.model_dump() for item in history], use_container_width=True)
else:
    st.info("Nenhum experimento gravado ainda.")
