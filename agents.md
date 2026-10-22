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

# Planned commands
- `python -m src.main` — planned, not implemented yet.
- `streamlit run app.py` — planned, not implemented yet.

# Environment names
- `OPENAI_API_KEY`.
- `OPENAI_MODEL`.
- Never invent a model ID; use the configured value only.

# Repo map
- `src/document_processor.py` — ingest Markdown fixtures and preserve source metadata.
- `knowledge_base/primary/` — verified primary Patagonia Markdown sources.
- `knowledge_base/secondary/` — secondary trend/competitor Markdown sources.
- `src/knowledge_base.py` — deterministic context assembly and source selection.
- `src/llm_integration.py` — configurable OpenAI client and usage capture.
- `src/prompt_templates.py` — prompt assembly for the three channels.
- `templates/instagram.md` — Instagram template.
- `templates/linkedin.md` — LinkedIn template.
- `templates/email.md` — email template.
- `src/content_pipeline.py` — generation, feedback, approval, and export flow.
- `src/main.py` — CLI entry point.
- `app.py` — Streamlit UI entry point.
- `outputs/` — exported approved content.
- `docs/evaluation/` — generic-versus-contextual comparisons and preserved evidence.
- `docs/evidence/` — Day 1 and Day 2 board screenshots and other evidence.
- `docs/presentation/` — final demo and five-slide presentation materials.
- `rag_decision.md` — provisional context-injection versus RAG decision record.

# Conventions
- Read this root `agents.md` explicitly before each task.
- Use English for all files and comments.
- Use `snake_case` for Python names.
- Keep Markdown KBs with source metadata intact.
- Do not fabricate facts, claims, APIs, or output values.
- Do not read or display secrets unless specifically required and authorized; never log keys.
- Do not overwrite another contributor’s work.
- Do not stage, commit, push, deploy, or expand scope without the project owner’s explicit permission.
- Human action is required for approval/export of approved content.
- The third teammate reviews or pairs; maximum two active cards team-wide.
- Each coding task must be tied to one Trello card, the relevant Must IDs, and a clearly assigned file scope.

# Definition of done
- Artifacts required by the Trello card are present.
- Planned verification for the card passes.
- Peer review is completed.
- The change and its verification are recorded on the card.
- No secrets are committed.
