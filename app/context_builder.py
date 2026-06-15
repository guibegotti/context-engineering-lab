from __future__ import annotations

from app.data_loader import list_world_document_names, load_world_document
from app.models import ContextDocument, ContextPackage, ContextStrategy, QuestionSpec


MINIMAL_CONTEXT = """# Campaign brief

- The campaign takes place on a stormy coastline where trade, religion, and local politics compete for influence.
- Port towns depend on seasonal festivals, customs revenue, and fragile alliances.
- Factions, rumors, and old grudges shape public events more than open warfare.
"""


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _select_documents(
    question: QuestionSpec, strategy: ContextStrategy
) -> list[ContextDocument]:
    if strategy == ContextStrategy.none:
        return []

    if strategy == ContextStrategy.minimum:
        return [ContextDocument(name="campaign_brief.md", content=MINIMAL_CONTEXT)]

    if strategy == ContextStrategy.relevant:
        return [load_world_document(name) for name in question.relevant_documents]

    return [load_world_document(name) for name in list_world_document_names()]


def _build_prompt(question: QuestionSpec, documents: list[ContextDocument]) -> str:
    context_block = "\n\n".join(
        f"## {doc.name}\n{doc.content.strip()}" for doc in documents
    )

    if not context_block:
        context_block = "Nenhum contexto adicional foi fornecido."

    return f"""Você é um analista narrativo de uma campanha de RPG de mesa genérico.

Responda sempre em português e siga estas regras:
- use apenas o que estiver no contexto;
- se faltar evidência, assuma menos e diga isso claramente;
- responda com uma tese principal e depois cite evidências.

Pergunta:
{question.question}

Contexto:
{context_block}

Formato esperado:
Tese principal: ...
Justificativa: ...
Evidências:
1. ...
2. ...
"""


def build_context(question: QuestionSpec, strategy: ContextStrategy) -> ContextPackage:
    documents = _select_documents(question, strategy)
    prompt = _build_prompt(question, documents)

    return ContextPackage(
        strategy=strategy,
        question_id=question.id,
        documents=documents,
        prompt=prompt,
        document_names=[doc.name for doc in documents],
        token_estimate=estimate_tokens(prompt),
    )

