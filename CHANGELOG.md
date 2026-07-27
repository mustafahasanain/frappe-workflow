# Changelog

All notable changes to this plugin are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] — 2026-07-27

Initial development version of the Frappe Workflow plugin.

### Added

- **Workflow engine** — nine-stage task lifecycle (`planning`,
  `implementation`, `codex_review`, `review_fixes`, `ready_for_commit`,
  `committed`, `deployment_skipped`, `deployed`, `completed`) with an
  enforced transition table and recorded transition history.
- **Atomic workflow state** — `.claude/task-workflow.json` written through
  validate → temp file → fsync → atomic replace, with an advisory lock on
  POSIX platforms; invalid or unknown-schema state is reported, never
  silently repaired.
- **Main user command** — `/frappe-workflow:frappe-task` with the actions
  `init`, `start`, `status`, `review`, `apply-review`, `commit`, `deploy`,
  `testing`, `reset`, `help`, plus no-action resume from the persisted
  stage.
- **Internal skills** — `project-context`, `feature-changelog`,
  `task-planning`, `task-implementation`, `codex-review`,
  `git-finalization`, `deployment`, `testing-task`, each with its own
  references and explicit boundaries.
- **Deterministic CLI** — `bin/frappe-workflow` wrapping `scripts/cli.py`:
  environment detection, state operations (including `state set` for
  atomic, schema-checked single-field updates), six validators, feature search
  and ID generation, Git inspection and fingerprinting, review bundling and
  result parsing, deployment configuration/preflight/command-matrix/
  verification helpers, and secret scanning. Stable exit codes 0–7, JSON
  output via `--json`, errors on stderr.
- **Environment detection** — upward bench search (`apps/`, `sites/`,
  `sites/apps.txt`), app validation against `sites/apps.txt` and Git, and
  Site detection that distinguishes one / multiple / no installed Sites and
  never creates a Site or installs an app.
- **Project context and feature registry** — `PROJECT_CONTEXT.md` full and
  incremental analysis rules keyed to `analyzed_commit`;
  `FEATURE_CHANGELOG.md` baseline discovery, advisory similarity search,
  deterministic `<TYPE>-<MODULE>-<NNN>` IDs, and full index/detail
  consistency validation.
- **Gates** — planning, completion (before review), approval, and
  finalization (before commit) gates with machine-readable rule identifiers.
- **Codex review loop** — review bundle generation, `APPROVED` /
  `CHANGES_REQUIRED` parsing with per-finding validation, append-only round
  history under `.claude/reviews/`, and a SHA-256 implementation
  fingerprint that invalidates approval when implementation code changes
  (documentation-only finalization files are excluded by construction).
- **Git finalization** — Conventional Commit generation from the actual
  diff, exact `git add -- <path>` staging with an excluded-files report, no
  AI attribution, and post-commit verification before the `committed`
  stage.
- **Deployment safety** — explicit deploy/skip confirmation before any SSH,
  configuration validation, local and read-only remote preflight,
  fast-forward-only pull, a conservative bench command matrix driven by
  changed-file categories, and deployed-commit verification.
- **Arabic testing task** — short Arabic title and description generated
  from approved behavior, saved to `.claude/testing-task-ar.md`, with a
  separate English warning when deployment was skipped.
- **Security scanning** — conservative redacted detection of private keys,
  tokens, passwords, credential URLs, and forbidden filenames across
  changed, staged, and untracked files; findings block review, commit, and
  deployment. Interpolation placeholders (`{API_KEY}`, `${VAR}`,
  `%(name)s`, `<value>`) are recognized as template syntax rather than
  secrets.
- **Safety hook** — `PreToolUse` Bash guard blocking destructive commands
  (`git reset --hard`, `git clean -fd`, force pushes, `git checkout -- .`,
  `rm -rf /`, `bench drop-site`, `bench reinstall`, `DROP DATABASE`) with
  fail-safe handling of malformed hook input.
- **Templates** — project context, feature changelog, task plan, workflow
  state, deployment config example, implementation summary, review prompt
  and result, and the Arabic testing task.
- **Tests** — 185 `unittest` cases across unit and integration suites using
  synthetic bench and Git fixtures, including an end-to-end walkthrough
  from `planning` to `completed` that exercises the gates, the fingerprint,
  and approval invalidation in sequence; no network, no SSH, no real Frappe
  installation required.
- **Local marketplace metadata** — `.claude-plugin/marketplace.json`, so the
  plugin can be installed persistently with
  `claude plugin marketplace add <path>` followed by
  `claude plugin install frappe-workflow@frappe-workflow-local`, instead of
  passing `--plugin-dir` every session.
- **Documentation** — README plus installation, usage, workflow,
  development, and troubleshooting guides.

### Notes

This is the initial development version. It has not been published to a
marketplace and carries no production-adoption claims. Version comparison
links are omitted until a repository URL exists.
