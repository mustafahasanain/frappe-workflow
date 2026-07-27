# Frappe Command Matrix

Run only what the actually-changed files require. Compute the set with:

```bash
bin/frappe-workflow deployment required-commands --commit <task-commit>
```

(implemented in `scripts/core/deployment.required_frappe_commands`; each
selected command comes with its reason — show the reasons to the user).

## Classification (conservative)

| Changed files | Command | Why |
|---|---|---|
| DocType JSON (`**/doctype/*/*.json`), `patches.txt`, `patches/`, `fixtures/`, `custom/`, `hooks.py` | `bench --site <site> migrate` | schema, patches, fixtures, and hook wiring apply at migrate |
| `public/js`, `public/css`, `public/scss`, `*.vue/jsx/tsx`, `package.json`, `webpack.config.js`, `build.json` | `bench build --app <app>` | frontend bundles must rebuild |
| Any backend `*.py` | `bench restart` | web workers and background workers must reload code |
| `tasks.py` / scheduler-related files | `bench restart` (covers scheduler reload) | scheduled job definitions changed |

Notes:

- `hooks.py` is classified into migrate **and** (being `.py`) restart —
  both are needed.
- Fixture export (`bench export-fixtures`) is a development-side action;
  on the server, fixtures apply via migrate.
- Explicitly-required patch commands beyond migrate only when the task
  plan says so.

## Execution Rules

- Run in matrix order: migrate → build → restart.
- Run inside the server bench directory via SSH argv arrays (see
  ssh-safety.md).
- Capture each command's exit status and trimmed output; a non-zero exit
  is a blocking error → stop, report, do not continue with remaining
  commands, do not retry blindly.
- Never blindly run every bench command "to be safe" — the whole point is
  the minimal justified set.
- Record commands and results (secrets redacted) in the deployment record.
