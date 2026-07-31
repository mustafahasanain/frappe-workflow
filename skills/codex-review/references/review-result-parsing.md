# Review Result Parsing

## Input Forms

`apply-review` accepts the result as command arguments, pasted content, or
a file path. Whatever the form, first write it verbatim to
`docs/ai-context/reviews/round-NNN-result.md` (current round from state), then:

```bash
bin/frappe-workflow review parse-result docs/ai-context/reviews/round-NNN-result.md
```

## Recognized Statuses

Exactly two, from the line `- **Status:** <STATUS>`:

```text
APPROVED
CHANGES_REQUIRED
```

Anything else — missing status line, "LGTM", "approved with comments",
lowercase variants — is **malformed**: reject it (`REVIEW_NO_STATUS`),
show the required format, stay in `codex_review`. Never guess.

## Findings Validation (CHANGES_REQUIRED)

The parser enforces per finding:

- `### N. Title` heading.
- `- **Severity:**` ∈ High | Medium | Low [`REVIEW_FINDING_SEVERITY`].
- `- **Issue:**` and `- **Required Fix:**` non-empty
  [`REVIEW_FINDING_FIELD`].
- CHANGES_REQUIRED with zero findings is malformed
  [`REVIEW_NO_FINDINGS`].

Plan Reference and File are required "when applicable" — the parser treats
them as optional; the fix loop flags findings that lack them when they
clearly should have them (a code finding without a file path goes back as
a question, not a guess).

## On Valid CHANGES_REQUIRED

1. Result file already saved (never edited afterward).
2. Record it:

```bash
bin/frappe-workflow state set codex_review.status changes_required
bin/frappe-workflow state set codex_review.result_path docs/ai-context/reviews/round-NNN-result.md
```

3. `bin/frappe-workflow state transition review_fixes --reason "round NNN changes required"`.
4. Continue in [review-fix-loop.md](review-fix-loop.md).

## On Valid APPROVED

1. `bin/frappe-workflow review fingerprint` — must equal
   `codex_review.implementation_fingerprint`. Mismatch → the approval is
   for a different implementation state: reject it, explain, and generate
   a new bundle (next round). Do not transition.
2. Match → record the approval:

```bash
bin/frappe-workflow state set codex_review.status approved
bin/frappe-workflow state set codex_review.approved_at <UTC timestamp>
```

3. Run finalization (feature-changelog skill update, project-context when
   architecture changed, plan metadata + review record — see
   git-finalization skill's finalization-gate reference).
4. `bin/frappe-workflow validate finalization-gate` must pass.
5. `bin/frappe-workflow state transition ready_for_commit --reason "round NNN approved"`.

## Never

- Edit or "clean up" the original result file.
- Drop a finding because it looks wrong — invalid findings are refuted
  with repository evidence in the fix loop, and that refutation is
  recorded.
