# Frappe Workflow

A Claude Code plugin that runs the full lifecycle of a Frappe or ERPNext
task: understand the application, plan the work, implement it step by step,
get it reviewed by Codex, commit it, optionally deploy it, and hand it to
the testing team — without losing the thread when you close the editor.

The plugin's premise is that the parts of this process which must not be
guessed — which bench you are in, whether a feature already exists, whether
every plan step really passed its validation, whether an approval still
applies to the current code — belong in deterministic Python, not in
prose. The skills orchestrate; a helper CLI decides the facts.

**Status:** version 0.1.0, initial development version. Installable locally
from the bundled marketplace metadata; not published to any public
marketplace.

## What It Does

- **Understands the application** — builds `PROJECT_CONTEXT.md`, a concise
  navigation and architecture map, so future work does not start by
  rereading the repository.
- **Knows what already exists** — maintains `FEATURE_CHANGELOG.md`, a
  functional feature registry searched before every plan, so a request that
  is really an extension of existing behavior is treated as one.
- **Plans before it builds** — turns a prepared plan or a plain description
  into a validated, repository-aware `TASK_PLAN.md` with verifiable steps.
- **Implements with gates** — one step at a time, each validated before it
  counts as done; blockers are recorded, never skipped.
- **Reviews with Codex** — generates the review prompt, parses the verdict,
  runs the fix loop, and ties approval to a fingerprint of the exact code
  that was reviewed.
- **Commits precisely** — a Conventional Commit message derived from the
  actual diff, exact per-file staging, and a list of what was excluded.
- **Deploys only when told** — explicit confirmation, read-only preflight,
  fast-forward-only pull, and only the bench commands the changes justify.
- **Closes the loop** — a short Arabic testing task written from the
  approved behavior.
- **Survives a restart** — the persisted stage is the source of truth, so
  reopening Claude Code continues exactly where you left off.

## Supported Work

Both existing applications and greenfield projects:

| Task type | Use for |
|---|---|
| `feature` | New functionality |
| `change` | Behavior change to existing functionality |
| `bugfix` | Fixing broken behavior |
| `integration` | External systems, APIs, webhooks |
| `refactor` | Internal restructuring without behavior change |
| `project` | A complete project — modules, DocTypes, relationships, workflows, permissions, roles, reports, APIs, integrations, jobs, audit, error handling, testing, deployment, MVP phases, and deferred features |

## The Command

```text
/frappe-workflow:frappe-task [init|start|status|review|apply-review|commit|deploy|testing|reset|help] [input]
```

```text
/frappe-workflow:frappe-task init                          # once per application
/frappe-workflow:frappe-task start Add Telegram reporting  # plan and begin
/frappe-workflow:frappe-task status                        # read-only report
/frappe-workflow:frappe-task review                        # completion gate + Codex prompt
/frappe-workflow:frappe-task apply-review                  # feed the verdict back
/frappe-workflow:frappe-task commit                        # prepare the commit
/frappe-workflow:frappe-task deploy                        # ask, then deploy or skip
/frappe-workflow:frappe-task testing                       # Arabic testing task, close
```

Run it with no action to continue the active task from its recorded stage.
Full details in [docs/usage.md](docs/usage.md).

## Prerequisites

Python 3.10+, Bash, Git, and the Claude Code CLI. A Frappe bench is needed
only in the environments where you actually run tasks — the plugin's own
tests need none of it.

## Install

Permanent install (no flag needed afterwards):

```bash
claude plugin marketplace add /path/to/frappe-workflow
claude plugin install frappe-workflow@frappe-workflow-local
```

Then **restart Claude Code** — plugins load at session startup — and run
`/frappe-workflow:frappe-task help` from inside a Frappe application.

While developing the plugin itself, load the working tree directly so your
edits take effect immediately (an installed plugin is a snapshot copy):

```bash
cd ~/frappe-bench/apps/general_trading
claude --plugin-dir /path/to/frappe-workflow
```

Full instructions, including the optional deployment configuration, in
[docs/installation.md](docs/installation.md).

## Validate and Test

```bash
python3 -m json.tool .claude-plugin/plugin.json
claude plugin validate . --strict
python3 -m unittest discover -s tests -p 'test_*.py' -v
bin/frappe-workflow --help
```

The suite runs entirely offline against synthetic bench and Git fixtures:
no network, no SSH, no real Frappe installation, no modification of real
repositories.

## Safety Principles

- **Nothing destructive runs automatically.** A `PreToolUse` hook blocks
  `git reset --hard`, file-deleting `git clean`, force pushes,
  `git checkout -- .`, `rm -rf /`, `bench drop-site`, `bench reinstall`,
  and `DROP DATABASE`. The workflow never needs them.
- **You approve the irreversible steps.** Executing the commit, deploying,
  replacing an unfinished task, choosing a Site, and resetting are all your
  decisions. No SSH connection is opened before you answer the deploy
  question.
- **Staging is explicit.** Never `git add .` — every path is named, and the
  files deliberately left out are shown to you.
- **Secrets are scanned and redacted.** Private keys, tokens, passwords,
  credential URLs, and `.env`-style files block review, commit, and
  deployment; findings print as `abc...xyz`, never in full.
- **State is atomic.** The workflow state file is validated, written to a
  temp file, fsynced, and renamed into place; an interrupted write cannot
  leave invalid JSON.
- **Gates cannot be skipped.** A pending or blocked step fails the
  completion gate. A changed implementation fails the finalization gate.
  There are no override flags.
- **Facts are verified, not assumed.** Paths, DocTypes, Sites, feature
  history, and test results come from the repository and real command
  output.

## Files Created in Your Application

```text
<app-repository>/
├── PROJECT_CONTEXT.md            tracked
├── FEATURE_CHANGELOG.md          tracked
├── TASK_PLAN.md                  tracked
└── .claude/                      local, ignored via a managed .gitignore block
    ├── task-workflow.json
    ├── deployment.local.json
    ├── implementation-summary.md
    ├── testing-task-ar.md
    └── reviews/round-NNN-{prompt,result}.md
```

The `.gitignore` block is managed idempotently between marker comments; the
rest of your `.gitignore` is never touched. See
[references/file-lifecycle.md](references/file-lifecycle.md).

## Deployment Behavior

Deployment is optional and never implicit. After a verified commit you are
asked to deploy or skip. Skipping records a reason and moves on. Deploying
validates the local configuration, runs a read-only remote preflight
(connection, paths, branch, clean tree, remote commit, fast-forward
possible), performs a fast-forward-only pull, runs only the bench commands
the changed files justify (`migrate` for schema/patches/fixtures/hooks,
`build` for frontend assets, `restart` for Python and scheduler changes),
and verifies that the server HEAD equals the task commit. Any surprise —
local server changes, an unexpected branch, diverged history, a failed
command — stops the deployment and leaves recovery to a human.

## Current Limitations

- Codex review is a manual hand-off: the plugin generates the prompt and
  parses the result, but you run Codex yourself. There is no API
  integration.
- Site installation status requires a working `bench` executable; when it
  is unavailable the status is reported as unknown rather than guessed.
- The feature-similarity score is advisory only — actual files are always
  inspected before deciding whether functionality already exists.
- Manual UI validations depend on you performing and reporting them; the
  plugin records them as performed-by-user and never assumes a result.
- The frontmatter parser supports the scalar and simple-list subset of YAML
  the templates use, not arbitrary YAML.
- The dangerous-command hook does not parse shell quoting, so a command
  that merely mentions a blocked pattern (for example
  `grep -R 'git reset --hard' docs/`) is also blocked.
- One active task per repository at a time, and a single-file feature
  registry — both deliberate for this version.

## Documentation

| Document | Contents |
|---|---|
| [docs/installation.md](docs/installation.md) | Prerequisites, validation, development loading, deployment config |
| [docs/usage.md](docs/usage.md) | Every action, both input styles, the helper CLI, exit codes |
| [docs/workflow.md](docs/workflow.md) | Stages, transitions, gates, fingerprint, review loop |
| [docs/development.md](docs/development.md) | Architecture, skill boundaries, tests, extending the plugin |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Concrete failures and what to do about them |

Shared rules the skills follow live in
[references/](references/shared-workflow-rules.md): workflow rules,
[project detection](references/frappe-project-detection.md),
[Git safety](references/git-safety-rules.md),
[security](references/security-rules.md),
[file lifecycle](references/file-lifecycle.md), and
[error handling](references/error-and-blocker-handling.md).

## License

MIT — see [LICENSE](LICENSE).
