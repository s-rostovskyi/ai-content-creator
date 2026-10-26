# Speaker notes — Patagonia Content Studio Final

## Slide 1 — 0:45 — Martha

Frame the project as a reviewable company brand generator for three channel formats.

The goal is an English-language Patagonia studio that drafts from curated source material without inventing facts. Introduce Sergii, Sandra and Martha.

Do not present a final RAG status callout as completed unless the evidence pack confirms it.

## Slide 2 — 1:15 — Martha, with Sandra for the KB point

Connect the problem to the project structure: the team needed a small, reviewable content studio with a human approval step.

Foreground the top risk: unsupported or stale claims. The control is primary-source grounding, explicit limitations, peer review and a human approval gate.

Mention that Sergii, Sandra, Martha, the hypothetical Patagonia approver and the instructor sit in Quadrant I, high interest and high influence. Keep Q/T/C visible. Do not claim the app eliminates generic language or guarantees factual safety.

## Slide 3 — 1:30 — Sandra, with Martha for evaluation

Explain the architecture progression. The original small, stable corpus justified deterministic full-context injection. Owner-authorized mutable sources and targeted evidence selection motivate the current RAG direction.

Current confirmed RAG status: OpenAI embeddings, a local SQLite index, hybrid factual-first retrieval and source upload/edit/delete UI with provenance. Sergii performed the real browser verification: one live Instagram RAG draft was manually reviewed and edited, approved and exported.

Defend the direction using three tradeoffs: targeted evidence selection adds retrieval logic; source/version updates add source-management responsibility; context cost and implementation complexity must be measured. Do not claim lower cost, higher accuracy, or complete channel acceptance.

The historical comparison is one qualitative sample per channel, not statistical proof.

## Slide 4 — 2:15 — Sergii for the app, Martha for the review decision

Sergii performs the single live browser generation using the approved demo brief. Do not promise a particular model response.

Point out channel copy, separate reviewer notes and preserved retrieval provenance. Show the human gate: manual edit, approval of the exact current revision, then Markdown/JSON export.

If the API fails, use the saved verified artifact. Do not make extra live calls for LinkedIn or email.

Read the exact matched excerpts aloud and label the experiment “Without supplied sources vs full-context injection — historical non-RAG comparison.” Do not call it a RAG benchmark or a comparison with the ChatGPT product.

The preserved format observations are one qualitative sample per channel: Instagram 70 vs 81 words, LinkedIn generic 116 below minimum vs contextual 135 OK, and email generic 107 vs contextual 133 under the clarification convention. Do not add scores.

## Slide 5 — 1:15 — Martha, with Sandra and Sergii available for questions

Contrast the board checkpoints. Day 1 evidence includes the actual Kanban screenshot and supplementary Definition of Done screenshot. The actual Day 2 board screenshot remains pending.

Explain the WBS-to-Trello bridge: each WBS leaf became a card with owner, reviewer, Must IDs, dependencies and verification. Card 6.2 owns the final docs, demo and presentation.

Mention the lessons: start with a bounded corpus, add retrieval when mutable sources and targeted evidence selection justify the complexity, keep reviewer reasoning visible, protect the demo path with WIP=2, and treat comparison artifacts as evidence with explicit limits.

State the evidence boundary clearly: Sergii’s one verified Instagram RAG path is real and specific. Other-channel RAG acceptance, live RAG revision and final deployment are not established. Martha read agents.md before this revision and kept the change to presentation artifacts only.

Total speaking time: 7:00. Maximum including contingency: 8:00.
