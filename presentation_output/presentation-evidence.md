# Presentation Evidence — Card 6.2

Owner: Sandra  
Must IDs: M7, M8

This note preserves evidence for Martha’s five-slide presentation. It is a presentation aid, not a new evaluation and not evidence of final RAG UI behavior.

## Verified scope and knowledge-base roles

- Product scope: Patagonia Men’s Nano Puff® Jacket, style 84212, for the US website and English content.
- Primary KB: official Patagonia materials. It carries product facts, Patagonia editorial observations, care/repair/reuse information, and published Patagonia style references. Primary facts are the source of truth for Patagonia claims.
- Secondary KB: historical industry and competitor reference material. It can inform context and editorial implications, but competitor or industry statements must not become Patagonia facts or current market telemetry.
- The source review is a curated Markdown snapshot, not live monitoring.

## Matched generic/contextual evidence

The comparison report describes one qualitative sample per channel. It is not statistical proof. For one matched Instagram pair, the generic draft says:

> “Built to pack down easily, it’s designed with convenience in mind”

[Original generic Instagram artifact](../evaluation/runs/20261023T021455-aab889c1/01-instagram-generic.json)

The contextual draft says:

> “The internal zippered chest pocket that doubles as a stuffsack”

[Original contextual Instagram artifact](../evaluation/runs/20261023T021455-aab889c1/02-instagram-contextual.json)

Concrete difference: the generic version uses broad, non-source-specific convenience language, while the contextual version names a verified style-84212 construction detail and also includes product-specific material and feature claims. This is an observed difference in this sample, not a claim that contextual prompting always improves output.

## Format observations and email clarification

The preserved report records these format observations:

- Instagram: generic 70 words and contextual 81 words; both marked OK.
- LinkedIn: generic 116 words, below the 120-word minimum; contextual 135 words, marked OK.
- Email: generic body 102 words and contextual body 133 words in the original report; both below the 150-word minimum.

The [email-counting clarification](../evaluation/email-counting-clarification.md) says the current validator counts a separately labeled CTA once when present. Under that convention, the generic email body is 107 words and the contextual body is 133 words; neither reaches 150 words, so the conclusion does not change.

## RAG decision criteria

The current evidence supports distinguishing two things:

- Historical implementation: the checkpoint’s implementation uses deterministic full-context injection of the six curated Markdown documents, separated into primary and secondary context. It is bounded and reviewable for this small corpus, but it is not query-based retrieval.
- New retrieval direction: a future RAG direction would select relevant sources or chunks for each request. The published checkpoint predates live RAG UI integration, so this checkout does not prove final RAG behavior.

Three defensible criteria for deciding whether to move from the historical implementation toward retrieval are:

1. Corpus scale and context fit. Move toward retrieval if the corpus grows or measured serialized context becomes unwieldy; the existing character guardrail is not a token-window guarantee.
2. Request diversity and source selection. Move toward retrieval if briefs routinely require only a subset of sources or expand beyond the fixed product scope, making targeted source selection materially useful.
3. Update frequency and review burden. Move toward retrieval if the curated source set changes often enough that rebuilding full context increases maintenance or review burden, while retaining traceable source provenance.

These are decision criteria, not proof that retrieval is already integrated or superior here. Implementation complexity and factual grounding remain constraints.

## Board evidence

Available Day 1 board evidence:

- [Day 1 board screenshot](../evidence/p2-kanban-day1.png) — the actual Trello board with five lists, work cards, and WIP limit visible.
- [Day 1 Definition of Done screenshot](../evidence/p2-kanban-day1-dod.png) — the five DoD rules readable.
- [Day 1 status notes](../evidence/day1-status.md) — records the board evidence and the pending Day 2 work.

Pending evidence slot: **[Insert the actual end-of-Day-2 Trello board screenshot here before presenting.]** No end-of-Day-2 screenshot is present in this synchronized checkout.

## Owner confirmation required before presenting

Sandra should confirm these items before they are stated as final presentation claims:

- Whether the planned or current retrieval direction has actually been integrated into the UI after checkpoint `e02846d`.
- The actual end-of-Day-2 board state and screenshot; do not substitute the Day 1 screenshots.
- Whether any human review, approval, or acceptance claim is being made beyond the preserved artifacts. The generic/contextual report has blank reviewer score tables, and the channel-acceptance README says its exports are owner-reviewed examples, not independent teammate reviews or generic/contextual evaluation results.
- Whether the presentation will mention live model, token, latency, or cost values. If so, confirm the intended artifact and scope; do not infer API cost from preserved exports.
- That no claim is made that every channel has passed live RAG acceptance. The checkpoint predates live RAG UI integration and the available evidence does not establish that claim.

