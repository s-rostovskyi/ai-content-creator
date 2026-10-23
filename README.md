# Patagonia Content Studio

Patagonia Content Studio is an unofficial educational prototype that combines two ideas: company brand-content generation and a multi-channel content pipeline. It is scoped to one product and one market slice for the course project: Patagonia Men's Nano Puff Jacket, style 84212, on the US site in English.

The goal is to help a marketing team move from a curated source snapshot to channel-ready drafts for Instagram, LinkedIn, and email, then through human review, feedback, manual editing, explicit approval, and Markdown/JSON export. It is a publication-ready export workflow, not automatic posting.

## What the workflow does

1. Review the curated Markdown knowledge base snapshot.
2. Prepare or edit one shared campaign brief.
3. Generate independent channel drafts.
4. Review reviewer notes and source provenance.
5. Revise or manually edit when needed.
6. Explicitly approve the exact saved revision.
7. Export approved content to Markdown plus a JSON sidecar.

The source review is manual snapshot analysis, not live monitoring. The secondary knowledge base is historical context and competitor/industry reference material; it is not treated as current market telemetry.

## Setup

Install dependencies with the active Python interpreter:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the application configuration:

```ini
OPENAI_API_KEY=
OPENAI_MODEL=
```

`OPENAI_API_KEY` is the application key used by the OpenAI client inside this repo. It is separate from Codex authentication and should stay local. `OPENAI_MODEL` selects the model at runtime; the project uses a configurable model rather than hard-coding credentials or secrets.

## Run the app

Start the Streamlit UI:

```bash
python -m streamlit run app.py
```

Run the CLI in dry-run mode to build prompts without loading credentials or calling the API:

```bash
python -m src.main --channel instagram --brief "..." --dry-run
```

Run the CLI in live review mode after configuration is in place:

```bash
python -m src.main --channel instagram --brief "..."
```

The CLI uses the same pipeline as the UI. Live mode shows the draft, reviewer notes, and explicit review actions; quit never implies approval or export.

## Evaluation commands

Run the generic-versus-contextual comparison in dry-run mode by default:

```bash
python scripts/generic_vs_contextual_eval.py
```

Run the six live comparison requests only when you explicitly want them:

```bash
python scripts/generic_vs_contextual_eval.py --live
```

Use `--runs-dir` if you want a different output base under `docs/evaluation/runs/`.

## Tests

Run the offline suite with a fresh temporary base directory:

```bash
python -m pytest -q -p no:cacheprovider --basetemp <fresh temp dir>
```

## Operational notes

- Session memory is browser-session scoped only; refreshing the page does not preserve state.
- Switching channels restores that channel's own draft, editor buffers, revision state, approval state, export record, and attempt count.
- Replacing the shared brief requires explicit confirmation if any channel already has work.
- Per-channel request limits are enforced by the pipeline; a failed revision still consumes the attempt allowance.
- Format checks are advisory. They help reviewers catch length and structure problems, but they do not verify factual accuracy, brand fit, or publication readiness.
- Approval and export remain explicit human actions.
- The UI uses the shared brief plus channel-specific workspaces; stale content is invalidated when the channel or brief changes.

## Evidence and references

- Channel acceptance evidence: [docs/evidence/channel-acceptance/README.md](docs/evidence/channel-acceptance/README.md)
- Generic-versus-contextual comparison report: [docs/evaluation/generic-vs-contextual-results.md](docs/evaluation/generic-vs-contextual-results.md)
- Email counting clarification: [docs/evaluation/email-counting-clarification.md](docs/evaluation/email-counting-clarification.md)
- Scorecard for reviewer scoring: [docs/evaluation/generic-vs-contextual-scorecard.md](docs/evaluation/generic-vs-contextual-scorecard.md)

Observed format issues in the preserved comparison report:
- Generic LinkedIn is below the 120-word minimum.
- Both email variants remain below the 150-word body minimum under the clarified counting convention.
- The comparison is one qualitative sample per channel; it does not prove uniqueness or independent review completion.

## Status

Implemented behavior includes Markdown ingestion, deterministic context assembly, OpenAI integration, channel templates, CLI dry-run/live review, Streamlit drafting and revision, validation, approval, export, and preserved evaluation artifacts.

Not deployed: there has been no production deployment from this repo. Remaining course work, if any, should be tracked on the board rather than implied by the codebase.
