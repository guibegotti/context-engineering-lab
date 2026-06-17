from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.experiment_service import ExperimentService
from app.exceptions import ExperimentExecutionError
from app.metrics import list_history_details, list_recent_results
from app.models import ContextStrategy, ExecutionMode, ModelChoice


RECENT_HISTORY_LIMIT = 4


st.set_page_config(
    page_title="Context Engineering Lab",
    page_icon="🧪",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stCode pre {
        white-space: pre-wrap !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }

    .stCode code {
        white-space: pre-wrap !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
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
        "execution_error": None,
        "single_result": None,
        "full_results": [],
        "matrix_results": [],
        "exp_selected_question": list(QUESTION_LABELS.keys())[0],
        "exp_run_type": "single",
        "exp_live_mode_enabled": False,
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


def experiment_type_label(experiment_type: str) -> str:
    return {
        "single": "Unitário",
        "full": "Comparativo 4 estratégias",
        "matrix": "Comparativo modelos x estratégias",
    }[experiment_type]


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


def describe_context_document(document_name: str) -> str:
    descriptions = {
        "locations.md": "Locais relevantes, incluindo cidades e pontos de interesse.",
        "factions.md": "Facções, interesses e disputas de poder.",
        "npcs.md": "NPCs, vínculos e oportunidades de ação.",
        "timeline.md": "Linha do tempo com eventos que afetam o presente.",
        "session_notes.md": "Anotações acumuladas das sessões e pistas já vistas.",
        "rumors.md": "Rumores e boatos que podem ajudar ou confundir.",
        "irrelevant_lore.md": "Lore decorativo e ruído proposital para testar excesso de contexto.",
    }
    return descriptions.get(document_name, "Documento incluído no contexto do experimento.")


def format_context_documents_for_display(context_documents: list[str]) -> str:
    if not context_documents:
        payload = [
            {
                "contexto": None,
                "descricao": "Sem documentos adicionais. Este experimento rodou apenas com a pergunta.",
            }
        ]
    else:
        payload = [
            {
                "contexto": document,
                "descricao": describe_context_document(document),
            }
            for document in context_documents
        ]

    return json.dumps(payload, ensure_ascii=False, indent=2)


def create_result_card_container(container_host, key: str):
    try:
        return container_host.container(border=True, key=key)
    except TypeError:
        return container_host.container()


def render_result_card(result, card_title: str | None = None, container_host=st) -> None:
    card = create_result_card_container(container_host, key=f"result-card-{result.run_id}")

    with card:
        if card_title:
            st.markdown(f"### {card_title}")

        st.subheader("Resposta")
        st.markdown(result.answer)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Qualidade",
            result.evaluation.quality_score,
            help="Score final de 0 a 100 após combinar acertos, aderência e penalidades.",
        )
        col2.metric(
            "Aderência",
            result.evaluation.adherence_score,
            help="Mostra o quanto a resposta ficou alinhada ao contexto e à pergunta.",
        )
        col3.metric(
            "Evidências",
            result.evaluation.evidence_score,
            help="Indica quantos termos e pistas essenciais do gabarito apareceram na resposta.",
        )
        hallucination_penalty = result.evaluation.hallucination_penalty
        penalty_display = "0" if hallucination_penalty == 0 else f"-{hallucination_penalty}"
        col4.metric(
            "Penalidade por alucinação",
            penalty_display,
            help="Desconta desvios ou termos suspeitos detectados fora do contexto esperado.",
        )

        st.caption(
            f"Modo: `{result.mode}` | Modelo: `{result.usage.model_name}` | "
            f"Tokens: `{result.usage.total_tokens}` | "
            f"Latência: `{result.usage.latency_ms} ms` | "
            f"Custo estimado: `${result.usage.estimated_cost_usd:.6f}`"
        )

        with st.expander("Contexto usado", expanded=False):
            st.code(
                format_context_documents_for_display(result.context_documents),
                language="json",
            )

        with st.expander("Prompt montado", expanded=False):
            st.code(result.context_preview, language="markdown")

        with st.expander("Notas da avaliação", expanded=False):
            st.markdown("\n".join([f"- {note}" for note in result.evaluation.notes]))


def render_result_grid(results, title_builder, container_host=st) -> None:
    for start in range(0, len(results), 2):
        columns = container_host.columns(2)
        row_items = results[start : start + 2]
        for idx, item in enumerate(row_items):
            render_result_card(
                item,
                card_title=title_builder(item),
                container_host=columns[idx],
            )


def render_model_comparison_section(model_item, model_results) -> None:
    section = create_result_card_container(
        st,
        key=f"model-section-{model_item.value}",
    )

    with section:
        st.markdown(f"### {model_label(model_item)}")
        st.caption(
            f"Os experimentos abaixo pertencem ao {model_label(model_item).lower()}."
        )
        render_result_grid(
            model_results,
            title_builder=lambda result: strategy_label(result.strategy),
            container_host=section,
        )


def render_execution_error() -> None:
    execution_error = st.session_state.execution_error
    if not execution_error:
        return

    st.error(execution_error["message"])
    if execution_error.get("details"):
        with st.expander("Detalhes do erro", expanded=False):
            st.code(execution_error["details"], language="text")


def execute_selected_experiment(
    question_id: str,
    run_type: str,
    execution_mode: ExecutionMode,
    model_choice: ModelChoice,
    strategy: ContextStrategy,
) -> None:
    completed_runs = 0
    try:
        if run_type == "single":
            st.session_state.single_result = service.run(
                question_id=question_id,
                model_choice=model_choice,
                strategy=strategy,
                execution_mode=execution_mode,
            )
            completed_runs = 1
            st.session_state.experiment_mode = "single"
            st.session_state.full_results = []
            st.session_state.matrix_results = []
        elif run_type == "full":
            full_results = []
            for item in STRATEGY_ORDER:
                full_results.append(
                    service.run(
                        question_id=question_id,
                        model_choice=model_choice,
                        strategy=item,
                        execution_mode=execution_mode,
                    )
                )
                completed_runs += 1

            st.session_state.full_results = full_results
            st.session_state.experiment_mode = "full"
            st.session_state.single_result = None
            st.session_state.matrix_results = []
        else:
            matrix_results = []
            for model_item in MODEL_ORDER:
                for strategy_item in STRATEGY_ORDER:
                    matrix_results.append(
                        service.run(
                            question_id=question_id,
                            model_choice=model_item,
                            strategy=strategy_item,
                            execution_mode=execution_mode,
                        )
                    )
                    completed_runs += 1

            st.session_state.matrix_results = matrix_results
            st.session_state.experiment_mode = "matrix"
            st.session_state.single_result = None
            st.session_state.full_results = []

        st.session_state.execution_error = None
    except ExperimentExecutionError as exc:
        details = exc.details
        if completed_runs > 0:
            partial_note = (
                f"{completed_runs} execução(ões) já tinham sido concluídas antes da falha."
            )
            details = f"{details}\n{partial_note}" if details else partial_note

        st.session_state.execution_error = {
            "message": exc.user_message,
            "details": details,
            "code": exc.code,
        }


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

        score_pair = None
        tokens_pair = None
        cost_pair = None
        diff_score = None
        diff_tokens = None
        diff_cost = None

        if medium_result and strong_result:
            score_pair = (
                f"{medium_result.evaluation.quality_score} / "
                f"{strong_result.evaluation.quality_score}"
            )
            tokens_pair = (
                f"{medium_result.usage.total_tokens} / "
                f"{strong_result.usage.total_tokens}"
            )
            cost_pair = (
                f"${medium_result.usage.estimated_cost_usd:.6f} / "
                f"${strong_result.usage.estimated_cost_usd:.6f}"
            )
            diff_score = (
                strong_result.evaluation.quality_score
                - medium_result.evaluation.quality_score
            )
            diff_tokens = (
                strong_result.usage.total_tokens
                - medium_result.usage.total_tokens
            )
            diff_cost = round(
                strong_result.usage.estimated_cost_usd
                - medium_result.usage.estimated_cost_usd,
                6,
            )

        rows.append(
            {
                "Estratégia": strategy_label(strategy_item),
                "Score m/f": score_pair,
                "Dif. score": diff_score,
                "Tokens m/f": tokens_pair,
                "Dif. tokens": diff_tokens,
                "Custo m/f": cost_pair,
                "Dif. custo": diff_cost,
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
        run_type = st.selectbox(
            "Tipo de experimento",
            options=["single", "full", "matrix"],
            format_func=experiment_type_label,
            key="exp_run_type",
        )
        live_mode_enabled = st.toggle(
            "Usar API real",
            key="exp_live_mode_enabled",
            help="Desligado usa Sandbox sem custo. Ligado faz chamadas reais para a API e pode consumir tokens.",
        )
        execution_mode = (
            ExecutionMode.live.value if live_mode_enabled else ExecutionMode.sandbox.value
        )
        model_choice = st.radio(
            "Modelo",
            options=[item.value for item in MODEL_ORDER],
            format_func=lambda item: model_label(ModelChoice(item)),
            key="exp_model_choice",
            disabled=run_type == "matrix",
        )
        strategy = st.radio(
            "Estratégia de contexto",
            options=[item.value for item in STRATEGY_ORDER],
            format_func=lambda item: strategy_label(ContextStrategy(item)),
            key="exp_strategy",
            disabled=run_type in {"full", "matrix"},
        )
        if execution_mode == ExecutionMode.live.value:
            if not service.client.settings.api_key:
                st.warning("OPENAI_API_KEY não está configurada neste ambiente.", icon="🔑")
        else:
            st.caption("Sandbox é o modo padrão e não faz chamadas externas pagas.")
        run_experiment = st.button("Executar experimento", use_container_width=True)

    selected_question_id = QUESTION_LABELS[selected_question_title]

    if run_experiment:
        execute_selected_experiment(
            question_id=selected_question_id,
            run_type=run_type,
            execution_mode=ExecutionMode(execution_mode),
            model_choice=ModelChoice(model_choice),
            strategy=ContextStrategy(strategy),
        )

    render_execution_error()

    if st.session_state.experiment_mode == "single" and st.session_state.single_result is not None:
        render_result_card(
            st.session_state.single_result,
            card_title=(
                f"{strategy_label(st.session_state.single_result.strategy)}"
                f" | {model_label(st.session_state.single_result.model_choice)}"
            ),
        )

    if st.session_state.experiment_mode == "full" and st.session_state.full_results:
        st.subheader("Comparação")
        render_result_grid(
            st.session_state.full_results,
            title_builder=lambda item: (
                f"{strategy_label(item.strategy)}"
                f" | {model_label(item.model_choice)}"
            ),
        )

        st.markdown("### Resumo comparativo")
        st.dataframe(
            [result_summary_row(item) for item in st.session_state.full_results],
            use_container_width=True,
        )

    if st.session_state.experiment_mode == "matrix" and st.session_state.matrix_results:
        st.subheader("Matriz comparativa")
        for model_item in MODEL_ORDER:
            model_results = [
                item
                for item in st.session_state.matrix_results
                if item.model_choice == model_item
            ]
            render_model_comparison_section(model_item, model_results)

        st.markdown("### Resumo da matriz")
        st.dataframe(
            [result_summary_row(item) for item in st.session_state.matrix_results],
            use_container_width=True,
        )

        st.markdown("### Comparativo executivo")
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
