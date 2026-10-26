# Patagonia Content Studio

## Delivery brief

- Owner: Martha
- Trello card: 6.2, Final docs, demo and presentation
- Must IDs: M7, M8
- Format: exactly five slides
- Speaking time: 7 minutes total
- Questions: reserve 2–3 minutes after slide 5
- Evidence note: the synchronized checkout predates the later live RAG browser verification. The outline uses Sandra's `presentation-evidence.md` and the owner-confirmed RAG update as the current presentation evidence.

## Slide 1 — Patagonia Content Studio

**Timing:** 0:45

**Speaker:** Martha

**Slide text**

> **Patagonia Content Studio**  
> A grounded generator for Instagram, LinkedIn and email

Small footer:

> Sergii Rostovskyi | Sandra Obregon | Martha Olukayode

**Speaker notes**

- Frame the project as a company brand generator with one workflow for three channel formats.
- The product goal is a reviewable English-language studio that drafts content from curated Patagonia source material without inventing facts.
- Introduce the team and the goal: a reviewable company brand generator for three channel formats.

**Evidence / visual slot**

- Use the final project title treatment.
- Reserve a small status callout for the final RAG status supplied by Martha/Sandra. Do not present it as completed until the evidence pack confirms it.

## Slide 2 — Problem

**Timing:** 1:15

**Speaker:** Martha, with Sandra for the KB point

**Slide text**

> **The content problem has two failure modes**

- Generic copy sounds interchangeable and gives the reviewer little to verify.
- Fast generation can blur product facts, secondary context and editorial interpretation.
- Three channels need different formats, not one caption copied three ways.

> **Q/T/C**
>
> **Quality:** source-grounded claims, channel fit, traceable review notes  
> **Time:** a working end-to-end demo by Day 2 with WIP capped at 2  
> **Cost:** configurable model and bounded calls within the agreed USD 5 team budget; no cost result is claimed here

**Speaker notes**

- Connect the problem to the project structure: the team needed a small, reviewable content studio with a human approval step.
- Highlight the top risk to foreground: unsupported or stale claims. The control is primary-source grounding, explicit limitations, peer review, and a human approval gate.
- Show the stakeholder quadrant briefly: the project structure places Sergii, Sandra, Martha, the hypothetical Patagonia approver and the instructor in Quadrant I, high interest and high influence. This explains why technical, editorial, usability and assessment evidence all matter.
- Do not claim that the application eliminates generic language or guarantees factual safety. It creates reviewable controls and evidence.

**Evidence / visual slot**

- Optional small stakeholder quadrant based on `project_structure.md`.
- Keep the Q/T/C wording visible; do not add unsupported performance or cost claims.

## Slide 3 — Solution

**Timing:** 1:30

**Speaker:** Sandra, with Martha for evaluation

**Slide text**

> **Curated sources become channel-specific drafts**

1. Primary Markdown KB: Patagonia facts and source metadata
2. Secondary Markdown KB: trends and competitor context for positioning only
3. Markdown loader preserves source, heading and metadata boundaries
4. Prompt templates create distinct Instagram, LinkedIn and email output shapes
5. Pipeline separates channel copy from reviewer notes, then requires human approval before export

> **Current RAG:** OpenAI embeddings + local SQLite index + hybrid factual-first retrieval; source upload/edit/delete UI
>
> **Tradeoffs:** targeted evidence selection | source/version updates | context cost and implementation complexity

**Speaker notes**

- Explain the architecture progression. The original small, stable corpus justified deterministic full-context injection. Owner-authorized mutable sources and the need for targeted evidence selection motivated the current RAG direction.
- Current confirmed RAG status: OpenAI embeddings, a local SQLite index and hybrid factual-first retrieval are implemented. The source UI supports upload, edit and delete, with retrieval provenance preserved.
- Sergii performed the real RAG browser verification. One live Instagram RAG draft was generated, manually reviewed and edited, approved and exported. The verification checked revision 3 Markdown/JSON equality, the approval fingerprint and preserved retrieval provenance.
- Defend the current RAG with explicit tradeoffs: targeted evidence selection improves fit to a request but adds retrieval logic; source/version updates improve maintainability but add source-management responsibility; context cost and implementation complexity must be measured rather than assumed away.
- Do not claim that RAG was required for full credit, lower cost or higher accuracy. Other-channel RAG acceptance, live RAG revision and final deployment are not established.
- Use Sandra's exact matched excerpts for the historical comparison. It is one qualitative sample per channel, not statistical proof.

**Evidence / visual slots**

- Sandra’s evidence pack: primary/secondary source examples and metadata screenshot.
- Final RAG status/provenance visual: use Sergii's verified Instagram browser evidence when available.
- Do not show the historical comparison as a RAG benchmark or as a comparison with the ChatGPT product.

## Slide 4 — Live demo

**Timing:** 2:15

**Speaker:** Sergii for the app, Martha for the review decision

**Slide text**

> **One brief, one grounded draft, one human review path**

Demo sequence:

1. Enter an Instagram brief in Streamlit.
2. Generate exactly one Instagram draft live with RAG retrieval.
3. Point out the channel copy, separate reviewer notes and preserved retrieval provenance.
4. Manually edit that draft once.
5. Approve the exact edited revision and show Markdown/JSON export.

Other channels:

> Show their preserved state only. Do not make extra live calls.

Fallback:

> If the API fails, use the saved verified artifact and narrate the same review, approval and export path.

Side-by-side evidence callout:

> **Without supplied sources:** “Built to pack down easily, it’s designed with convenience in mind”  
> **Full-context injection:** “The internal zippered chest pocket that doubles as a stuffsack”

Small label:

> Without supplied sources vs full-context injection — historical non-RAG comparison

**Speaker notes**

- Sergii performs the single live browser generation. Use the approved demo brief and do not promise a particular model response.
- Show that reviewer notes preserve source paths, facts used, interpretations, limitations and retrieval provenance. Keep those notes separate from publishable copy.
- Show the human gate: manual edit, approval of the exact current revision, then Markdown/JSON export. The owner-confirmed verification checked revision 3 Markdown/JSON equality and the approval fingerprint.
- If the API fails, use the saved verified artifact. Do not make extra live calls for LinkedIn or email.
- Read the exact matched excerpts aloud and label the experiment **Without supplied sources vs full-context injection — historical non-RAG comparison**. Do not call it a RAG benchmark or a comparison with the ChatGPT product.
- Sandra's preserved format observations: Instagram generic 70 words and contextual 81 words, both marked OK; LinkedIn generic 116 words below the 120-word minimum and contextual 135 words marked OK; email generic 107 words and contextual 133 words under the 150-word minimum under the clarification convention. This is one qualitative sample per channel, not statistical proof. Do not add scores.

**Evidence / visual slots**

- Final UI screenshots: reserve a slot for the final Streamlit generation, review and approval/export states.
- Live RAG Instagram evidence: reserve a slot for Sergii's verified run, retrieved facts, limitations and provenance.
- Sandra's exact excerpts: use the preserved artifact references for the side-by-side comparison.

## Slide 5 — Key takeaways

**Timing:** 1:15

**Speaker:** Martha, closing with Sandra and Sergii available for questions

**Slide text**

> **What we can defend today**

- The team built a reviewable multi-channel Patagonia content workflow around primary and secondary Markdown knowledge bases.
- The pipeline separates facts, interpretation and reviewer notes, with human approval before export.
- The historical comparison shows a concrete difference between broad convenience language and a verified style-84212 construction detail. It is a historical non-RAG comparison, not a RAG benchmark.
- Current RAG includes embeddings, a local SQLite index, hybrid factual-first retrieval and mutable-source UI. One live Instagram draft reached manual edit, approval and export; other-channel acceptance, live RAG revision and final deployment remain unestablished.

> **How the team worked**

> Day 1: plan, source, ingest and smoke-test  
> Day 2: pipeline, UI, evaluation and delivery evidence  
> WIP = 2 | Definition of Done: artifact, verification, peer review, and card record

**Speaker notes**

- Contrast the board checkpoints: Day 1 evidence includes the actual Kanban screenshot and supplementary Definition of Done screenshot in `docs/evidence/`; the actual Day 2 board screenshot remains a required slot until supplied.
- Explain the WBS-to-Trello bridge: each WBS leaf became a Trello card with owner, reviewer, Must IDs, dependencies and verification. Card 6.2 owns the final docs, demo and presentation.
- State the lessons: start with a small bounded corpus, add retrieval when mutable sources and targeted evidence selection justify its complexity, keep reviewer reasoning visible, protect the demo path with WIP=2, and treat comparison artifacts as evidence with explicit limits.
- Mention actual `agents.md` usage: Martha read the root instructions before this revision and used the file-scope rule to change only this outline. No source files, KBs, historical evidence or other contributor files changed.
- Consolidate the evidence boundary here: Sergii's one verified Instagram RAG path is real and specific; other-channel RAG acceptance, live RAG revision and final deployment are not established. Do not fill those gaps with claims.

**Evidence / visual slots**

- Actual Day 2 board screenshot: required replacement slot.
- Final RAG status/provenance visual: use Sergii's verified Instagram evidence if supplied.
- Final UI screenshots: required replacement slot.
- Sandra's exact matched excerpts are now incorporated; reserve only the final visual/artifact reference slot.

## Requirement-to-slide / notes mapping

| Requirement | Slide / notes location |
|---|---|
| Company brand generator and multi-channel pipeline | Slide 1 text and notes; Slide 3 text |
| Primary/secondary KB architecture and Markdown processing | Slide 3 text and notes |
| Q/T/C | Slide 2 text |
| Stakeholder quadrant | Slide 2 notes and evidence slot |
| Top risk | Slide 2 notes |
| WBS → Trello | Slide 5 notes |
| RAG decision defended using at least three tradeoffs | Slide 3 text and notes |
| Live content generation during demo | Slide 4 text and notes |
| Side-by-side uniqueness evidence | Slide 4 text and notes |
| Actual `agents.md` usage | Slide 5 notes |
| Day 1 versus Day 2 board | Slide 5 notes and evidence slots |
| WIP = 2 | Slide 2 text; Slide 5 text |
| Definition of Done | Slide 5 text and notes |
| Challenges and lessons | Slide 2 notes; Slide 5 notes |
| Sandra’s exact matched excerpts | Slide 4 text and notes |
| Final UI screenshots | Slide 4 evidence slot |
| Final RAG status and provenance | Slides 3–5 evidence slots |
| Actual Day 2 board screenshot | Slide 5 evidence slot |

## Unresolved evidence needs before deck finalization

- Final visual/artifact references from Sandra's evidence pack, although the exact matched excerpts are now incorporated.
- Final Streamlit UI screenshots for the single live Instagram generation, manual edit, approval and export.
- Sergii's owner-confirmed RAG browser evidence showing retrieved facts, limitations and provenance.
- Actual Day 2 Trello board screenshot.
- Final confirmation of peer review for Card 6.2. The outline does not claim that review is complete.
- Preserve the label **Without supplied sources vs full-context injection — historical non-RAG comparison**. Do not add scores, costs, accuracy improvements, performance improvements or publication claims that the artifacts do not support.
