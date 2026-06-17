# Context Engineering Lab

An experimental playground for testing the hypothesis that relevant context creates more value than abundant context.

## Hypothesis

`H1`: relevant, sufficient, and well-selected context beats large, redundant, or noisy context.

## What the project includes

- A Streamlit interface for choosing a question, model, context strategy, and execution mode
- A FastAPI backend for listing questions and running experiments
- A fictional generic tabletop RPG campaign dataset
- Four context strategies:
  - `none`
  - `minimum`
  - `relevant`
  - `abundant`
- Heuristic evaluation for:
  - quality
  - contextual adherence
  - evidence usage
  - hallucination / false-lead penalties
  - tokens
  - latency
  - estimated cost
- SQLite result persistence
- A default offline sandbox mode when no API key is configured

## Technical documentation

For a complete explanation of the architecture, calculations, evaluation heuristics, persistence model, UI decisions, and design tradeoffs, see:

- `docs/project_technical_guide.md`

## Project structure

```text
context-engineering-lab/
  app/
  data/
    rpg_world/
    questions.json
  docs/
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

If you want to use OpenAI or another OpenAI-compatible provider, fill in `.env` with your API key and adjust `OPENAI_BASE_URL` if needed.

Without a key, the app remains usable in `sandbox` mode, which is useful for demos and local testing.

## Running the UI

```bash
streamlit run ui/streamlit_app.py
```

## Running the API

```bash
uvicorn app.main:app --reload
```

Main endpoints:

- `GET /health`
- `GET /questions`
- `GET /results/recent`
- `POST /experiment`

## Experiment modes

The UI supports three run types:

- `single`: one question with one model and one context strategy
- `full`: one model compared across the four context strategies
- `matrix`: medium and strong models compared across the four context strategies

It also supports two execution modes:

- `sandbox`: local simulated mode, no paid API usage
- `live`: real API calls using the configured provider

## How to interpret results

- `none`: baseline with no factual support
- `minimum`: only a short campaign brief
- `relevant`: only the documents required to answer the question
- `abundant`: nearly the full document set, including deliberate noise

The experiment supports the hypothesis when `relevant` preserves or improves quality with fewer tokens, lower cost, and lower latency than `abundant`.

## Cost note

Estimated cost is computed from configurable pricing values in `.env`.

The defaults in the project are intended to match the configured logical model roles (`medium` and `strong`), but you should always review pricing before making real financial comparisons or running large live batches.
