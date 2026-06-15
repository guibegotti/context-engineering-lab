from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.experiment_service import ExperimentService
from app.metrics import list_recent_results
from app.models import ContextStrategy, ModelChoice


st.set_page_config(
    page_title="Context Engineering Lab",
    page_icon="🧪",
    layout="wide",
)

service = ExperimentService()
questions = service.list_questions()

QUESTION_LABELS = {
    question.title: question.id
    for question in questions
}


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
        options=[ModelChoice.medium.value, ModelChoice.strong.value],
        format_func=lambda item: "Modelo médio" if item == "medium" else "Modelo forte",
    )
    strategy = st.radio(
        "Estratégia de contexto",
        options=[
            ContextStrategy.none.value,
            ContextStrategy.minimum.value,
            ContextStrategy.relevant.value,
            ContextStrategy.abundant.value,
        ],
        format_func=lambda item: {
            "none": "Sem contexto",
            "minimum": "Contexto mínimo",
            "relevant": "Contexto relevante",
            "abundant": "Contexto abundante/ruidoso",
        }[item],
    )
    run_single = st.button("Executar experimento", use_container_width=True)
    run_full = st.button("Comparar 4 estratégias", use_container_width=True)

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
    for idx, item in enumerate(ContextStrategy):
        result = service.run(
            question_id=selected_question_id,
            model_choice=ModelChoice(model_choice),
            strategy=item,
        )
        all_results.append(result)
        with columns[idx % 2]:
            st.markdown(f"### {item.value}")
            render_result_card(result)

    st.markdown("### Resumo comparativo")
    summary_rows = [
        {
            "strategy": item.strategy.value,
            "score": item.evaluation.quality_score,
            "tokens": item.usage.total_tokens,
            "latency_ms": item.usage.latency_ms,
            "cost_usd": item.usage.estimated_cost_usd,
            "mode": item.mode,
        }
        for item in all_results
    ]
    st.dataframe(summary_rows, use_container_width=True)

st.markdown("---")
st.subheader("Histórico recente")
history = list_recent_results(limit=12)

if history:
    st.dataframe([item.model_dump() for item in history], use_container_width=True)
else:
    st.info("Nenhum experimento gravado ainda.")

