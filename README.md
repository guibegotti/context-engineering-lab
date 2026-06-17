# Context Engineering Lab

Um playground experimental para testar a hipótese de que contexto relevante gera mais valor do que contexto abundante.

## Hipótese

`H1`: contexto relevante, suficiente e bem selecionado supera contexto grande, redundante ou ruidoso.

## O que a demo entrega

- Interface Streamlit para escolher pergunta, modelo e estratégia de contexto
- API FastAPI para listar perguntas e executar experimentos
- Base fictícia de campanha de RPG genérico
- Quatro estratégias de contexto:
  - `none`
  - `minimum`
  - `relevant`
  - `abundant`
- Avaliação heurística com:
  - qualidade
  - aderência ao contexto
  - uso de evidências
  - alucinação
  - tokens
  - latência
  - custo estimado
- Persistência dos resultados em SQLite
- Modo offline simulado quando não há chave de API configurada

## Documentação técnica

Para uma visão completa de arquitetura, cálculos, heurísticas de avaliação, persistência, UI e decisões de design, veja:

- `docs/project_technical_guide.md`

## Estrutura

```text
context-engineering-lab/
  app/
  data/
    rpg_world/
    questions.json
  results/
  ui/
  .env.example
  README.md
  requirements.txt
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Se você quiser usar OpenAI ou OpenRouter, preencha a `.env` com a chave e, se necessário, ajuste `OPENAI_BASE_URL`.

Sem chave, a app entra em modo `simulated`, útil para demonstrar a hipótese sem depender de rede.

## Rodando a UI

```bash
streamlit run ui/streamlit_app.py
```

## Rodando a API

```bash
uvicorn app.main:app --reload
```

Endpoints principais:

- `GET /health`
- `GET /questions`
- `GET /results/recent`
- `POST /experiment`

## Como interpretar os resultados

- `none`: baseline sem apoio factual
- `minimum`: só um briefing curto da campanha
- `relevant`: só os documentos necessários para a pergunta
- `abundant`: contexto quase total com ruído proposital

O experimento favorece a hipótese quando `relevant` mantém ou melhora o score com menos tokens, menor custo e menor latência do que `abundant`.

## Observação sobre custos

O custo estimado usa preços configuráveis na `.env`. Os valores da `.env.example` são placeholders e devem ser revisados antes de qualquer comparação financeira real.
