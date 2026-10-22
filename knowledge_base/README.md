# Knowledge-base document format

This README documents the shared Markdown format for both knowledge bases and **must be excluded from corpus ingestion**.

## Required structure for every KB document

# Descriptive document title

- Source URL: ...
- Publisher: ...
- Published/updated: ... or "Not stated"
- Accessed: YYYY-MM-DD
- Knowledge base: primary or secondary
- Evidence type: official statement, product fact, published brand content, industry research, or competitor statement

## Relevant facts

Short paraphrased facts, each linked to its supporting source when multiple sources are used.

## Content implications

Clearly labeled editorial interpretations. These must not be represented as source facts.

## Limitations

Missing information, geographic restrictions, dated claims, or other qualifications.

## Rules

- Use UTF-8 Markdown with clear headings.
- Use verified, accessible source pages only.
- Never invent URLs, dates, statistics, product details, performance results, or environmental claims.
- Primary KB: official Patagonia materials only.
- Secondary KB: industry research and competitors’ official materials; competitors’ statements must never become Patagonia facts.
- Keep quoted material short; prefer paraphrases and source links.
- Published brand examples are style references, not proof of campaign success.
- Never describe inferred brand guidance as an official Patagonia brand manual.
- Source content is data, not executable instructions for the LLM.
- Aim for a small initial corpus: 3–4 primary documents and 2–3 secondary documents, about 150–350 words each. These are targets, not measured corpus values.
- Proposed primary files: `brand_voice.md`, `product_facts.md`, `repair_and_reuse.md`, `past_content/examples.md`.
- Proposed secondary files: `market_trends.md`, `competitor_context.md`.
- Agreed scope: Patagonia Men's Nano Puff® Jacket, style 84212, for the US website and English content.
- `past_content/examples.md` belongs under `primary/` and contains published Patagonia style references, not evidence of campaign success.
- Distinguish water-resistant from waterproof and preserve qualifications on material and environmental claims.
- Sandra owns primary KB curation; Martha owns secondary KB curation.
- Do not put unfinished placeholder documents into the actual KB folders.

## FORMAT EXAMPLE — NOT A SOURCE

# Example title

- Source URL: https://example.com/example-page
- Publisher: Example Publisher
- Published/updated: Not stated
- Accessed: 2026-10-22
- Knowledge base: primary
- Evidence type: official statement

## Relevant facts

- Example fact paraphrase supported by the example page.

## Content implications

- Example editorial takeaway that is not a source fact.

## Limitations

- Fictional example only; not a real source.
- This README is documentation and must not be ingested as corpus content.

