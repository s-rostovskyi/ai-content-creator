# Evidence map

| Presentation claim / slide | Source of truth | Evidence status |
|---|---|---|
| Product goal, channels, exclusions | `project_structure.md`, `AGENTS.md` | Implemented/project-defined |
| Quality / Time / Cost | `project_structure.md` | Project plan; USD 5 is agreed budget, not billing enforcement |
| Stakeholders and names | `project_structure.md` | Documented names only: Sergii, Sandra, Martha |
| WBS and WIP rule | `project_structure.md` | Documented plan |
| Primary/secondary KB split | `knowledge_base/README.md`, `knowledge_base/primary/`, `knowledge_base/secondary/` | Implemented |
| Markdown metadata and section parsing | `src/document_processor.py` | Implemented |
| Deterministic context assembly | `src/knowledge_base.py`, `rag_decision.md` | Implemented; no query-based retrieval |
| RAG decision | `rag_decision.md` | Implemented decision record; revisit conditions defined |
| LLM configuration and usage capture | `src/llm_integration.py`, `.env.example` | Implemented; secrets not read |
| Channel templates and constraints | `templates/*.md`, `src/prompt_templates.py` | Implemented |
| Review, revision, approval and export | `src/content_pipeline.py`, `app.py`, `src/main.py` | Implemented |
| Streamlit live verification status | `AGENTS.md`, `docs/evidence/day1-status.md` | Instagram manually verified; LinkedIn/email pending |
| Generic vs contextual comparison | `docs/evaluation/uniqueness-evaluation.md`, `docs/evidence/day1-smoke-test.json` | Offline fixture comparison; not a live benchmark |
| Day 1 board evidence | `docs/evidence/p2-kanban-day1.png`, `docs/evidence/p2-kanban-day1-dod.png` | Actual screenshot embedded from repository |
| Day 1 test count and smoke test | `docs/evidence/day1-status.md`, `rag_decision.md` | 62 offline tests; one live Instagram smoke test |
| Day 2 board evidence | `project_structure.md` references it, but no `p2-kanban-day2.png` was found | Missing |
