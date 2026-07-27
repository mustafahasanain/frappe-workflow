# Step Validation

Every step's `- **Validation:**` line is a contract: it names the exact
verification, and the step is not `Completed` until it succeeded.

## Validation Kinds

| Kind | How it runs |
|---|---|
| Automated test | Run the named test file/case; require pass output. Frappe apps: `bench --site <target_site> run-tests --app <app> --module <module>` (or the app's documented runner). |
| Schema/migrate | `bench --site <target_site> migrate` completes without error after DocType/patch changes. |
| Import/syntax | The changed module imports cleanly (running the test suite or `bench --site <site> console` one-liner); for JS bundles, the build step succeeds. |
| Behavioral check | A concrete scripted check (console snippet, API call with a test record) whose expected output the step states. |
| Manual UI check | Only when truly not automatable; the step must say exactly what to click and what must appear, and the result is recorded as performed-by-user, never assumed. |

## Rules

- Use the task's `target_site`, never a guessed site.
- Validation output is captured verbatim (trimmed) for the summary; "it
  worked" without output is not a record.
- A failed validation keeps the step `In Progress` (fix and retry) or moves
  it to `Blocked` with the exact failure.
- Site-touching validations (migrate, run-tests) are development-bench
  operations — they are fine locally; they are never run on the demo
  server outside the deployment skill.
- Tests must use obviously fake credentials/values so the security scanner
  stays quiet (see `references/security-rules.md`).
