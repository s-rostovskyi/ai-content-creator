# Generic-versus-contextual Evaluation Scorecard

This is a small qualitative comparison, not statistical proof. A cautious generic response is a valid outcome when verified source context is unavailable.

Use the anchors below when scoring each response. The anchor table remains unfilled; completed named reviews are recorded separately below.

| Criterion | 1 | 3 | 5 | Score |
|---|---|---|---|---|
| Factual grounding and unsupported claims | Heavy hallucination, unsupported facts, or unsafe claims. | Mostly grounded but with some vague or weakly supported claims. | Strongly grounded, no unsupported claims, and careful around uncertain points. |  |
| Product and brand specificity | Generic or off-target; misses Patagonia or the product details. | Mentions the product but misses some useful specifics or brand signals. | Clearly specific to Patagonia and the chosen product, without invented details. |  |
| Channel-format compliance | Ignores channel conventions or reads like the wrong format. | Mostly follows the channel but with noticeable structural or tonal issues. | Fits the channel format cleanly and reads naturally for that platform. |  |
| Editorial quality and usefulness | Hard to use, awkward, or too thin to publish. | Serviceable but not especially polished or actionable. | Clear, useful, polished, and ready for human review with minimal cleanup. |  |
| Source traceability | Claims are not traceable to sources or the traceability is unclear. | Some claims can be traced, but not consistently or clearly enough. | Claims are easy to trace back to the preserved source context or explicitly marked as generic. |  |

## Reviewer notes

- Use the same rubric for Instagram, LinkedIn, and email.
- Compare generic and contextual responses separately for each channel.
- Record only human judgments here; leave scores blank until review.

## Sandra Obregon — independent saved-file review

- Recorded: 2026-10-23T15:25:46.789Z.
- Source: [Trello card 5.2, Sandra's original comment](https://trello.com/c/Md6G1HMn/12-52-uniqueness-evaluation#comment-6adb7c7a0abaa489b0838576).
- Run: [20261023T021455-aab889c1](runs/20261023T021455-aab889c1/manifest.json).
- Scope: historical non-RAG generic versus full-context outputs, not current RAG acceptance.
- Method: saved-file review and local measurements; no new generation. The reviewer did not verify the uploaded artifacts' commit SHA.
- These are Sandra's reported human judgments, transcribed without rescoring. Martha's separate ratings remain pending.

| Channel | Condition | Factual grounding | Product / brand specificity | Channel compliance | Editorial usefulness | Source traceability |
|---|---|---:|---:|---:|---:|---:|
| Instagram | generic | 3 | 3 | 3 | 3 | 3 |
| Instagram | contextual | 3 | 5 | 5 | 3 | 3 |
| LinkedIn | generic | 3 | 3 | 3 | 3 | 3 |
| LinkedIn | contextual | 5 | 5 | 5 | 5 | 3 |
| Email | generic | 3 | 3 | 3 | 3 | 3 |
| Email | contextual | 5 | 5 | 3 | 3 | 3 |

### Reviewer rationale and limitations

The following is transcribed from Sandra's comment; its judgments are not independently rescored here.

Evidence-based reasons:
- Instagram generic: 70 words and three hashtags, but two CTA-like invitations. Notes call packability verified without a supporting source.
- Instagram contextual: 81 words and compliant format. Specific product details are supported, but performance wording applies jacket-level properties to materials. Notes include unused facts.
- LinkedIn generic: few specific details, product claims without supplied sources, and 116 words instead of at least 120.
- LinkedIn contextual: 135 words, supported component-level facts and clearly identified editorial framing. Notes list unused care instructions and performance facts.
- Email generic: 107 body words including the separate CTA, below 150. Product characteristics need verification, and the invitation is repeated.
- Email contextual: supported product and care facts, but only 133 body words. Notes list some construction details not used in the copy.
- Generic notes disclose missing sources, but some copy claims remain unverified.
- Contextual notes provide paths and URLs, but do not consistently distinguish supplied context from facts actually used.

Comparison checks:
Within each channel pair, briefs, trusted instructions, requested model and recorded settings match. The output limit is 2,000 tokens.
Generic prompts contain no supplied KB and include an absence notice. Prompts and original outputs are preserved.

Limitations:
One sample per condition and channel. No statistical significance or overall uniqueness claim. Historical non-RAG evaluation only; current RAG performance was not tested.

No original evidence was changed.

See [email counting clarification](email-counting-clarification.md): generic email has 107 body words including its separate CTA, contextual email has 133; both fail the minimum. Scores above are preserved even where channel compliance was rated 3 despite a measured length failure. No overall winner, aggregate score, statistical significance, or all-channel acceptance is inferred.

## Martha — independent ratings pending

Martha's contribution to the uniqueness analysis and her approval of corrected wording are separate from independent ratings of this six-response run. No scores are assigned on her behalf.
