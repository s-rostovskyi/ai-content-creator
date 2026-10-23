# Generic-versus-Contextual Comparison Report

This is one qualitative sample per channel, not statistical proof and not a comparison with the ChatGPT product. Within each pair, the templates, settings, brief, and requested model were held constant; the baseline received no provided KB and explicitly stated that verified source context was unavailable.

## Experiment summary

- Run directory: `F:\UserData\Desktop\AI_Consulting_and_Integration\Week_03\Day_4-5\ai-content-creator\docs\evaluation\runs\20261023T021455-aab889c1`
- Requested model: `gpt-5.4-mini`
- Returned model: `gpt-5.4-mini-2026-03-17`
- Planned requests: 6
- Completed requests: 6
- Failed requests: 0
- Missing requests: 0

## Format conventions

- **Email counting clarification:** see [docs/evaluation/email-counting-clarification.md](email-counting-clarification.md) for the corrected email body convention and updated counts.

- Copy words count the full rendered channel payload after trimming surrounding whitespace. For email, that includes the subject, preheader, body, and CTA text, while the body word count isolates only the body text after the `Body:` label.
- Email subject and preheader counts measure characters in the field text only, excluding the `Subject:` / `Preheader:` labels.
- Email body word count measures only the body text after the `Body:` label.

## Format measurements

| Channel | Condition | Copy words | Subject chars | Preheader chars | Body words | Limit check |
|---|---|---:|---:|---:|---:|---|
| Instagram | generic | 70 | n/a | n/a | n/a | ok |
| Instagram | contextual | 81 | n/a | n/a | n/a | ok |
| LinkedIn | generic | 116 | n/a | n/a | n/a | violation (116 words; limit 120-200) |
| LinkedIn | contextual | 135 | n/a | n/a | n/a | ok |
| Email | generic | 122 | 32 | 43 | 102 | violation: body 102 words (limit 150-250) |
| Email | contextual | 151 | 33 | 70 | 133 | violation: body 133 words (limit 150-250) |

## Instagram / generic
Source: `docs/evaluation/runs/20261023T021455-aab889c1/01-instagram-generic.json`

```text
A jacket stuffed into a daypack before a trailhead coffee stop says it’s ready when you are. Explore the Patagonia Men’s Nano Puff Jacket, style 84212, for a closer look at the details that make it a practical layer for everyday outings and outdoor trips. Built to pack down easily, it’s designed with convenience in mind for changing plans and shifting weather. Tap to learn more. 🧥 #Patagonia #NanoPuff #OutdoorLayer
```

## Instagram / contextual
Source: `docs/evaluation/runs/20261023T021455-aab889c1/02-instagram-contextual.json`

```text
A jacket stuffed into its own pocket, ready for a cross-town coffee run or a windy trail stop. The Men’s Nano Puff® Jacket, style 84212, is lightweight, highly compressible, and built with warm, windproof, water-resistant materials. Details like the internal zippered chest pocket that doubles as a stuffsack, zippered handwarmer pockets, and a drawcord-adjustable hem make it an easy grab for everyday outings and outdoor trips. Explore the product details and see how it fits your routine. 🌿 #Patagonia #NanoPuff #OutdoorGear
```

## LinkedIn / generic
Source: `docs/evaluation/runs/20261023T021455-aab889c1/03-linkedin-generic.json`

```text
Introducing the Patagonia Men’s Nano Puff Jacket, style 84212, in a clean, versatile layer designed for everyday wear and travel. When you want an outer layer that works well on its own or under another jacket, the Nano Puff offers a simple, technical look that fits a range of settings.

Its appeal is in the balance: lightweight feel, packable convenience, and a streamlined silhouette that can move from commuting to weekend plans with ease. For people looking for a dependable layer that is easy to bring along, this jacket is worth a closer look.

If you’re comparing layers for changing conditions, explore the product details to see whether the Men’s Nano Puff Jacket fits your needs.
```

## LinkedIn / contextual
Source: `docs/evaluation/runs/20261023T021455-aab889c1/04-linkedin-contextual.json`

```text
Meet the Men’s Nano Puff Jacket, style 84212.

Built for everyday layering, it pairs a regular fit with lightweight, highly compressible warmth. The shell is 100% recycled polyester ripstop with a durable water repellent finish made without intentionally added PFAS, and Patagonia notes the finish is intended to shed light moisture. The insulation is 60-g PrimaLoft® Gold Insulation Eco made from 100% postconsumer recycled polyester, with P.U.R.E.™ technology.

The details are practical: brick quilting, a center-front zipper with interior storm flap and chin garage, two zippered handwarmer pockets, an internal zippered chest pocket that doubles as a stuffsack, and a drawcord-adjustable drop-tail hem.

It’s the kind of jacket that works well for commuting, travel, and cool-weather days when you want warmth without extra bulk.

Explore the product details to see whether it fits your routine.
```

## Email / generic
Source: `docs/evaluation/runs/20261023T021455-aab889c1/05-email-generic.json`

```text
Subject: Patagonia Men’s Nano Puff Jacket

Preheader: A lightweight layer for cool-weather warmth

Body: Meet the Patagonia Men’s Nano Puff Jacket, style 84212—a versatile layer built for everyday wear in changing conditions. Designed to pack down easily, it’s a go-to option when you want warmth without extra bulk. The clean silhouette makes it easy to wear on its own or under a shell, whether you’re heading out for a hike, commuting across town, or adding a dependable layer to your kit.

If you’re looking for a practical cold-weather staple, the Nano Puff Jacket offers a simple balance of comfort and function in a lightweight form. Explore the jacket to see if it fits your layering setup.

CTA: Explore the Nano Puff Jacket
```

## Email / contextual
Source: `docs/evaluation/runs/20261023T021455-aab889c1/06-email-contextual.json`

```text
Subject: The Nano Puff, built for layering

Preheader: Warm, windproof, and water-resistant in a lightweight, packable build.

Body:  
Meet the Men’s Nano Puff® Jacket, style 84212: a regular-fit layer designed to bring warmth without the bulk. It’s windproof, water-resistant, lightweight, and highly compressible, so it’s easy to keep close when the weather shifts.

The shell is 100% recycled polyester ripstop with a DWR finish made without intentionally added PFAS, and the insulation is 60-g PrimaLoft® Gold Insulation Eco made from 100% postconsumer recycled polyester with P.U.R.E.™ technology. Details like the brick quilting pattern, zippered handwarmer pockets, an internal chest pocket that doubles as a stuffsack, and a drawcord-adjustable drop-tail hem round out the design.

It’s also made in a Fair Trade Certified™ factory, and the product page lists simple care instructions: machine wash warm, do not bleach, tumble dry low, and do not iron.

Explore the Men’s Nano Puff Jacket →
```

## Recorded generation settings and usage

- Instagram / generic: requested model `gpt-5.4-mini`; returned model `gpt-5.4-mini-2026-03-17`; input tokens 427; output tokens 291; elapsed 5.602s.
- Instagram / contextual: requested model `gpt-5.4-mini`; returned model `gpt-5.4-mini-2026-03-17`; input tokens 3663; output tokens 548; elapsed 4.601s.
- LinkedIn / generic: requested model `gpt-5.4-mini`; returned model `gpt-5.4-mini-2026-03-17`; input tokens 427; output tokens 345; elapsed 3.585s.
- LinkedIn / contextual: requested model `gpt-5.4-mini`; returned model `gpt-5.4-mini-2026-03-17`; input tokens 3663; output tokens 722; elapsed 6.246s.
- Email / generic: requested model `gpt-5.4-mini`; returned model `gpt-5.4-mini-2026-03-17`; input tokens 434; output tokens 348; elapsed 3.858s.
- Email / contextual: requested model `gpt-5.4-mini`; returned model `gpt-5.4-mini-2026-03-17`; input tokens 3670; output tokens 717; elapsed 4.939s.

## Review sections

### Sandra

Sandra Obregon recorded independent ratings for all six preserved outputs on 2026-10-23 at 15:25:46.789 UTC. See the [named scorecard, rationale, limitations, and original Trello comment](generic-vs-contextual-scorecard.md#sandra-obregon--independent-saved-file-review).

This was a saved-file review with local measurements, not new generation. The uploaded artifacts' commit SHA was not verified by the reviewer. Her ratings concern this historical non-RAG run only; they do not establish current RAG quality or full acceptance. Martha's independent ratings remain pending.

### Martha

| Criterion | 1 | 3 | 5 | Score |
|---|---|---|---|---|
| Factual grounding and unsupported claims |  |  |  |  |
| Product and brand specificity |  |  |  |  |
| Channel-format compliance |  |  |  |  |
| Editorial quality and usefulness |  |  |  |  |
| Source traceability |  |  |  |  |
