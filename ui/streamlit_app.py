from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.experiment_service import ExperimentService
from app.metrics import list_history_details, list_recent_results
from app.models import ContextStrategy, ModelChoice


RECENT_HISTORY_LIMIT = 4


st.set_page_config(
    page_title="Context Engineering Lab",
    page_icon="🧪",
    layout="wide",
)

service = ExperimentService()
service.ensure_demo_history(minimum_runs=4)
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


def init_state() -> None:
    defaults = {
        "current_page": "home",
        "nav_history": [],
        "experiment_mode": "idle",
        "single_result": None,
        "full_results": [],
        "matrix_results": [],
        "exp_selected_question": list(QUESTION_LABELS.keys())[0],
        "exp_model_choice": ModelChoice.medium.value,
        "exp_strategy": ContextStrategy.none.value,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def model_label(model_choice: ModelChoice) -> str:
    return "Modelo médio" if model_choice == ModelChoice.medium else "Modelo forte"


def strategy_label(strategy: ContextStrategy) -> str:
    return {
        ContextStrategy.none: "Sem contexto",
        ContextStrategy.minimum: "Contexto mínimo",
        ContextStrategy.relevant: "Contexto relevante",
        ContextStrategy.abundant: "Contexto abundante/ruidoso",
    }[strategy]


def navigate_to(target_page: str) -> None:
    current_page = st.session_state.current_page
    if current_page != target_page:
        st.session_state.nav_history.append(current_page)
        st.session_state.current_page = target_page
        st.rerun()


def go_back() -> None:
    if st.session_state.nav_history:
        st.session_state.current_page = st.session_state.nav_history.pop()
    else:
        st.session_state.current_page = "home"
    st.rerun()


def go_home() -> None:
    current_page = st.session_state.current_page
    if current_page != "home":
        st.session_state.nav_history.append(current_page)
        st.session_state.current_page = "home"
        st.rerun()


def render_result_card(result) -> None:
    st.subheader("Resposta")
    st.markdown(result.answer)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Qualidade", result.evaluation.quality_score)
    col2.metric("Aderência", result.evaluation.adherence_score)
    col3.metric("Evidências", result.evaluation.evidence_score)
    hallucination_penalty = result.evaluation.hallucination_penalty
    penalty_display = "0" if hallucination_penalty == 0 else f"-{hallucination_penalty}"
    col4.metric("Penalidade por alucinação", penalty_display)

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


def build_matrix_pivot_rows(matrix_results) -> list[dict[str, object]]:
    by_pair = {
        (item.model_choice, item.strategy): item
        for item in matrix_results
    }
    rows = []

    for strategy_item in STRATEGY_ORDER:
        medium_result = by_pair.get((ModelChoice.medium, strategy_item))
        strong_result = by_pair.get((ModelChoice.strong, strategy_item))

        rows.append(
            {
                "strategy": strategy_label(strategy_item),
                "medium_score": medium_result.evaluation.quality_score if medium_result else None,
                "medium_tokens": medium_result.usage.total_tokens if medium_result else None,
                "medium_latency_ms": medium_result.usage.latency_ms if medium_result else None,
                "medium_cost_usd": medium_result.usage.estimated_cost_usd if medium_result else None,
                "strong_score": strong_result.evaluation.quality_score if strong_result else None,
                "strong_tokens": strong_result.usage.total_tokens if strong_result else None,
                "strong_latency_ms": strong_result.usage.latency_ms if strong_result else None,
                "strong_cost_usd": strong_result.usage.estimated_cost_usd if strong_result else None,
                "delta_score": (
                    strong_result.evaluation.quality_score - medium_result.evaluation.quality_score
                    if medium_result and strong_result
                    else None
                ),
                "delta_tokens": (
                    strong_result.usage.total_tokens - medium_result.usage.total_tokens
                    if medium_result and strong_result
                    else None
                ),
                "delta_cost_usd": (
                    round(
                        strong_result.usage.estimated_cost_usd
                        - medium_result.usage.estimated_cost_usd,
                        6,
                    )
                    if medium_result and strong_result
                    else None
                ),
            }
        )

    return rows


def history_summary_row(item) -> dict[str, object]:
    return {
        "created_at": item.created_at.isoformat(),
        "question_id": item.question_id,
        "model": item.model_choice,
        "strategy": item.strategy,
        "score": item.quality_score,
        "tokens": item.total_tokens,
        "latency_ms": item.latency_ms,
        "cost_usd": item.estimated_cost_usd,
        "provider": item.provider,
    }


def render_sidebar_navigation() -> None:
    with st.sidebar:
        nav_cols = st.columns(2)
        back_clicked = nav_cols[0].button(
            "← Voltar",
            use_container_width=True,
            disabled=st.session_state.current_page == "home" and not st.session_state.nav_history,
        )
        home_clicked = nav_cols[1].button(
            "⌂ Início",
            use_container_width=True,
            disabled=st.session_state.current_page == "home",
        )
        st.markdown("---")

    if back_clicked:
        go_back()
    if home_clicked:
        go_home()


def render_home_page() -> None:
    st.title("Context Engineering Lab")
    st.caption("Teste se contexto relevante supera contexto abundante em tarefas narrativas dependentes de domínio.")

    st.markdown(
        """
        **Hipótese:** contexto relevante, suficiente e bem selecionado tende a vencer
        contexto grande, redundante e ruidoso em qualidade por token.
        """
    )

    with st.sidebar:
        st.subheader("Páginas")
        if st.button("◫ Experimentos", use_container_width=True):
            navigate_to("experiments")
        if st.button("☰ Histórico", use_container_width=True):
            navigate_to("history")

    st.markdown("---")
    st.subheader("Histórico recente")
    history = list_recent_results(limit=RECENT_HISTORY_LIMIT)
    if history:
        st.dataframe([item.model_dump() for item in history], use_container_width=True)
    else:
        st.info("Nenhum experimento gravado ainda.")


def render_experiments_page() -> None:
    st.title("Experimentos")
    st.caption("Configure uma pergunta, selecione o modelo e compare estratégias de contexto.")

    with st.sidebar:
        st.subheader("Configuração")
        selected_question_title = st.selectbox(
            "Pergunta",
            list(QUESTION_LABELS.keys()),
            key="exp_selected_question",
        )
        model_choice = st.radio(
            "Modelo",
            options=[item.value for item in MODEL_ORDER],
            format_func=lambda item: model_label(ModelChoice(item)),
            key="exp_model_choice",
        )
        strategy = st.radio(
            "Estratégia de contexto",
            options=[item.value for item in STRATEGY_ORDER],
            format_func=lambda item: strategy_label(ContextStrategy(item)),
            key="exp_strategy",
        )
        run_single = st.button("Executar experimento", use_container_width=True)
        run_full = st.button("Comparar 4 estratégias", use_container_width=True)
        run_matrix = st.button("Comparar modelos x estratégias", use_container_width=True)

    selected_question_id = QUESTION_LABELS[selected_question_title]

    if run_single:
        st.session_state.single_result = service.run(
            question_id=selected_question_id,
            model_choice=ModelChoice(model_choice),
            strategy=ContextStrategy(strategy),
        )
        st.session_state.experiment_mode = "single"
        st.session_state.full_results = []
        st.session_state.matrix_results = []

    if run_full:
        st.session_state.full_results = [
            service.run(
                question_id=selected_question_id,
                model_choice=ModelChoice(model_choice),
                strategy=item,
            )
            for item in STRATEGY_ORDER
        ]
        st.session_state.experiment_mode = "full"
        st.session_state.single_result = None
        st.session_state.matrix_results = []

    if run_matrix:
        st.session_state.matrix_results = [
            service.run(
                question_id=selected_question_id,
                model_choice=model_item,
                strategy=strategy_item,
            )
            for model_item in MODEL_ORDER
            for strategy_item in STRATEGY_ORDER
        ]
        st.session_state.experiment_mode = "matrix"
        st.session_state.single_result = None
        st.session_state.full_results = []

    if st.session_state.experiment_mode == "single" and st.session_state.single_result is not None:
        render_result_card(st.session_state.single_result)

    if st.session_state.experiment_mode == "full" and st.session_state.full_results:
        st.subheader("Comparação")
        columns = st.columns(2)
        for idx, item in enumerate(st.session_state.full_results):
            with columns[idx % 2]:
                st.markdown(f"### {strategy_label(item.strategy)}")
                render_result_card(item)

        st.markdown("### Resumo comparativo")
        st.dataframe(
            [result_summary_row(item) for item in st.session_state.full_results],
            use_container_width=True,
        )

    if st.session_state.experiment_mode == "matrix" and st.session_state.matrix_results:
        st.subheader("Matriz comparativa")
        for model_item in MODEL_ORDER:
            st.markdown(f"### {model_label(model_item)}")
            columns = st.columns(2)
            model_results = [
                item
                for item in st.session_state.matrix_results
                if item.model_choice == model_item
            ]
            for idx, result in enumerate(model_results):
                with columns[idx % 2]:
                    st.markdown(f"#### {strategy_label(result.strategy)}")
                    render_result_card(result)

        st.markdown("### Resumo da matriz")
        st.dataframe(
            [result_summary_row(item) for item in st.session_state.matrix_results],
            use_container_width=True,
        )

        st.markdown("### Pivot executivo")
        st.dataframe(
            build_matrix_pivot_rows(st.session_state.matrix_results),
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("Histórico recente")
    history = list_recent_results(limit=RECENT_HISTORY_LIMIT)
    if history:
        st.dataframe([item.model_dump() for item in history], use_container_width=True)
    else:
        st.info("Nenhum experimento gravado ainda.")


def render_history_page() -> None:
    st.title("Histórico")
    st.caption("Consulte todas as execuções gravadas sem interferir no experimento aberto.")

    history_details = list_history_details()
    if not history_details:
        st.info("Nenhum experimento gravado ainda.")
        return

    st.dataframe(
        [history_summary_row(item) for item in history_details],
        use_container_width=True,
    )

    for item in history_details:
        with st.expander(
            f"{item.created_at.isoformat()} | {item.question_id} | {item.model_choice}/{item.strategy}"
        ):
            st.markdown(f"**Modelo real:** `{item.model_name}`")
            st.markdown(
                f"**Contexto usado:** {', '.join(item.context_documents) or 'Sem documentos'}"
            )
            st.markdown("**Resposta gerada**")
            st.markdown(item.answer)


init_state()
render_sidebar_navigation()

if st.session_state.current_page == "home":
    render_home_page()
elif st.session_state.current_page == "experiments":
    render_experiments_page()
else:
    render_history_page()
