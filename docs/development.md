# Development

## Repository Architecture

```text
.claude-plugin/plugin.json   manifest (the only file that belongs here)
skills/                      one directory per skill, each with SKILL.md
  frappe-task/               the only user-invocable skill (orchestrator)
  <internal skills>/         invoked by the orchestrator, hidden from users
references/                  rules shared by several skills
templates/                   file shapes generated into target applications
scripts/cli.py               deterministic CLI dispatcher
scripts/core/                the logic the skills must not guess at
scripts/hooks/               hook implementations
hooks/hooks.json             hook configuration
bin/frappe-workflow          bash wrapper resolving the plugin root
tests/                       unit + integration suites and fixtures
docs/                        this documentation
```

Two rules shape the layout: only `plugin.json` lives under
`.claude-plugin/`, and anything a wrong guess could break lives in
`scripts/core/` rather than in prose.

## Skill Boundaries

| Skill | Owns |
|---|---|
| `frappe-task` | Argument parsing, routing, stage enforcement. Delegates everything else. |
| `project-context` | `docs/ai-context/PROJECT_CONTEXT.md`: full analysis, incremental updates, the update decision. |
| `feature-changelog` | `docs/ai-context/FEATURE_CHANGELOG.md`: baseline discovery, search, IDs, post-approval updates, index validation. |
| `task-planning` | `docs/ai-context/TASK_PLAN.md` from a ready plan or a description; scope discipline. |
| `task-implementation` | Executing steps, per-step validation, blockers, the summary, the completion gate. |
| `codex-review` | Bundles, result parsing, the fix loop, fingerprint-based invalidation. |
| `git-finalization` | Finalization gate, documentation timing, commit message, staging, verification. |
| `deployment` | Consent, preflight, ff-only pull, bench command matrix, verification. |
| `testing-task` | The Arabic testing task printed in the terminal (no file is written), and closing the workflow. |

Keep `SKILL.md` files short. Each states when to use it, inputs, outputs,
preconditions, stopping conditions, and prohibitions, then links to its own
references. Detailed procedure belongs in `references/`, not in the skill
body, and shared rules belong in the top-level `references/` directory so
they exist once.

## CLI Modules

| Module | Responsibility |
|---|---|
| `core/environment.py` | Bench/app/Site/Git detection; `run_bench_list_apps` is the single injectable seam for tests |
| `core/workflow_state.py` | Schema, transition table, atomic writes, blockers |
| `core/project_files.py` | Managed paths (the single source of truth for every managed location), the `.gitignore` block, legacy-layout migration, a minimal frontmatter parser |
| `core/feature_registry.py` | Index/entry parsing, search scoring, next-ID, registry validation |
| `core/git_checks.py` | Read-only Git inspection and the implementation fingerprint |
| `core/validators.py` | The six validators, including both gates |
| `core/review_bundle.py` | Prompt building, round numbering, result parsing |
| `core/deployment.py` | Config validation, SSH argv construction, preflight evaluation, command matrix |
| `core/security.py` | Secret patterns, redaction, forbidden filenames |
| `core/exit_codes.py` | The stable exit-code constants |

Constraints for anything added here: standard library only, `pathlib` for
paths, subprocess **argument arrays** (never `shell=True`), atomic writes
for state, UTF-8 everywhere, no side effects on import, and no function
that opens a network or SSH connection during tests.

## Tests and Fixtures

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Discovery from `tests/` puts that directory on `sys.path`, which is how
`tests/support.py` is importable as `support`; it also prepends
`scripts/` so `from core import ...` resolves.

`tests/support.py` provides the seams: `make_bench()` copies
`tests/fixtures/sample-bench/` into a temp directory and `git init`s the
app, `init_repo()` builds a throwaway repository, `write_repo_file()` and
`write_fixture_file()` place a managed file at a `project_files` constant
(creating `docs/ai-context/` on the way), and `GIT_ENV` pins the Git
identity while neutralizing the user's global and system Git config so
fixtures behave identically on every machine.

Tests address managed files through the `project_files` constants rather
than path literals, so the layout is defined in exactly one place. The only
deliberate exceptions are the legacy-migration tests, which must write the
old paths, and the help-output tests, which assert the old locations are
*absent*.

Fixture files (`sample-project-context.md`,
`sample-feature-changelog.md`, `sample-task-plan.md`,
`sample-review-result.md`) double as the canonical examples of each
generated format — when a template changes, the fixture changes with it, and
the validator tests will tell you if they drift apart.

Any credential-shaped value in a test must be obviously fake (containing
`example`, `fake`, `dummy`, or `sample`) so the scanner classifies it as
non-blocking. Tests that deliberately trigger a blocking finding construct
realistic-looking values inline and assert on the redacted output.

## Adding a New Workflow Action

1. Add the action to the argument hint in `skills/frappe-task/SKILL.md` and
   to the routing table there.
2. Write its procedure in
   `skills/frappe-task/references/command-routing.md` — preconditions,
   steps, which skill it delegates to, and its stopping condition.
3. If it needs a deterministic operation, add it to `scripts/cli.py` (with
   a subparser) and implement the logic in a `core/` module — never in the
   CLI dispatcher itself.
4. Add tests: unit tests for the core logic, an integration test that runs
   the CLI as a subprocess and asserts the exit code.
5. Document it in `docs/usage.md` and, if it touches state, in
   `docs/workflow.md`.

## Adding a Stage Safely

Stages are load-bearing; adding one touches four places that must agree:

1. `STAGES` and `ALLOWED_TRANSITIONS` in `core/workflow_state.py`, plus any
   stage/status consistency rule in `validate_state`.
2. `skills/frappe-task/references/workflow-stages.md` and
   `state-transitions.md`.
3. `docs/workflow.md` (both the prose list and the transition table).
4. Tests in `tests/unit/test_workflow_state.py` — a valid transition into
   it and a rejected one out of it.

Prefer extending an existing stage's semantics over adding a stage.
Never add a transition that skips a gate, and never add a backward
transition other than the existing approval invalidation.

## Updating Templates

Templates in `templates/` define what the plugin writes into target
applications. When you change one:

- Update the matching validator in `core/validators.py` (required sections
  and frontmatter keys are enumerated there).
- Update the matching fixture in `tests/fixtures/` so the "valid fixture
  passes" tests still exercise a realistic file.
- Update the skill reference that describes the format.
- Run the suite: the validator tests fail loudly when a required section is
  renamed in only one of the three places.

## Hook Testing

The hook is a plain script reading JSON on stdin, so it can be exercised
directly:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git reset --hard"}}' \
  | python3 scripts/hooks/guard_dangerous_commands.py
```

A blocked command prints a `hookSpecificOutput` object with
`permissionDecision: "deny"`; a safe command prints nothing. Both exit 0 —
the hook never fails the session, even on malformed input.

`tests/unit/test_hook_guard.py` covers the pattern list from both sides
(blocked variants including extra whitespace and compound commands, and a
list of safe commands that must never be blocked) plus the I/O contract.
When adding a pattern, add it to both lists — a pattern with no
"must still be allowed" counterpart tends to become a false positive.

## Consistency Checks Before Committing Plugin Changes

```bash
claude plugin validate . --strict
python3 -m unittest discover -s tests -p 'test_*.py'
grep -RInE 'TODO|FIXME|PLACEHOLDER|NotImplementedError' --exclude-dir=__pycache__ .
```

Stage names, action names, file paths, and status values appear in code,
skills, references, templates, and docs. When you change one, grep for it
across the whole repository — a stale stage name in a reference is a real
bug, because the model reads those files as instructions.
