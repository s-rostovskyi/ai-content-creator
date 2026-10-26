# Demo runbook — Patagonia Content Studio

## Timing and owners

- Slide 4 demo block: 2:15. Sergii runs the app; Martha makes the review decision.
- Total presentation timing: 0:45 + 1:15 + 1:30 + 2:15 + 1:15 = 7:00.
- Maximum with contingency: 8:00.

## Before presenting

1. Open the Streamlit app with the configured local environment.
2. Confirm the approved demo brief is ready and that no secret is visible.
3. Have the saved verified Instagram artifact available as fallback.
4. Open the preserved LinkedIn and email acceptance artifacts for reference only.
5. Keep the Day 1 Kanban and Definition of Done evidence available.

## Live sequence

1. Enter the Instagram brief in Streamlit.
2. Generate exactly one Instagram draft live with RAG retrieval.
3. Point out channel copy, separate reviewer notes, and retrieval provenance.
4. Manually edit the draft once.
5. Approve the exact edited revision.
6. Show Markdown and JSON export.

## Guardrails

- Do not make extra live calls for LinkedIn or email. Show preserved state only.
- Do not promise a particular model response.
- Keep reviewer notes separate from publishable copy.
- Do not claim all-channel RAG acceptance, live RAG revision, final deployment, cost savings, or accuracy gains.
- Read the historical excerpts exactly and label them: **Without supplied sources vs full-context injection — historical non-RAG comparison**.

## Fallback

If the API fails, use the saved verified artifact and narrate the same review, approval, and export path. The saved artifact demonstrates the approved Instagram flow and preserves revision, fingerprint, and provenance evidence.
