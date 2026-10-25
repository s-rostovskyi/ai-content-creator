# API Cost Estimate

Verification date: 2026-10-25
Currency: USD
Scope: application-side API usage only. This estimate does **not** include Codex usage outside the application, billed account totals, taxes, credits, or any non-application charges.

## Pricing sources (official OpenAI)
- GPT-5.4 Mini pricing: `https://developers.openai.com/api/docs/models/gpt-5.4-mini`
- OpenAI API pricing table: `https://developers.openai.com/api/docs/pricing`
- text-embedding-3-small pricing: `https://developers.openai.com/api/docs/models/text-embedding-3-small`

## Verified rates used for this estimate

| Model | Billing unit | Input rate | Cached input rate | Output rate | Evidence |
|---|---|---:|---:|---:|---|
| `gpt-5.4-mini-2026-03-17` | per 1M text tokens | $0.75 | $0.075 | $4.50 | Pricing page and model page list GPT-5.4 Mini with these rates. |
| `text-embedding-3-small` | per 1M input tokens | $0.02 | n/a | n/a | Model page lists $0.02 per 1M tokens for embeddings. |

## Usage included in the numeric subtotal

### Directly recorded generation usage
- Historical channel-acceptance baseline: input `11,660`; cached input `2,176`; output `1,629`.
- Historical Day 1 smoke test: input `3,683`; cached input `0`; output `547`.
- Historical six-response comparison: input `12,284`; cached input `0`; output `2,971`.
- RAG generation / live model revision: input `5,834`; cached input `0`; output `1,674`.

### Directly recorded retrieval-query embeddings
- Packability retrieval before selection fix: `56` tokens.
- Packability retrieval after selection fix: `56` tokens.
- Instagram RAG retrieval: `87` tokens.
- LinkedIn RAG retrieval: `422` tokens.
- Email RAG retrieval: `87` tokens.

### Directly recorded index-build embeddings
- Build manifest: `1,634` tokens.
- The manifest records `3` embedded chunks, `17` reused embeddings, `1` completed batch, and `3.205738s` elapsed time.

## Usage excluded from the numeric subtotal
- Owner screenshot / conversation report for the same build invocation: corroborates the manifest row and is not counted again.
- Manual edits, offline previews, and zero-batch rebuild previews: not paid API calls.
- Retrieval or build evidence with missing usage metadata beyond the values above: excluded from the numeric subtotal.
- Billed account totals: not available here.

## Reproducible calculations

### Generation cost
Generation input tokens are split into ordinary input and cached input before applying rates.

- Ordinary input tokens = `33,461 - 2,176 = 31,285`
- Cached input tokens = `2,176`
- Output tokens = `6,821`

Formula:
- Ordinary input cost = `31,285 / 1,000,000 × $0.75 = $0.02346375`
- Cached input cost = `2,176 / 1,000,000 × $0.075 = $0.00016320`
- Output cost = `6,821 / 1,000,000 × $4.50 = $0.03069450`
- Generation subtotal = `$0.05432145`

### Retrieval-query embedding cost
- Retrieval tokens counted = `56 + 56 + 87 + 422 + 87 = 708`
- Embedding subtotal = `708 / 1,000,000 × $0.02 = $0.00001416`

### Index-build embedding cost
- Build tokens counted = `1,634`
- Build subtotal = `1,634 / 1,000,000 × $0.02 = $0.00003268`

## Estimated subtotal by usage category
- Directly recorded generation usage: `$0.05432145`
- Directly recorded retrieval-query embeddings: `$0.00001416`
- Directly recorded index-build embeddings: `$0.00003268`
- **Estimated application API usage total: `$0.05436829`**

## Coverage limitations
- The estimate is based on observed application-side usage only and is not reconciled to billing-account data.
- The generation subtotal uses the exact current GPT-5.4 Mini rates verified on 2026-10-25, not reconstructed historical billing.
- The packability retrieval call is counted twice as two distinct observed executions because the evidence shows separate timestamps and latencies, even though the query text is identical.
- The linked owner build screenshot is corroborative only and does not add a second charge.
- Any missing or overwritten usage metadata remains excluded rather than inferred.
- The application inventory does not include Codex usage outside this application.
