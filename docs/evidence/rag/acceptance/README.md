# RAG Acceptance Evidence

The original Instagram checkpoint below preserves one owner-reviewed export pair exactly as copied from `UI_Test/`. A separate LinkedIn live-revision checkpoint follows; the evidence boundaries differ by channel.

## Instagram owner-reviewed checkpoint

- Markdown export: `instagram-rev3-20261023T130612Z-0fee9998.md`
- JSON export: `instagram-rev3-20261023T130612Z-0fee9998.json`

Recorded facts:
- Retrieval saved at: `2026-10-23T12:53:49Z`
- Approval timestamp: `2026-10-23T13:06:12.559683+00:00`
- Approved revision: `3`
- Model: `gpt-5.4-mini-2026-03-17`
- Retrieval usage: prompt_tokens=`87`, total_tokens=`87`, latency=`2.715s`
- Generation usage: input_tokens=`1837`, output_tokens=`547`, total_tokens=`2384`, latency=`5.113s`
- Context mode: `rag`
- Source snapshot: `9349972665c952782b93afde17efc583f4f577019709d36d43b35d0523cf1e20`
- SHA-256 markdown: `87d9cdc3c6d578829f3308fd1390cbd55caa01aefc7c5ec656e6d1f1c9ea1a1e`
- SHA-256 JSON: `9af39228d04cd56eae09bd40635f23222a985560b5c132752024a0a6038fce95`
- Markdown/channel_copy equality: `True`

Scope notes:
- This is one owner-reviewed Instagram generation -> manual notes edit -> approval -> export, not all-channel RAG acceptance.
- This is not an independent peer review and not a live revision test.
- Earlier failed retrieval evidence remains preserved in `docs/evidence/rag/` and was not rewritten.
- Owner browser checks previously confirmed per-channel view retention and an explicit zero-API index rebuild; those are reported checks, not claims from this copy step.
- Native rerenders can still reset scroll position; this limitation is not fixed here.

## LinkedIn owner-approved live RAG revision

Card: 3.2 Context assembly and RAG assessment; Must IDs M2, M5, M7.

- Preserved unchanged from `UI_Test/`: [linkedin-rev2-20261023T201936Z-84be0282.md](linkedin-rev2-20261023T201936Z-84be0282.md) and [linkedin-rev2-20261023T201936Z-84be0282.json](linkedin-rev2-20261023T201936Z-84be0282.json).
- Channel: `linkedin`; revision `2`; origin `revision`; context mode `rag`.
- Approval: revision `2` at `2026-10-23T20:19:36.639756+00:00`; export reviewer label is `Human reviewer`. Owner approval is reported in the conversation; the artifact does not identify an independent named reviewer.
- Markdown/channel_copy equality and approval SHA-256 verified; approved copy fingerprint `c35d501531634525aa7e22b77728bcdf4f482b730c4091d4e1b6ef93d3400813`.
- Corpus snapshot: `4984775f808b507cc6c77b5394d5e730a314e80a7da19da1ada8bc0cd1bcb531`.
- Retrieval query includes the prior channel copy and human revision feedback; query digest `89f5f2412b5dbdc5d33d812e023da0babbfead3e69b43c2a1ccf4b6488ab1402`.
- Retrieval: `text-embedding-3-small` requested / `text-embedding-3-small` returned; `422` tokens; `0.266781` seconds.
- Retrieved context: `5720/6000` characters; 3 primary factual chunks from 2 sources; attached limitations preserved. The source manifest records supplied context, including repair_and_reuse.md; reviewer notes correctly cite only product_facts.md for claims actually used.
- Revision generation: `gpt-5.4-mini-2026-03-17`; input `2157`, output `436`, total `2593` tokens; `3.327263` seconds.
- Copy: `129` whitespace-separated words, within LinkedIn's 120-200 range but one word below the feedback request of 130-160; no automatic correction or rescore was applied.
- Scope: one owner-run LinkedIn generation -> live RAG revision -> approval -> export. This pair preserves the final revision and its query containing prior copy, not a separate initial-response metadata artifact. It is not independent peer review or all-channel RAG acceptance.
- Owner saved a page immediately after Revise showing stale revision-1 format/retrieval details alongside revision-2 approval controls. Switching to Draft displayed revision 2 correctly. This UI consistency defect is recorded, not fixed by preserving evidence.
- SHA-256 md: `2c8c32fc4e238efd85637188ffc89a43fd273e8dbb6557474a4c92dde081b878`.
- SHA-256 json: `6c379b99187eaff112e3ea9dedaf653f0c33b8c227fd0ede10cec8f121ee685e`.

## Email owner-approved manual-edit checkpoint

Card: 3.2 Context assembly and RAG assessment; Must IDs M2, M5, M7.

- Preserved unchanged from `UI_Test/`: [email-rev3-20261023T205812Z-272e76ac.md](email-rev3-20261023T205812Z-272e76ac.md) and [email-rev3-20261023T205812Z-272e76ac.json](email-rev3-20261023T205812Z-272e76ac.json).
- Revision `3`; origin `manual_edit`; context mode `rag`.
- Approval: revision `3` at `2026-10-23T20:58:12.611445+00:00`; recorded reviewer label `Human reviewer`. The conversation establishes owner approval, not independent named peer review.
- Markdown/channel_copy equality and approval SHA-256 verified: `ee0f145eaa0c989ab8243c007b601209c08eb884a7d4561735a59e8f0eda89b9`.
- Corpus snapshot: `4984775f808b507cc6c77b5394d5e730a314e80a7da19da1ada8bc0cd1bcb531`.
- Subject 39/50 characters; preheader 63/90; body 157 words, including the single inline CTA.
- Initial generated body was 140 words and failed the 150-word minimum. The owner manually added an editorial interpretation of the verified stuffsack feature and removed unused facts/URLs from notes. Format compliance is therefore after human editing, not initial model compliance.
- Retrieval: `text-embedding-3-small` requested / `text-embedding-3-small` returned; `87` tokens; `1.355916` seconds. Context is 5720/6000 characters, 3 primary factual chunks from 2 sources with limitations retained.
- Originating generation: `gpt-5.4-mini-2026-03-17`; input `1840`, output `691`, total `2531` tokens; `5.067303` seconds. These metrics describe the original generation, not the manual edits.
- Scope: RAG generation -> manual copy/notes edits -> owner approval -> export; not a live model revision or independent peer review.
- SHA-256 md: `2bc8117a4edf50ab28ab29abd7c9580ed5deedefdade35642b1454c390ffe043`.
- SHA-256 json: `3a7a82a1896847f1ca4a50503cb6de652257850846386444f40bcbc6509921db`.

## Combined evidence boundary

One owner-approved example is preserved for each channel; Instagram uses the earlier corpus snapshot, while LinkedIn and email use the corrected snapshot. LinkedIn additionally demonstrates a live RAG revision. This is limited smoke/acceptance evidence across different runs and snapshots, not a controlled RAG benchmark or independent all-channel sign-off.
