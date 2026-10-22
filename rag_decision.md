# RAG decision

## Terms
- **Proposed non-RAG context injection:** fixed, deterministic file and section inclusion without query-based retrieval.
- **RAG:** query-based retrieval, including keyword retrieval without embeddings.
- **Vector stores:** optional; they are not mandatory for RAG.

## Provisional position
- Start with proposed non-RAG context injection because the project begins with a small, curated Markdown corpus and a two-day schedule.
- This keeps source selection explicit, reviewable, and easy to compare against a generic baseline.
- Revisit the architecture only when measured evidence shows the current approach no longer fits the corpus or workflow.

## Decision factors
- **Corpus size and structure:** more documents, deeper hierarchies, or overlapping content increase the need for retrieval.
- **Update frequency:** if Markdown sources change often, retrieval may reduce manual curation work.
- **Query diversity:** more varied user requests increase the chance that fixed inclusion becomes inefficient or incomplete.
- **Context limits:** prompt size, token usage, and latency can make fixed inclusion too expensive or too brittle.
- **Implementation complexity:** the team should prefer the simplest architecture that still preserves factual grounding.

## Measurement table
| Metric | Value | Collection method |
|---|---|---|
| Document count per KB | not measured yet | Count Markdown files in `knowledge_base/primary/` and `knowledge_base/secondary/`. |
| Total corpus size | not measured yet | Sum bytes or tokens across both KB folders after ingestion. |
| Prompt token usage for the selected model | not measured yet | Record prompt and completion token counts from the OpenAI response when available. |
| API latency | not measured yet | Time the request from send to first complete response. |
| API usage/cost when calculable | not measured yet | Capture usage fields and convert with the selected model’s pricing if available. |

## Revisit conditions
- Revisit the architecture if the corpus grows enough that repeated context assembly becomes unwieldy.
- Revisit it if update frequency or request diversity makes deterministic inclusion hard to maintain.
- Revisit it if token usage, latency, or maintenance cost becomes unacceptable for the team’s workflow.
- Revisit it only after measurements are collected and compared against the generic baseline.

## Current status
- No corpus measurements have been taken yet.
- No generic-versus-contextual comparison has been completed yet.
- No retrieval layer has been implemented yet.
- No deployment, API call, or code change is performed by this planning decision alone.
