# Context Engineering Lab: Technical Guide

## 1. Purpose of the project

Context Engineering Lab is an experimental playground for testing a single product hypothesis:

> Relevant, sufficient, and well-selected context tends to beat large, redundant, noisy context in quality per token.

The project uses a fictional tabletop RPG campaign setting as a controlled domain where answers depend on distributed evidence rather than generic world knowledge.

This is not a general-purpose RPG assistant. It is a comparative environment for running the same question under different context strategies and measuring:

- output quality
- contextual adherence
- evidence usage
- hallucination / false-lead acceptance
- token consumption
- latency
- estimated cost

## 2. Core experimental design

The experiment compares four context strategies:

1. `none`
   Only the question is provided.

2. `minimum`
   A short campaign brief is provided, but no case-specific evidence.

3. `relevant`
   Only the documents required to answer the question are included.

4. `abundant`
   The full world document set is included, including noise, false leads, decorative lore, overlapping names, and contradictory signals.

The design intention is:

- `none` should force speculative or cautious answers
- `minimum` should provide atmosphere but remain insufficient
- `relevant` should enable correct synthesis with efficient token use
- `abundant` should increase token use and sometimes reduce answer quality through distraction

## 3. High-level architecture

The project is split into a few small modules with clear responsibilities:

- `app/config.py`
  Loads runtime configuration, models, pricing, API settings, and database path.

- `app/data_loader.py`
  Loads `questions.json` and markdown world documents.

- `app/context_builder.py`
  Selects documents by context strategy and builds the final prompt.

- `app/token_counter.py`
  Counts tokens using `tiktoken`.

- `app/llm_client.py`
  Executes either sandbox simulation or real OpenAI-compatible API calls.

- `app/evaluator.py`
  Scores the answer heuristically against the structured expected answer and rubric.

- `app/metrics.py`
  Estimates cost and persists experiment runs to SQLite.

- `app/experiment_service.py`
  Orchestrates the full run: load question, build context, generate answer, evaluate, persist.

- `app/main.py`
  FastAPI surface for programmatic access.

- `ui/streamlit_app.py`
  Streamlit UI for manual experimentation, comparisons, history, and progress feedback.

## 4. Data model and content structure

### 4.1 World data

The world lives under:

`data/rpg_world/`

This folder contains markdown documents that function as the factual evidence base for the experiments.

Examples:

- `locations.md`
- `factions.md`
- `npcs.md`
- `timeline.md`
- `session_notes.md`
- `rumors.md`
- `irrelevant_lore.md`
- `logistics.md`
- `case_4_operation_ghost.md`

These files are intentionally written to support:

- direct evidence
- partial evidence
- distributed evidence
- misleading evidence
- decorative noise

### 4.2 Question schema

Questions are stored in:

`data/questions.json`

Each question includes:

- `id`
- `title`
- `question`
- `relevant_documents`
- `expected_answer`
- `scoring`

### 4.3 Expected answer structure

`expected_answer` includes:

- `entity`
  The central answer target or main actor.

- `answer`
  Canonical answer wording.

- `rationale`
  Narrative explanation of why the answer is correct.

- `evidence`
  Structured supporting evidence items, each with:
  - `doc`
  - `detail`

### 4.4 Scoring structure

`scoring` currently supports:

- `required_terms`
- `bonus_terms`
- `hallucination_terms`
- `candidate_terms`
- `rubric_checks`
- `false_leads`
- `rejection_markers`
- `uncertainty_markers`

The first four fields are used across all cases. The last four were added to support more complex investigative cases such as Case 4.

## 5. Context selection logic

Implemented in:

`app/context_builder.py`

The core selection function is `_select_documents(question, strategy)`.

Behavior:

- `none` returns an empty document list
- `minimum` returns a synthetic `campaign_brief.md`
- `relevant` returns only `question.relevant_documents`
- `abundant` returns every markdown file in the world folder

This design deliberately keeps the context strategies simple and deterministic. There is no retrieval model or ranking layer yet. The experiment is about comparing explicit context policies, not retrieval quality.

### 5.1 Why abundant is "all documents"

The current implementation defines "abundant" as the entire world folder, not "a large but somewhat relevant subset". This is intentional:

- it maximizes token load
- it maximizes interference from nearby but wrong evidence
- it makes the comparison easy to reason about

The tradeoff is realism. In a production RAG system, abundant context would usually still be filtered. Here, it is intentionally less disciplined to stress-test the hypothesis.

## 6. Prompt construction

Also implemented in:

`app/context_builder.py`

The final prompt contains:

- a system-style framing inside the user prompt
- explicit answer constraints
- the question
- a concatenated context block
- a fixed answer format

Prompt rules currently emphasize:

- use only provided context
- admit lack of evidence
- answer with thesis plus evidence

The prompt builder is intentionally static. This avoids contaminating experimental results with many prompt-template variants.

## 7. Token counting

Implemented in:

`app/token_counter.py`

### 7.1 Counting strategy

The project uses `tiktoken` with:

- `encoding_for_model(model_name)` when possible
- fallback to `o200k_base` when the model name is unknown

This is better than character-count heuristics because it tracks model tokenization more realistically.

### 7.2 Where token counts are used

Tokens are used in three places:

1. prompt token estimation during context construction
2. simulated-mode usage accounting
3. real-mode cost estimation

### 7.3 Important limitation

Prompt token estimation in `ContextPackage.token_estimate` is only an estimate. The authoritative token counts for live API responses come from the provider response when available.

## 8. Cost calculation

Implemented in:

`app/metrics.py`

### 8.1 Current formula

Estimated cost is computed as:

`input_cost = (prompt_tokens / 1_000_000) * input_rate`

`output_cost = (completion_tokens / 1_000_000) * output_rate`

`total_cost = round(input_cost + output_cost, 6)`

### 8.2 Why the calculation uses model choice, not raw model name

The project maps costs by logical role:

- `medium`
- `strong`

This keeps the UI and comparison logic stable even if the underlying real models change.

### 8.3 Current default pricing

Loaded in:

`app/config.py`

Current defaults:

- `medium` -> `gpt-5.4-mini`
  - input: `0.75 / 1M`
  - output: `4.50 / 1M`

- `strong` -> `gpt-5.4`
  - input: `2.50 / 1M`
  - output: `15.00 / 1M`

These are configurable through environment variables and should be treated as deployment-level settings rather than immutable logic.

## 9. LLM execution modes

Implemented in:

- `app/models.py`
- `app/llm_client.py`
- `ui/streamlit_app.py`

There are two execution modes:

### 9.1 Sandbox

Default mode.

- no paid API calls
- no external dependency beyond local code and data
- deterministic enough for demos
- useful for validating the experiment structure and UI

### 9.2 Live

Explicit opt-in mode.

- requires `OPENAI_API_KEY`
- uses an OpenAI-compatible chat completion endpoint
- incurs real token cost

### 9.3 Why sandbox is the default

This is a product-safety decision, not only a dev convenience.

The project should:

- not spend money by accident
- remain demoable offline
- let people understand the experiment before trusting live results

## 10. Live API execution and error handling

Implemented in:

- `app/llm_client.py`
- `app/exceptions.py`
- `app/main.py`
- `ui/streamlit_app.py`

### 10.1 Live request flow

When mode is `live`, `LLMClient.generate(...)`:

1. checks whether a client exists
2. chooses the configured model for `medium` or `strong`
3. sends a low-temperature chat completion request
4. captures:
   - answer
   - prompt tokens
   - completion tokens
   - total tokens
   - latency
   - estimated cost

### 10.2 Supported error classes

The client maps provider/SDK failures into a unified application error:

`ExperimentExecutionError`

Handled cases include:

- missing API key
- authentication failure
- permission denied
- bad request
- rate limit
- insufficient quota / billing exhaustion
- timeout
- connection failure
- unexpected provider status error
- generic unexpected runtime error

### 10.3 Why a custom exception exists

This keeps:

- API responses structured
- UI messaging friendly
- technical details still available in an expandable section

The API returns both:

- a human message
- machine-ish details

This is useful for debugging configuration problems without exposing raw stack traces to the user interface.

## 11. Sandbox simulation logic

Implemented in:

`app/llm_client.py`

The simulated mode is not random text generation. It is a heuristic answer synthesizer designed to mimic the expected behavior of weak vs strong context handling.

### 11.1 How candidate scoring works

For each candidate in `question.scoring.candidate_terms`:

- every candidate term gets counted in the concatenated context
- each occurrence contributes `+1.0`

Then additional strategy/model effects are applied:

- `relevant` adds `+2.0` to the expected entity
- `minimum` adds `+0.4`
- `none` adds `+0.1`
- `strong` model adds `+1.2` to the expected entity

For `abundant` + `medium`:

- every non-target candidate gets `+0.8`

This deliberately models confusion under noisy context.

### 11.2 Why the simulation is biased this way

The sandbox is designed to demonstrate the hypothesis:

- relevant context should be easier to solve
- abundant noisy context should be riskier, especially for the weaker model

This is not intended as a faithful behavioral emulator of a frontier model. It is a controlled experimental stand-in.

### 11.3 Output shaping in simulation

The simulator chooses among three broad answer styles:

- explicit uncertainty under `none`
- partial-but-insufficient under weak `minimum`
- either correct synthesis or plausible misread under richer contexts

This keeps the demo pedagogically useful even without network access.

## 12. Evaluation model

Implemented in:

`app/evaluator.py`

The evaluator is heuristic and rubric-based. It is not a semantic grader.

### 12.1 Normalization

All string comparisons use a simple normalized representation:

- lowercase/casefold
- collapsed whitespace

This makes matching robust to minor formatting differences.

### 12.2 Base scoring dimensions

All cases use:

- entity identification
- required-term evidence match
- bonus-term match
- hallucination detection

### 12.3 Base score structure

The evaluator computes:

- `entity_score`
- `evidence_score`
- `adherence_score`
- `hallucination_penalty`

Then:

`quality_score = clamp(entity_score + evidence_score + adherence_score - hallucination_penalty, 0, 100)`

### 12.4 Standard-case behavior

For simpler cases:

- entity match gives `40`
- evidence score is up to `30`
- adherence score is up to `20`, plus `10` if entity matches
- hallucination penalty is `5 * hallucinated_terms`, capped at `15`

### 12.5 Extended rubric behavior for complex cases

Case 4 required richer scoring, so the evaluator now supports:

- `rubric_checks`
- `false_leads`
- `rejection_markers`
- `uncertainty_markers`

For rubric-enabled cases:

- entity score is reduced to `20`
  - this avoids over-rewarding merely naming the central faction
- rubric checks add weighted evidence score
  - total evidence score capped at `60`
- adherence can be boosted for:
  - showing uncertainty where appropriate
  - explicitly rejecting false leads
- hallucination penalty is expanded:
  - hallucinated terms still count
  - accepted false leads also count
  - total penalty capped at `30`

### 12.6 False-lead logic

The evaluator splits the answer into segments and checks whether false-lead terms are mentioned in a segment containing rejection markers such as:

- `boato`
- `sem evidência`
- `hipótese alternativa`
- `insuficiente`

If a false lead is mentioned without explicit distancing language, it is treated as accepted.

This is intentionally heuristic. It rewards the behavior the experiment cares about:

- distinguishing signal from noise
- not merely listing every plausible suspect as equivalent

### 12.7 Notes generated by the evaluator

The evaluator also produces human-readable notes, used in the UI:

- whether the expected entity was identified
- whether key terms were present
- whether rubric checks were satisfied
- whether hallucinations appeared
- whether false leads were rejected or accepted
- whether a no-context answer appropriately admitted uncertainty

## 13. Why the evaluation is heuristic, not model-graded

This is a deliberate design choice.

Reasons:

- lower cost
- deterministic behavior
- easier debugging
- easier to explain in demos
- better isolation of the context hypothesis from grader-model variance

Tradeoff:

- it is stricter and narrower than human evaluation
- it may miss semantically correct paraphrases
- it can overvalue explicit terminology

The project currently prioritizes interpretability over nuance.

## 14. Persistence and database decisions

Implemented in:

`app/metrics.py`

### 14.1 Storage model

Every experiment run is persisted to SQLite in `experiment_runs`.

Stored fields include:

- metadata
- strategy
- model choice
- evaluation scores
- tokens
- estimated cost
- latency
- provider/model name
- answer text
- context documents
- full evaluation payload

### 14.2 Database path resolution

The configured DB path is checked first.

If it cannot be written:

- the app falls back to `%TEMP%/context_lab.db`

This was added to make the app resilient in environments where the expected workspace path is not writable from the current runtime.

### 14.3 Why all runs are kept

The database now preserves the full history. The UI shows only a recent subset on the home and experiments pages, while the history page can display the entire run history.

This separation preserves both:

- lightweight recent context
- deeper auditability

## 15. Orchestration flow

Implemented in:

`app/experiment_service.py`

For every run:

1. load question spec
2. build context package
3. generate answer via `LLMClient`
4. evaluate answer heuristically
5. persist result
6. return structured `ExperimentResponse`

This service is the orchestration boundary used by both FastAPI and Streamlit.

## 16. API surface

Implemented in:

`app/main.py`

Current endpoints:

- `GET /health`
- `GET /questions`
- `GET /results/recent`
- `POST /experiment`

The API is intentionally small. It is sufficient for:

- listing available experiment cases
- triggering runs
- reading recent results

## 17. Streamlit UI design

Implemented in:

`ui/streamlit_app.py`

### 17.1 Navigation model

The app uses a 3-page session-state-driven layout:

- home
- experiments
- history

This avoids the confusion caused by inline toggling or pseudo-modal sections.

### 17.2 Experiment modes in UI

The experiments page supports:

- unitário
- comparativo 4 estratégias
- comparativo modelos x estratégias

The config sidebar enables or disables controls based on experiment type:

- single: model and strategy enabled
- full comparison: strategy disabled
- matrix comparison: model and strategy disabled

### 17.3 Result rendering choices

Results are shown as bordered cards to improve scanability.

Each card includes:

- answer text
- metrics
- context used
- assembled prompt
- evaluation notes

This design reflects a deliberate UX decision:

- keep the narrative answer visible
- let technical details stay available but collapsed

### 17.4 History design

There are two layers:

- recent history on home and experiments
- full history on dedicated history page

This balances quick monitoring and full auditability.

### 17.5 Progress feedback

To handle live-mode latency:

- single runs show a basic execution state
- multi-run comparisons show incremental progress by completed run count

This is not streaming token-level progress from the API. It is run-level progress, which is the best practical representation given the current sequential orchestration.

## 18. Case design philosophy

Each case is meant to answer a different version of the same hypothesis:

- Case 1: clear incentive chain
- Case 2: access/opportunity chain
- Case 3: location/safety reasoning
- Case 4: multi-document investigative synthesis under noise

Case 4 ("Operação Fantasma") is especially important because it pushes the boundary where abundant context can begin to hurt, not just fail to help.

Design ingredients added for that case:

- true multi-step causal chain
- at least three plausible false chains
- overlapping names
- temporal overlap
- partially true rumors
- contradictory and distracting evidence
- explicit need to separate evidence from speculation

## 19. Key product and research decisions

### 19.1 Why the domain is generic tabletop fantasy

Using a system-agnostic RPG domain avoids contamination from:

- benchmark familiarity
- strong prior model knowledge of official settings
- ruleset-specific assumptions

### 19.2 Why all world content is local markdown

Markdown keeps the content:

- readable
- editable
- diffable
- easy to reason about in context selection experiments

### 19.3 Why questions include explicit relevant document lists

This is central to the experiment.

The system needs a ground-truth definition of what "relevant context" means for each question. Otherwise, comparisons between strategies would become ambiguous.

### 19.4 Why the UI uses logical roles (`medium`, `strong`)

This separates experiment design from provider naming.

You can swap:

- `gpt-4.1` to `gpt-5.4`
- `gpt-4.1-mini` to `gpt-5.4-mini`

without rewriting the analysis logic or visual vocabulary.

### 19.5 Why costs are estimated locally even in simulation

Even sandbox mode reports token counts and estimated cost. This keeps:

- dashboards consistent
- comparative outputs visually aligned
- the user focused on the same metrics in both offline and live runs

## 20. Current limitations

The project is useful, but intentionally lightweight. Important limitations:

- no retrieval engine beyond explicit strategy selection
- no semantic grading model
- no streaming live results into cards as each run finishes
- no experiment export yet
- no automatic regression test suite for case validity
- no per-question custom prompt templates
- no versioned schema migrations for SQLite

For Case 4 specifically:

- false-lead rejection is still string-heuristic, not true reasoning verification
- answers can be semantically right but under-scored if they avoid expected terminology

## 21. How to extend the project safely

### 21.1 Adding a new question

To add a new case:

1. create or adapt world documents
2. add a new question object to `data/questions.json`
3. define:
   - `relevant_documents`
   - `expected_answer`
   - `scoring`
4. validate that the question loads through `QuestionSpec.model_validate(...)`

### 21.2 Adding more advanced rubrics

If a question requires richer evaluation:

- add `rubric_checks`
- define `false_leads`
- add `rejection_markers`
- add `uncertainty_markers`

This is the recommended pattern for complex synthesis cases.

### 21.3 Changing pricing or providers

Use environment variables rather than hardcoding:

- `MODEL_MEDIUM`
- `MODEL_STRONG`
- price-per-million variables
- `OPENAI_BASE_URL`
- provider metadata

## 22. Recommended future improvements

High-value next steps:

- add a formal docs page in the UI explaining score composition
- add export of full run history to CSV/JSON
- show progress and partial render as each comparison item completes
- add offline regression tests that assert expected rank ordering:
  - `relevant >= abundant` for chosen cases
  - `minimum < relevant`
  - `none` remains cautious
- add a richer analyst report per question:
  - cost delta
  - score delta
  - token efficiency
- optionally add a fifth strategy:
  - `retrieved_relevant`

## 23. Summary

The project is intentionally small but conceptually disciplined.

Its core value comes from:

- controlled context strategies
- explicit ground-truth relevance per question
- low-ceremony local data
- interpretable heuristic evaluation
- side-by-side comparison of quality, tokens, latency, and cost

The strongest design choice in the project is that it treats context not as "more text", but as an experimental variable with measurable tradeoffs.
