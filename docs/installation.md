# Installation

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Standard library only; no third-party packages needed |
| Bash | For the `bin/frappe-workflow` wrapper |
| Git | Read-only inspection plus explicit staging/commit you approve |
| Claude Code CLI | The plugin host (developed against 2.1.x) |
| Frappe Bench | Only in the target environments where tasks run |

The plugin itself has no runtime dependencies beyond Python's standard
library. The test suite uses `unittest`; nothing else is required.

## 1. Validate the Plugin

From the plugin repository root:

```bash
python3 -m json.tool .claude-plugin/plugin.json
claude plugin validate . --strict
```

`validate` checks the manifest. `--strict` additionally fails on
unrecognized fields and missing metadata, which is what you want in CI.

## 2. Verify the Helper CLI and Tests

```bash
test -x bin/frappe-workflow && echo "wrapper is executable"
bin/frappe-workflow --help
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

All tests run offline against synthetic fixtures — no bench, no network,
no SSH.

## 3. Load the Plugin in Development Mode

The currently supported way to load a plugin straight from a directory is
the `--plugin-dir` flag, which loads it for that session:

```bash
cd ~/frappe-bench/apps/general_trading
claude --plugin-dir /path/to/frappe-workflow
```

Repeat the flag to load several plugins
(`--plugin-dir A --plugin-dir B`). The path may also point at a `.zip`.

Inside the session, confirm discovery by running the command:

```text
/frappe-workflow:frappe-task help
```

Loading the plugin also activates its `PreToolUse` safety hook, which
blocks destructive Bash commands (see
[../references/git-safety-rules.md](../references/git-safety-rules.md)).

## 4. Persistent Installation (no flag needed)

`--plugin-dir` lasts one session. For a permanent install, this repository
ships local marketplace metadata at `.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace add /path/to/frappe-workflow
claude plugin install frappe-workflow@frappe-workflow-local
claude plugin list
```

`claude plugin list` should report `frappe-workflow@frappe-workflow-local`
as `✔ enabled`. **Restart Claude Code** — plugins are loaded at session
startup, so the command does not appear in an already-running session.

### Installed plugins are a snapshot, not a live link

`claude plugin install` copies the plugin into
`~/.claude/plugins/cache/frappe-workflow-local/frappe-workflow/<version>/`.
Editing the source repository afterwards has **no effect** on the installed
copy.

`claude plugin update frappe-workflow@frappe-workflow-local` does not help
on its own: it compares **version numbers**, so while `plugin.json` still
says `0.1.0` it reports "already at the latest version" and copies nothing.
Two things actually refresh the snapshot:

```bash
# Either reinstall (picks up edits at the same version)
claude plugin uninstall frappe-workflow
claude plugin install frappe-workflow@frappe-workflow-local

# Or bump "version" in .claude-plugin/plugin.json and marketplace.json, then
claude plugin update frappe-workflow@frappe-workflow-local
```

Either way, restart Claude Code afterwards.

That friction matters if you are developing the plugin. Choose accordingly:

| You are | Use |
|---|---|
| Using the plugin on real work | `claude plugin install` — persistent, no flag |
| Editing the plugin itself | `claude --plugin-dir /path/to/frappe-workflow` — always reflects your latest edits |

To remove it:

```bash
claude plugin uninstall frappe-workflow
claude plugin marketplace remove frappe-workflow-local
```

This marketplace is local to your machine. Nothing is published anywhere.

## Working Directory

Start Claude Code **inside the Frappe application repository** you want to
work on:

```bash
cd ~/frappe-bench/apps/general_trading
claude --plugin-dir /path/to/frappe-workflow
```

Detection walks upward from the current directory to find the bench, so a
subdirectory of the app also works. Running from the bench root leaves the
application ambiguous and the plugin will ask you to pick one.

## Deployment Configuration (optional)

Deployment is optional and off by default. To enable it for an application,
copy the example into the app repository and edit it:

```bash
cp /path/to/frappe-workflow/templates/state/deployment.local.json.example \
   ~/frappe-bench/apps/general_trading/.claude/deployment.local.json
```

That file is local-only and is covered by the managed `.gitignore` block
the `init` action maintains. Never put passwords in it — use SSH keys,
ssh-agent, or your SSH config. See
[../references/security-rules.md](../references/security-rules.md).

## Uninstalling

Stop passing `--plugin-dir`. Nothing is installed globally. Files the
plugin generated inside a target application (`PROJECT_CONTEXT.md`,
`FEATURE_CHANGELOG.md`, `TASK_PLAN.md`, `.claude/`) stay where they are and
are yours to keep or delete.
