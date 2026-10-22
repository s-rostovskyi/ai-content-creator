# 1. Project identity
- **Project name:** Patagonia Content Studio.
- **Type:** two-day applied R&D / educational prototype.
- **Goal:** deliver an English-only Patagonia content studio in Python/Streamlit that drafts Instagram, LinkedIn, and email newsletter content from curated Markdown knowledge bases, then routes output through human review, revision, and export without inventing facts.
- **Dates:** October 22–23, 2026.
- **Initial product:** Patagonia Men's Nano Puff® Jacket, style 84212.
- **Canonical source:** https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html
- **Market/source scope:** US website, English content.
- **Channels:** Instagram, LinkedIn, email newsletter.
- **Initial use case:** a marketing team enters a campaign brief and receives three channel-specific drafts grounded in verified product and industry sources, with human review, revision and approval.
- **Excluded scope:** live prices, discounts, availability, unsupported performance claims, and facts from other styles/seasons.
- **Characteristics:**
  - Defined goal.
  - Limited resources.
  - Interdisciplinary.
  - Responsibility for results.
  - Complex.
  - Novel.
  - Defined start/end.

# 2. Objectives (Quality / Time / Cost)
- **Quality:** outputs remain grounded in verified Patagonia source notes, channel tone is distinct per format, and reviewers can trace every significant claim back to the knowledge base.
- **Quality:** the UI makes each state obvious so the workflow is usable for non-builders and easy to demo.
- **Time:** finish a working end-to-end demo by Day 2 while keeping at most two active cards across the team and using pair/review work to avoid overload.
- **Cost:** keep the model configurable, bound generation and revision calls, and record token/usage data when the API returns it; shared team API budget is **USD 5** for the two-day project.
- **Cost:** model preset is `gpt-5.4-mini`, configurable through `OPENAI_MODEL`.
- **Cost:** shared team API budget is USD 5 for October 22–23, 2026; this is an agreed spending budget, not an already implemented or guaranteed billing cap.
- **Cost:** corpus measurements remain marked as not measured.
- **Milestone - Day 1:** both Markdown KBs are ingested and one real OpenAI response is produced using their context.
- **Milestone - Day 2:** deliver the end-to-end demo, review flow, exported approved content, and presentation evidence.

# 3. Stakeholder analysis
- **Quadrant mapping:** I = high interest / high influence; II = low interest / high influence; III = high interest / low influence; IV = low interest / low influence.

| Role | Interest | Influence | Quadrant | Engagement |
|---|---|---|---|---|
| Sergii, technical lead | H | H | I | Owns architecture, ingestion, context selection, OpenAI integration, and delivery risk control. |
| Sandra, primary KB owner | H | H | I | Curates primary Markdown knowledge base and channel prompt templates; pairs on claim safety and tone. |
| Martha, evaluation/usability reviewer | H | H | I | Checks content quality, usability, and whether the workflow is understandable for the team. |
| Hypothetical Patagonia marketing approver | H | H | I | Non-builder client persona; validates brand fit, factual discipline, and whether outputs are acceptable. |
| Course instructor | H | H | I | Reviews feasibility, Trello discipline, and whether the two-day scope stays realistic. |

# 4. Requirements → implementation
- **Use case:** the team needs a small, reviewable content studio that can take verified Patagonia source material, assemble bounded context, generate channel-specific drafts, and support human approval before export.
- **Won’t:** no automated social publishing; no auth, database, scheduling, or vector database unless measurement proves they are necessary.

| Must | Proposed files | Planned check |
|---|---|---|
| **M1 — Both Markdown KBs ingested with source metadata** | `src/document_processor.py`, `knowledge_base/primary/`, `knowledge_base/secondary/` | Planned check: all fixture files from both folders load and sections retain source/file/heading metadata. |
| **M2 — Bounded deterministic context assembly using both KBs** | `src/knowledge_base.py` | Planned check: repeatable source selection for three requests, both KBs represented, and explicit handling of oversized context. |
| **M3 — Real configurable OpenAI integration** | `src/llm_integration.py` | Planned check: real response, missing-key/API errors, model configuration, and usage when available. |
| **M4 — Three channel templates** | `src/prompt_templates.py`, `templates/instagram.md`, `templates/linkedin.md`, `templates/email.md` | Planned check: channel constraints and no unresolved placeholders. |
| **M5 — CLI and web generation, feedback/revision, human approval and export** | `src/content_pipeline.py`, `src/main.py`, `app.py`, `outputs/` | Planned check: full workflow including refusal to mark a draft approved without human action, and UI loading/empty/error/success states. |
| **M6 — Actual generic-versus-contextual comparisons** | `docs/evaluation/` | Planned check: preserved requests, prompts, settings, real raw outputs, and source-grounded review for all three channels using the same model. |
| **M7 — Defensible RAG decision** | `rag_decision.md` | Planned check: at least three architectural criteria, actual corpus measurements when available, and revisit conditions. |
| **M8 — Planning, agent workflow and submission evidence** | `project_structure.md`, `agents.md`, `README.md`, `requirements.txt`, `docs/evidence/`, `docs/presentation/` | Planned check: required sections, actual agent usage, real Day 1/Day 2 screenshots, demo, and five-slide presentation. |

# 5. WBS (2 levels)
Treat each leaf as a Trello card with review and evidence captured in the card. Planning closure precedes development cards: card 1.1 must be peer reviewed and board-aligned before any 2.x–6.x card starts.

1. **Planning**
   1.1 **Planning files and board alignment** — Owner: Sergii; Reviewer: Martha; Must: M8; Dependencies: none; Verification: project_structure.md, agents.md, and the board rules are aligned; planning closure is recorded before any development card starts; Day 1/Day 2 target: **D1 AM**.
2. **Knowledge bases**
   2.1 **Primary KB** — Owner: Sandra; Reviewer: Martha; Must: M1; Dependencies: none; Verification: Markdown structure, source URLs, access dates, factual grounding, and primary/secondary separation are reviewed for the primary KB; Day 1/Day 2 target: **D1 AM**.
   2.2 **Secondary KB** — Owner: Martha; Reviewer: Sandra; Must: M1; Dependencies: none; Verification: Markdown structure, source URLs, access dates, factual grounding, and primary/secondary separation are reviewed for the secondary KB; Day 1/Day 2 target: **D1 AM**.
3. **Ingestion and context**
   3.1 **Markdown ingestion** — Owner: Sergii; Reviewer: Sandra; Must: M1; Dependencies: 2.1, 2.2; Verification: loader integration is verified when both KB folders ingest successfully with metadata preserved; Day 1/Day 2 target: **D1 PM**.
   3.2 **Context assembly and RAG assessment** — Owner: Sergii; Reviewer: Martha; Must: M2, M7; Dependencies: 3.1; Verification: repeatable source selection for three requests, both KBs represented, and oversized context is handled explicitly; Day 1/Day 2 target: **D1 PM**.
4. **Generation**
   4.1 **OpenAI client** — Owner: Sergii; Reviewer: Martha; Must: M3; Dependencies: none; Verification: real response, missing-key/API errors, model configuration, and usage when available; Day 1/Day 2 target: **D1 PM**.
   4.2 **Three channel templates** — Owner: Sandra; Reviewer: Martha; Must: M4; Dependencies: 2.1, 2.2; Verification: Instagram, LinkedIn, and email templates enforce channel constraints and contain no unresolved placeholders; Day 1/Day 2 target: **D1 PM**.
   4.3 **Pipeline, feedback, approval and export** — Owner: Sergii; Reviewer: Sandra; Must: M5; Dependencies: 3.2, 4.1, 4.2; Verification: full workflow works and a draft cannot be marked approved without human action; Day 1/Day 2 target: **D2 AM**.
5. **Interface and evaluation**
   5.1 **Streamlit interface** — Owner: Sergii; Reviewer: Martha; Must: M5; Dependencies: 4.3; Verification: loading, empty, error, and success states appear in the UI; Day 1/Day 2 target: **D2 AM**.
   5.2 **Uniqueness evaluation** — Owner: Martha; Reviewer: Sandra; Must: M6; Dependencies: 4.1, 4.2, 4.3; Verification: generic-versus-contextual comparisons are preserved with requests, prompts, settings, raw outputs, and source-grounded review for all three channels using the same model; Day 1/Day 2 target: **D2 AM**.
6. **Delivery**
   6.1 **Deployment attempt and runtime verification** — Owner: Sergii; Reviewer: Martha; Must: M5, M8; Dependencies: 5.1; Verification: optional deployment is attempted and runtime behavior is checked, but failure does not block final delivery; Day 1/Day 2 target: **D2 PM**.
   6.2 **Final docs, demo and presentation** — Owner: Martha; Reviewers: Sergii and Sandra; Must: M7, M8; Dependencies: 5.1, 5.2; Verification: docs, demo, real Day 1/Day 2 screenshots (`docs/evidence/p2-kanban-day1.png`, `docs/evidence/p2-kanban-day2.png`) as independent checkpoints, and the five-slide presentation are complete; Day 1/Day 2 target: **D2 PM**.

# 6. Risks
| Risk | Probability | Impact | Strategy | Concrete response |
|---|---|---|---|---|
| Unsupported or stale claims | M | H | Reduction | Keep claims source-grounded, require peer review, and block approval if a statement cannot be traced to the KB. |
| API availability/cost problems | M | H | Mitigation | Keep model choice configurable, cap generation/revision calls, log usage when available, and fall back to saved comparison artifacts if the API is unstable. |
| Scope/WIP bottlenecks | H | H | Reduction | Keep only two active cards, pair on risky work, cut stretch tasks early, and protect the Day 2 demo path. |

# 7. Bridge to RAG decision
Marketing quality needs require source-grounded content, but the first architecture choice is still bounded deterministic context assembly (M1/M2/M7) rather than query-based retrieval. Corpus size and structure, update frequency, request diversity, and context limits should decide whether the planned non-RAG approach remains sufficient or whether query-based retrieval becomes justified. The team should measure prompt token usage, API latency, and the review burden for repeated requests before expanding scope. If the corpus stays small and stable, fixed file/section inclusion may remain the best option; if the corpus grows, updates become frequent, or request diversity increases, retrieval may improve maintainability despite cost and latency. Poor generation quality alone is not enough to prove retrieval is required. Use the measured evidence, not assumptions, to decide whether to revisit the architecture.
