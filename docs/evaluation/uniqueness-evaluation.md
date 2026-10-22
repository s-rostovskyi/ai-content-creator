# Uniqueness Evaluation

## Scope

This evaluation checks whether the content-generation workflow creates drafts that are more specific and useful than generic ChatGPT-style copy. It focuses on four criteria:

1. Evidence of content uniqueness.
2. Effective use of the defined Hivemind strategies.
3. Patagonia brand alignment and contextual relevance.
4. Avoidance of generic “AI-slop” language.

The preserved evidence is available in [`docs/evidence/day1-smoke-test.json`](../evidence/day1-smoke-test.json).

## Comparison

The smoke test compares two clearly labeled fixtures using the same evaluation terms:

| Draft | Observable characteristics | Audit result |
|---|---|---|
| Generic fixture | “Elevate your everyday adventure with a game-changer.” It contains no required Patagonia context and includes two flagged generic phrases: “elevate your” and “game-changer”. | Failed |
| Contextual fixture | Mentions the Nano Puff jacket, a changing forecast, and Patagonia’s repair and reuse guidance. It contains both required context terms and no flagged generic phrases. | Passed |

The contextual fixture is therefore more differentiated on the observable checks: it gives the reader a concrete product anchor and a specific next step instead of relying on broad promotional language.

## Hivemind strategy evaluation

The generation request contains an explicit differentiation contract with four strategies:

- **Specificity:** lead with a verified product detail and a concrete use case.
- **Productive tension:** connect the product detail to a real reader trade-off without inventing a benefit.
- **Channel-native writing:** use the selected channel’s rhythm and one useful reader action.
- **Anti-slop control:** remove cliches, empty superlatives, vague sustainability claims, and generic calls to action.

The smoke test confirms that the contract, the selected `instagram` channel, and the verified contextual anchor are sent together. This makes the creative direction inspectable rather than leaving uniqueness as an untestable instruction such as “be creative”.

## Brand alignment and contextual relevance

The contextual fixture uses the verified anchor:

> Nano Puff jacket; repair and reuse guidance

It also preserves the distinction between a practical layering use case and a repair/reuse action. The evidence does not claim unsupported pricing, availability, performance results, environmental outcomes, or publication approval. Human review remains required.

## AI-slop avoidance

The evaluation flags the following phrases when they appear in generated text:

- “elevate your”
- “game-changer”
- “in today’s fast-paced”
- “seamlessly”
- “unlock the power of”
- “make a statement”

The generic fixture triggers two of these phrases. The contextual fixture triggers none and includes the required product and repair/reuse terms. This is a useful first-pass review signal, but it is not a semantic safety guarantee; a human reviewer must still check every factual claim and editorial interpretation.

## Result

The available offline evidence supports the following conclusion:

**The workflow demonstrates a measurable uniqueness advantage over the generic fixture by requiring verified contextual anchors, applying explicit Hivemind strategies, and rejecting common generic phrases.**

This is an integration and review-aid result, not a claim about live model performance. The smoke test used an offline fixture (`live_api_call: false`), so a stronger follow-up evaluation should preserve raw generic and contextual outputs from the same configured model, prompt family, and channel for Instagram, LinkedIn, and email.

## Template and prompt-layer evidence

The channel templates create meaningful differentiation before a model response is produced:

| Channel | Required distinctive shape | Uniqueness contribution |
|---|---|---|
| Instagram | 60–120 words; begins with a concrete image, object, action, or use case; one CTA; 0–2 emojis; at most 3 hashtags. | Favors a specific, visual entry point rather than a broad brand slogan. |
| LinkedIn | 120–200 words; short paragraphs; a useful product or design angle; one CTA; no unsupported business claims. | Requires an explanatory product/design perspective rather than repurposing a social caption. |
| Email | Subject up to 50 characters; preheader up to 90 characters; body 150–250 words; one CTA. | Requires a multi-part editorial package with a distinct subject, preheader, and body. |

All three templates also require `CHANNEL COPY` and `REVIEWER NOTES`. The notes must identify supporting source paths and URLs, facts used, editorial interpretations, limitations, and unresolved uncertainties. This separation helps prevent reviewer reasoning from being disguised as publishable copy.

The shared grounding rules strengthen differentiation and brand safety: primary context is authoritative for Patagonia facts, secondary context informs positioning only, competitor claims must not be transferred to Patagonia, source prose must not be copied, and “water-resistant” must remain distinct from “waterproof.” The templates also prohibit invented prices, availability, specifications, testimonials, personal experiences, and unsupported outcomes.

## Prompt-construction evidence

`src/prompt_templates.py` provides a deterministic boundary between trusted instructions and untrusted values:

- The template instructions retain channel-specific output rules and grounding rules.
- Campaign brief, primary context, secondary context, and reviewer feedback are rendered under `UNTRUSTED USER INPUT` delimiters.
- Braces inside user-provided values remain literal instead of being recursively interpreted as prompt placeholders.
- Each template must contain exactly the expected placeholders and the ordered sections `Inputs`, `Grounding and safety rules`, and `Required output`.
- Context values are not placed in trusted instructions.

These controls support uniqueness in two ways: they preserve the channel’s distinct creative brief, and they keep verified context available to the model without allowing context text to rewrite the template’s rules.

## Focused test evidence

`tests/test_prompt_templates.py` verifies the uniqueness-related prompt behavior across all three channels. The tests confirm that:

- Instagram, LinkedIn, and email all build successfully.
- Channel-specific instructions survive prompt construction.
- Primary and secondary context are included in the user-input section.
- Reviewer feedback is preserved literally and safely.
- Unknown channels, blank briefs, missing templates, invalid placeholders, and malformed section order are rejected.
- Context and campaign brief values do not leak into trusted instructions.
- The LinkedIn rule against unsupported business claims survives construction.

This is structural evidence of differentiated prompting and grounding discipline. It does not, by itself, prove that a live model will always produce unique copy; output review remains necessary.

## Pipeline, CLI, and output assessment

At the time of this evaluation, the requested pipeline artifacts were not present in the repository:

- `src/content_pipeline.py`: not present.
- `src/main.py`: not present.
- Focused pipeline tests: none found.
- `outputs/`: contains only `.gitkeep`; no approved content export is available for comparison.

Because these artifacts are absent, this evaluation makes no claim about end-to-end generation, feedback/revision behavior, human approval enforcement, CLI execution, or uniqueness of exported content. The template and prompt layers are ready to support those checks, but the pipeline evidence must be added before those parts can be scored.

## Updated conclusion

The available evidence supports a qualified conclusion:

**The project has a strong uniqueness foundation at the template, prompt-construction, and integration-contract layers.** It requires channel-specific forms, verified contextual anchors, source-aware reviewer notes, and explicit anti-slop checks. The offline comparison shows that the contextual fixture is more specific than the generic fixture.

**End-to-end uniqueness is not yet demonstrated.** The pipeline, CLI, focused pipeline tests, and approved output artifacts are missing, and the existing comparison is offline rather than a live same-model generic-versus-contextual evaluation. These are the next evidence gaps for a complete M6 uniqueness evaluation.

## Verification record

- Evidence artifact: [`day1-smoke-test.json`](../evidence/day1-smoke-test.json)
- Offline smoke checks: passed
- Python compilation check: passed
- Live API response: not used in this evaluation
- API key: not logged
- Human approval/export: still required
