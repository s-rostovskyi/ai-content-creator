# Uniqueness Evaluation

## Provenance note

- Original draft and core analysis: Martha Olukayode.
- This maintainer correction keeps the useful prompt-analysis material while reconciling the evidence claims with the preserved artifacts.
- The preserved response artifacts themselves are unchanged.

## Scope

This note covers uniqueness signals in the prompt/template layer and the preserved Day 1 live response artifact. It does not validate the current RAG pipeline or claim end-to-end uniqueness for the now-implemented app.

## Day 1 live evidence

- `docs/evidence/day1-smoke-test.json` records one live API response plus reviewer notes.
- It is not an offline paired generic-vs-contextual experiment.
- The generated caption stays focused on the Nano Puff jacket, packability, and practical features.
- Repair and reuse context belongs in the supporting notes/evidence, not in the publishable caption.
- Human review remains required.

## Uniqueness signals

The live response shows a concrete product anchor, practical feature language, and a reviewer note trail that points back to the supporting sources. That is a stronger uniqueness signal than generic brand copy, but it is still a single live response and not a full comparative study.

## Template and prompt structure

The channel templates create meaningful differentiation before a model response is produced:

| Channel | Required distinctive shape | Uniqueness contribution |
|---|---|---|---|
| Instagram | 60-120 words; begins with a concrete image, object, action, or use case; one CTA; 0-2 emojis; at most 3 hashtags. | Favors a specific, visual entry point rather than a broad brand slogan. |
| LinkedIn | 120-200 words; short paragraphs; a useful product or design angle; one CTA; no unsupported business claims. | Requires an explanatory product/design perspective rather than repurposing a social caption. |
| Email | Subject up to 50 characters; preheader up to 90 characters; body 150-250 words; one CTA. | Requires a multi-part editorial package with a distinct subject, preheader, and body. |

All three templates also require `CHANNEL COPY` and `REVIEWER NOTES`. The notes must identify supporting source paths and URLs, facts used, editorial interpretations, limitations, and unresolved uncertainties. This separation helps prevent reviewer reasoning from being disguised as publishable copy.

The shared grounding rules strengthen differentiation and brand safety: primary context is authoritative for Patagonia facts, secondary context informs positioning only, competitor claims must not be transferred to Patagonia, source prose must not be copied, and "water-resistant" must remain distinct from "waterproof." The templates also prohibit invented prices, availability, specifications, testimonials, personal experiences, and unsupported outcomes.

## Prompt-construction evidence

`src/prompt_templates.py` provides a deterministic boundary between trusted instructions and untrusted values:

- The template instructions retain channel-specific output rules and grounding rules.
- Campaign brief, primary context, secondary context, and reviewer feedback are rendered under `UNTRUSTED USER INPUT` delimiters.
- Braces inside user-provided values remain literal instead of being recursively interpreted as prompt placeholders.
- Each template must contain exactly the expected placeholders and the ordered sections `Inputs`, `Grounding and safety rules`, and `Required output`.
- Context values are not placed in trusted instructions.

These controls support uniqueness in two ways: they preserve the channel's distinct creative brief, and they keep verified context available to the model without allowing context text to rewrite the template's rules.

## Historical comparison artifacts

For the later six-response generic-versus-contextual comparison, use the preserved run and its companion reports:

- `docs/evaluation/generic-vs-contextual-results.md`
- `docs/evaluation/generic-vs-contextual-scorecard.md`
- `docs/evaluation/email-counting-clarification.md`
- `docs/evaluation/runs/20261023T021455-aab889c1/manifest.json`

That comparison is historical non-RAG evidence. It helps with channel-format review and groundedness review, but it does not validate the newly developed RAG pipeline.

## Current status and limits

The repository now includes the implemented pipeline/CLI and the evolving RAG workflow, but this historical uniqueness note does not score those moving parts.

Human scores remain blank and independent acceptance is still pending.

This document should be read as a reconciliation note: it preserves Martha's useful uniqueness analysis, corrects the Day 1 evidence framing, and keeps the later comparison artifacts linked without overstating what they prove.

## Verification record

- Evidence artifact: [`day1-smoke-test.json`](../evidence/day1-smoke-test.json)
- Live API response: recorded in the preserved JSON artifact
- Offline smoke checks: not claimed here
- Python compilation check: not claimed here
- API key: not logged
- Human approval/export: still required
