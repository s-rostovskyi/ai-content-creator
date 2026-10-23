# Email counting clarification for run 20261023T021455-aab889c1

This note reconciles the email format measurements in the generic-versus-contextual comparison run. It does not modify the preserved run artifacts or the original comparison report.

## Measurement conventions

- **Original report convention:** email body word count excluded a separately labeled `CTA:` section.
- **Current validator convention:** email body word count includes a separately labeled `CTA:` section exactly once when present.
- Subject and preheader counts always measure only the field text, excluding their labels.
- All counts below use the current content validator against the original `channel_copy` values from the preserved run artifacts.

## Corrected email measurements

| Condition | Original body count | Separate CTA words | Corrected combined body count | 150-250 words? | Original conclusion changes? |
|---|---:|---:|---:|---|---|
| Generic | 102 | 5 | 107 | No | No |
| Contextual | 133 | 0 | 133 | No | No |

## Conclusion

The original report's email-format conclusion does not change for either condition: both email drafts remain below the 150-word minimum even after the separate CTA is counted once. The original measurements remain documented in the comparison report, and this clarification should be read alongside it before reviewer scoring.
