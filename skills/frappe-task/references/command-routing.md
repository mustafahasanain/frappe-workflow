# Command Routing

Detailed procedure for each action. `CLI` below means
`${CLAUDE_PLUGIN_ROOT}/bin/frappe-workflow` run inside the target app
repository (or with `--repo <app_git_root>`).

## No Action (continue)

1. `CLI detect --json` — detect bench/app; abort with the error if detection
   fails (exit 3).
2. If `docs/ai-context/task-workflow.json` does not exist: tell the user to run
   `/frappe-workflow:frappe-task init`. Stop. Do not create a task.
3. `CLI validate workflow-state` — abort on invalid state and report it.
4. Cross-check state vs Git: recorded branch vs actual, recorded commit
   hash exists (when stage ≥ committed), fingerprint match (when
   `ready_for_commit`). On mismatch → stop; report per
   `references/error-and-blocker-handling.md`.
5. Continue from `current_stage`:
   - `planning` → task-planning skill (finish or await the plan).
   - `implementation` → task-implementation skill (next non-completed step).
   - `codex_review` → the prompt exists; remind the user to run Codex and
     return the result via `apply-review`.
   - `review_fixes` → task-implementation skill on the open findings, then
     codex-review skill for the next round.
   - `ready_for_commit` → git-finalization skill (prepare the commit).
   - `committed` → ask the deploy question (deployment skill).
   - `deployed` / `deployment_skipped` → testing-task skill.
   - `completed` → report completion; suggest `start` for a new task.

## `init`

Order matters; stop on the first hard failure.

1. `CLI detect --json`. On multiple-candidate app ambiguity (run from bench
   root), list apps and ask the user to `cd` into one.
2. Report Sites (installed / not installed / unknown). Do **not** force a
   Site choice at init; the choice is task-level and happens at `start`.
3. `CLI project migrate` — move an old-layout application onto
   `docs/ai-context/`. Nothing to move is the normal case and reports
   "already current". A `MIGRATE_CONFLICT` (exit 1) means a path exists in
   both layouts: report it and stop; never guess which copy is current.
4. If `docs/ai-context/PROJECT_CONTEXT.md` missing → project-context skill
   (first-time analysis). Else → its incremental-analysis reference.
5. If `docs/ai-context/FEATURE_CHANGELOG.md` missing → feature-changelog
   skill (baseline discovery).
6. Ensure `docs/ai-context/` and `docs/ai-context/reviews/` exist in the
   app repo.
7. `CLI project ensure-gitignore` — idempotent managed block (see
   `../../../references/file-lifecycle.md`). Report `conflict` outcomes.
8. `CLI validate project-context` and `CLI validate feature-changelog`.
9. Report an initialization summary (what was created, updated, unchanged,
   migrated).

Never: start a task, create `docs/ai-context/TASK_PLAN.md`, create
`docs/ai-context/task-workflow.json`, create the old root-level files,
modify app behavior, commit, deploy.

## `start <plan or description>`

1. Run the No-Action checks 1–3 first (state may not exist yet — that is
   fine for `start`; create it in step 5).
2. **Unfinished-task guard:** if state exists and `current_stage` is not
   `completed`, report the active task + stage and require an explicit
   decision (finish it, or `reset`). Never silently replace.
3. Delegate to the task-planning skill with the raw input (ready plan or
   plain description). It produces a validated
   `docs/ai-context/TASK_PLAN.md`.
4. Site selection: exactly one installed Site → auto-select; several →
   ask; none → explain options and stop (see
   `references/frappe-project-detection.md`).
5. `CLI state init` (fresh state), then fill the task fields with
   `CLI state set <path> <value>` — `task_id`, `task_title`, `task_type`,
   `bench_path`, `app_name`, `app_path`, `target_site`, `branch`, and
   `base_commit` (current HEAD). Never hand-edit the JSON.
6. `CLI validate task-plan` must pass.
7. Planning gate (see workflow-gates.md) → `CLI state transition
   implementation --reason "plan accepted"`, then begin the
   task-implementation skill.

## `status`

Read-only. Never modifies anything. Gather:
`CLI detect --json`, `CLI state show`, `CLI git inspect`, and plan step
counts from `docs/ai-context/TASK_PLAN.md`. Render as in
[../examples/status-output.md](../examples/status-output.md), including
state/repository inconsistencies and blockers.

## `review`

1. `CLI validate completion-gate`. On failure: report every error; stay in
   `implementation`. Do not generate a prompt.
2. `CLI review bundle` — creates `docs/ai-context/reviews/round-NNN-prompt.md` and
   records the fingerprint (a blocking secret aborts with exit 7).
3. Record the round, prompt path, and fingerprint with `CLI state set`
   (see the codex-review skill's review-prompt-generation reference).
4. `CLI state transition codex_review --reason "review prompt round NNN"`.
5. Tell the user where the prompt is and to paste Codex's result back via
   `apply-review`.

## `apply-review <text | path>`

Input: pasted review text, a file path, or text in the arguments.
Delegate to the codex-review skill:

- Parse with `CLI review parse-result <file>` (write pasted text to
  `docs/ai-context/reviews/round-NNN-result.md` first — the round currently in
  state). Malformed output → reject, explain the required format, stay in
  `codex_review`.
- `CHANGES_REQUIRED` → save result, record round,
  `state transition review_fixes`, then work findings per the codex-review
  skill (validate each against the repository before applying).
- `APPROVED` → `CLI review fingerprint` must equal the recorded one
  (mismatch → approval rejected, generate a new bundle instead). Then run
  finalization (feature-changelog + project-context updates, review record),
  `CLI validate finalization-gate`, and
  `state transition ready_for_commit`.

## `commit`

Requires stage `ready_for_commit`. Delegate to the git-finalization skill:

- `CLI validate finalization-gate` must pass (fingerprint still matching).
- Generate the Conventional Commit message, exact `git add -- <path>`
  commands, and the excluded-files list. **Prepare only.**
- Execute the commit only when the user explicitly says to create it now.
- After execution: verify old HEAD ≠ new HEAD, committed files match the
  task, record hash/subject, `state transition committed`.

## `deploy`

Requires stage `committed`. Always ask first, exactly:

```text
The task has been committed successfully.

Deploy this task to the demo server?

1. Deploy now
2. Skip deployment
```

No SSH before the answer. Skip → record the skip fields with
`CLI state set`, then `state transition deployment_skipped`. Deploy →
deployment skill
(preflight → fast-forward pull → bench commands → verification →
`state transition deployed`).

## `testing`

Requires stage `deployed` or `deployment_skipped`. Delegate to the
testing-task skill: Arabic title + description from the approved behavior,
**copied to the host clipboard** with `CLI clipboard copy --preview` (text
on stdin) in logical Unicode order, so the user can paste them into their
task-management system —

```text
العنوان:
<Arabic title>

الوصف:
<Arabic description>
```

— and then **printed in the terminal** as the visual preview that same
command produces: the identical text reordered for a terminal without
bidirectional support. Repeat that preview output; never print the logical
Arabic, and never copy, save, or record the preview. Then
`CLI state set testing_task.status generated`,
`CLI state set testing_task.generated_at <UTC timestamp>`, and
`state transition completed`. When deployment was skipped, show the English
skip warning separately, after the preview (never inside the Arabic text).

The copy comes first and gates everything after it. If `clipboard copy`
exits 8 (no clipboard reachable from this session), stop: show the checked
methods it lists, print no Arabic text, record no state, and
transition nothing. Ask the user to install `wl-clipboard`, `xclip`, or
`xsel` — the plugin never installs packages — and to ask again.

No file is written: there is no `testing-task-ar.md` and no replacement for
it. If the user asks for the text again once the stage is `completed`,
regenerate it, copy it with `--preview` again, show that preview, and
change nothing.

## `reset`

1. Show exactly what will be cleared:
   `docs/ai-context/task-workflow.json`, `docs/ai-context/TASK_PLAN.md`,
   `docs/ai-context/implementation-summary.md`,
   `docs/ai-context/reviews/`.
   `CLI project paths` prints this list as `reset_paths`.
2. State what is **never** touched: Git changes, commits, app files,
   `docs/ai-context/PROJECT_CONTEXT.md`,
   `docs/ai-context/FEATURE_CHANGELOG.md`,
   `.claude/deployment.local.json`, `.claude/task-workflow.lock`, a legacy
   `testing-task-ar.md` left by an older plugin version, repository
   history.
3. Require explicit confirmation.
4. On confirmation: `CLI state init --force` and remove only the listed
   generated files.

## `help`

Print the canonical help text from
[../examples/help-output.md](../examples/help-output.md) **verbatim**. Do
not paraphrase it, reorder it, or regenerate the action descriptions from
memory — inaccurate help was the reason that file exists.

Strictly read-only: no detection, no state read or write, no Git commands,
no file creation. Help must work when no bench, application, or task
exists.

## Unknown Input

First token is not a recognized action:

- **No active task state** → treat the full input as a possible task
  description; if the intent is clearly a development task, route to
  `start` with it; otherwise ask.
- **Active task exists** → do not replace it. Show the active task, its
  stage, and the available actions. Never silently reset state.
