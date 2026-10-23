# Channel Acceptance Evidence

This folder preserves three owner-reviewed live functional examples copied from the UI test exports. These are not independent teammate reviews and they are not generic-versus-contextual evaluation results.

## Verified artifacts

- Instagram
  - Markdown: `instagram-rev3-20261022T204049Z-a149b306.md`
  - JSON: `instagram-rev3-20261022T204049Z-a149b306.json`
  - Revision: 3
  - Origin: manual_edit
  - Response ID: `resp_073b7d413d9db95b006ada7378c82087d2b7853b5319998bb1`
  - Approved at: `2026-10-22T20:40:49.760439+00:00` UTC / `2026-10-22T22:40:49.760439+02:00` Europe/Berlin

- LinkedIn
  - Markdown: `linkedin-rev4-20261022T221546Z-313b21a5.md`
  - JSON: `linkedin-rev4-20261022T221546Z-313b21a5.json`
  - Revision: 4
  - Origin: revision
  - Response ID: `resp_0cc94867f1bfc214006ada8af0e40087d29b1810eee66affda`
  - Approved at: `2026-10-22T22:15:46.805511+00:00` UTC / `2026-10-23T00:15:46.805511+02:00` Europe/Berlin

- Email newsletter
  - Markdown: `email-rev2-20261022T222413Z-105918ca.md`
  - JSON: `email-rev2-20261022T222413Z-105918ca.json`
  - Revision: 2
  - Origin: manual_edit
  - Response ID: `resp_02830046d75b13c5006ada8b9b181887d280b0a60a1ad2de6c`
  - Approved at: `2026-10-22T22:24:13.422836+00:00` UTC / `2026-10-23T00:24:13.422836+02:00` Europe/Berlin

## Verification notes

- Each Markdown file was verified against the corresponding JSON `channel_copy` content, with matching revision numbers and matching SHA-256 fingerprints for the approved copy.
- The recorded timestamps above remain unchanged.
- The LinkedIn stale-draft rendering issue and the email post-save approval issue were discovered during manual testing and later covered by offline regressions.
- The latest reported offline suite result is `100 passed`; this README does not claim a new test run.
- Manual browser verification of the latest post-save approval fix remains pending.
- Do not infer total API spending from these final exports; they do not include every earlier request.
