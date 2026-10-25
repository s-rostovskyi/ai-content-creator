# Purpose
- Root coding-agent instructions for this project; read this file before each task and align work to `project_structure.md` and Must IDs M1-M8.
- This repository is a Python/Streamlit educational prototype with Markdown knowledge bases, OpenAI API integration, and human review for approved content.

# Planned stack
- Python 3.14.7 (verified from the active interpreter).
- Python.
- Streamlit.
- OpenAI API.
- Markdown parsing.
- `python-dotenv`.

# Run commands
- `python -m src.main --channel <channel> --brief "..." [--dry-run]` - implemented and verified for dry-run; live mode supports manual review, explicit approval, and export.
- `python -m streamlit run app.py` - implemented; the local UI supports channel switching, draft editing, validation, approval, export, and the preserved acceptance evidence covers Instagram, LinkedIn, and email.
- `python scripts/generic_vs_contextual_eval.py [--live] [--runs-dir ...]` - dry-run is the default; `--live` performs the six-request comparison and writes to `docs/evaluation/runs/`.
- `python scripts/build_rag_index.py [--live]` - dry-run is the default; preview shows the planned corpus snapshot, chunk counts, reusable embeddings, missing embeddings, and API batch plan before any build runs.
- `python scripts/retrieve_rag_context.py [--live] [--save-evidence <path>] --channel <channel> --brief "..."` - dry-run is the default; live mode performs retrieval and optional evidence export.

# Environment names
- `OPENAI_API_KEY`.
- `OPENAI_MODEL`.
- `OPENAI_EMBEDDING_MODEL`.
- `SOURCE_MANAGEMENT_ENABLED`.
- The application key is owner-funded and local to the environment; it is separate from Codex authentication and must not be committed.
- Never invent a model ID; use the configured value only.

# Repo map
- `src/product_catalog.py` - two prepared product profiles, default briefs and explicit source assignments.
- `src/document_processor.py` - ingest Markdown fixtures and preserve source metadata.
- `knowledge_base/primary/` - verified primary Patagonia Markdown sources.
- `knowledge_base/secondary/` - secondary trend and competitor Markdown sources.
- `src/knowledge_base.py` - deterministic context assembly and source selection.
- `src/campaign_brief.py` - curated source snapshot, editorial angles, and brief preparation.
- `src/llm_integration.py` - configurable OpenAI client and usage capture.
- `src/embedding_integration.py` - configurable OpenAI embeddings client and usage capture.
- `src/prompt_templates.py` - prompt assembly for the three channels.
- `src/content_validation.py` - deterministic channel-format feedback.
- `src/content_pipeline.py` - generation, feedback, approval, and export flow.
- `src/main.py` - CLI entry point.
- `app.py` - Streamlit UI entry point.
- `scripts/generic_vs_contextual_eval.py` - evaluation runner entry point.
- `src/evaluation_runner.py` - evaluation orchestration.
- `src/rag_chunking.py` - heading-aware chunking for RAG corpora.
- `src/rag_index.py` - persistent local SQLite vector index and readiness checks.
- `src/rag_retrieval.py` - hybrid factual-first retrieval with bounded context assembly.
- `src/rag_service.py` - index preview/build and retrieval orchestration.
- `src/rag_context_provider.py` - backend context provider for explicit RAG generation and revision.
- `scripts/build_rag_index.py` - offline index preview/build CLI.
- `scripts/retrieve_rag_context.py` - offline retrieval CLI.
- `templates/instagram.md` - Instagram template.
- `templates/linkedin.md` - LinkedIn template.
- `templates/email.md` - email template.
- `outputs/` - exported approved content.
- `docs/evaluation/` - generic-versus-contextual comparisons and preserved evidence.
- `docs/evidence/` - Day 1 and Day 2 board screenshots, channel acceptance evidence, and other evidence.
- `docs/presentation/` - final demo and five-slide presentation materials.
- `rag_decision.md` - provisional context-injection versus RAG decision record.

# Conventions
- Read this root `agents.md` explicitly before each task.
- Use English for all files and comments.
- Use `snake_case` for Python names.
- Keep Markdown KBs with source metadata intact.
- Do not fabricate facts, claims, APIs, or output values.
- Do not read or display secrets unless specifically required and authorized; never log keys.
- Do not overwrite another contributor's work.
- Do not stage, commit, push, deploy, or expand scope without the project owner's explicit permission.
- Human action is required for approval and export of approved content.
- The third teammate reviews or pairs; maximum two active cards team-wide.
- Each coding task must be tied to one Trello card, the relevant Must IDs, and a clearly assigned file scope.
- Fresh clones need a compatible `.rag` index (explicitly built, or restored from a validated prepared seed) before UI RAG generation or revision can run.
- Prepared product sessions use source filtering before ranking, require selected-product factual evidence, and retain separate channel/editor/approval/export state per product. New source uploads are excluded until deliberately assigned in `src/product_catalog.py`. Never transfer product facts between styles.

# Definition of done
- Artifacts required by the Trello card are present.
- Planned verification for the card passes.
- Peer review is completed.
- The change and its verification are recorded on the card.
- No secrets are committed.
