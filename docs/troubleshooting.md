# Troubleshooting

## Plugin validation fails

```bash
python3 -m json.tool .claude-plugin/plugin.json
claude plugin validate . --strict
```

The first command isolates JSON syntax errors (a trailing comma is the
usual culprit). If `--strict` fails but plain `validate` passes, the
manifest contains a field the current CLI does not recognize — remove or
correct it rather than suppressing the check. Validate the path to the
plugin **root**, not to `.claude-plugin/`.

## `Unknown command: /frappe-workflow:frappe-task`

This almost always means the plugin is not loaded in the session you are
typing into. **Plugins are loaded at session startup**, so a session
started with a plain `claude` will never see the command — including the
session you used to build or edit the plugin itself.

Confirm what is actually loaded:

```bash
claude plugin list
```

If `frappe-workflow` is absent, start a new session with the plugin:

```bash
cd ~/frappe-bench/apps/<your_app>
claude --plugin-dir /path/to/frappe-workflow
```

Then `/frappe-workflow:frappe-task help` works.

Verify the plugin itself is discoverable without starting a session:

```bash
claude --plugin-dir /path/to/frappe-workflow plugin details frappe-workflow
```

That prints the component inventory. A healthy plugin reports **Skills (9)**
including `frappe-task`, and **Hooks (1) PreToolUse**. If the skills are
listed there but the command is missing in your session, you are in a
session that was started without `--plugin-dir`.

`--plugin-dir` applies to one session only; there is no settings key that
loads a plugin directory permanently. For a permanent install, use the
local marketplace this repository ships:

```bash
claude plugin marketplace add /path/to/frappe-workflow
claude plugin install frappe-workflow@frappe-workflow-local
claude plugin list      # expect: frappe-workflow@... ✔ enabled
```

Then **restart Claude Code**. Installing does not affect the session you
are currently in — plugins load at startup.

Note that an installed plugin is a **copy**. Edits to the source repository
do not reach it, and `claude plugin update` compares version numbers only —
at an unchanged version it reports "already at the latest version" and
copies nothing. Reinstall to pick up edits:

```bash
claude plugin uninstall frappe-workflow
claude plugin install frappe-workflow@frappe-workflow-local
```

See [installation.md](installation.md).

## The skill does not appear

- The command is namespaced: `/frappe-workflow:frappe-task`, not
  `/frappe-task`.
- `frappe-task` is user-invocable by design and the internal skills are
  not — you should see exactly one command from this plugin.
- If validation passes and the command still does not appear, restart the
  session; plugin discovery happens at startup.

## Running the command inside the plugin repository

The plugin operates on a **Frappe application**, not on itself. Loading it
while your working directory is the plugin repository makes the command
available, but `init` will fail with exit code 3:

```text
error: No Frappe bench found. Walked up from '/path/to/frappe-workflow' to
the filesystem root without finding a directory containing apps/, sites/
and sites/apps.txt.
```

That is correct behavior. Change into a Frappe application first.

## Wrong working directory

Symptom: detection finds a different app than you expected, or none.

Start Claude Code inside the application repository:

```bash
cd ~/frappe-bench/apps/general_trading
claude --plugin-dir /path/to/frappe-workflow
```

Check what the plugin actually sees:

```bash
bin/frappe-workflow detect --json
```

You can also point the CLI elsewhere without changing directory:
`bin/frappe-workflow --repo ~/frappe-bench/apps/general_trading detect`.

## Bench not detected (exit code 3)

Detection walks upward looking for a directory that contains **all** of
`apps/`, `sites/`, and `sites/apps.txt`. It stops at the filesystem root
and never scans the whole disk.

```bash
ls ~/frappe-bench/apps ~/frappe-bench/sites ~/frappe-bench/sites/apps.txt
```

If `sites/apps.txt` is missing, the directory is not a usable bench — the
plugin will not guess.

## App not listed in sites/apps.txt

```text
error: Application 'general_trading' is not listed in sites/apps.txt (listed: frappe)
```

The directory exists under `apps/` but the bench does not know about it.
Install it with bench (`bench get-app` / `bench install-app`) so
`sites/apps.txt` lists it. The plugin deliberately does not edit
`apps.txt` — that file describes the bench's real state.

## Multiple Sites

When the app is installed on more than one Site, the plugin lists them and
asks you to choose; the choice is stored in task state (`target_site`), not
in `docs/ai-context/PROJECT_CONTEXT.md`, because an app is not permanently
bound to a Site.

When installation status shows `unknown`, the `bench` executable was not
available or `bench --site <site> list-apps` failed. Run it manually to see
why:

```bash
cd ~/frappe-bench && bench --site all list-apps
```

When the app is installed on **no** Site, the plugin explains the options
and stops. It will never create a Site or install an app for you.

## Workflow files are still at the old locations

An application initialized by an earlier version keeps `PROJECT_CONTEXT.md`,
`FEATURE_CHANGELOG.md`, and `TASK_PLAN.md` at its repository root and the
workflow files under `.claude/`. `init` migrates it; you can also do it
directly:

```bash
bin/frappe-workflow project migrate --dry-run
bin/frappe-workflow project migrate
```

Contents and the full review history are preserved,
`.claude/deployment.local.json` is never touched, and a repeat run does
nothing.

```text
error: both TASK_PLAN.md and docs/ai-context/TASK_PLAN.md exist; move or
remove one of them manually [MIGRATE_CONFLICT]
```

The command found the same file in both layouts and refuses to guess which
copy is current — **nothing is moved at all**, not even the paths that had
no conflict. Compare the two files, delete or rename the stale one, and
rerun.

## An active task will not resume on my other computer

The shared files are Git-*trackable*, not Git-*synchronized*. Nothing moves
between computers on its own:

1. On the first computer: `git add -- docs/ai-context/`, commit (a
   work-in-progress checkpoint commit is fine), and push the working
   branch.
2. On the second computer: pull or check out that branch.
3. Run `/frappe-workflow:frappe-task` with no action.

If `docs/ai-context/task-workflow.json` is missing on the second computer,
it was never committed or you are on a different branch — check
`git status` and `git branch --show-current` on both. If it appears in
`git status --ignored` as ignored, your `.gitignore` still carries entries
from an older version; run `bin/frappe-workflow project ensure-gitignore`
to repair the managed block.

`.claude/deployment.local.json` is deliberately per-computer: create it
separately on each machine from the example template.

## Invalid workflow state

```bash
bin/frappe-workflow validate workflow-state
```

Typical results and what they mean:

- `[STATE_MISSING]` — no active task. Run
  `/frappe-workflow:frappe-task init`, then `start`.
- `[STATE_INVALID_JSON]` — the file was hand-edited or a write was
  interrupted by something outside the plugin's atomic write path. Keep a
  copy, then `bin/frappe-workflow state init --force` to start clean; your
  Git changes, plan, and documentation are untouched.
- `[STATE_SCHEMA_VERSION]` — the file was written by a different plugin
  version. It is never silently migrated; decide explicitly whether to
  reset.
- `[STATE_STAGE_COMMIT_MISMATCH]` and friends — the stage and the recorded
  sub-status disagree (for example stage `committed` with no recorded
  commit). Check `git log` to see what actually happened before changing
  anything.

Never hand-edit `current_stage`. Use
`bin/frappe-workflow state transition <stage>`, which enforces the
transition table.

## Review fingerprint mismatch

```text
finalization gate: implementation changed after approval
(recorded ce072321a652…, current b098ba10705a…) [FINAL_FINGERPRINT_MISMATCH]
```

The approval belongs to code that no longer exists — an implementation file
changed after the prompt was generated. This is working as intended:

```bash
bin/frappe-workflow state transition review_fixes --reason "approval invalidated"
```

then rerun `review` for a new round. Editing anything under
`docs/ai-context/` — the plan, the feature changelog, the project context,
the workflow state, the summary, the reviews — does **not** cause this —
those three are excluded from the fingerprint. If you see a mismatch and
believe you only touched documentation, check what actually changed:

```bash
bin/frappe-workflow git changed-files
```

## Codex result rejected as malformed

Only two statuses are recognized, on their own line:

```markdown
- **Status:** APPROVED
- **Status:** CHANGES_REQUIRED
```

`CHANGES_REQUIRED` needs at least one finding, and every finding needs
`Severity` (High/Medium/Low), `Issue`, and `Required Fix`. Anything else —
"LGTM", "approved with minor comments", a missing status line — is rejected
rather than interpreted. Test a result file directly:

```bash
bin/frappe-workflow review parse-result docs/ai-context/reviews/round-001-result.md
```

## Dirty server repository

```text
server working tree has local changes; refusing to deploy [PREFLIGHT_DIRTY]
```

Someone edited files directly on the demo server. The plugin will not
stash, reset, or clean them — that would destroy work it cannot see. Log in
yourself, inspect `git status`, and decide what to keep. The same applies
to `[PREFLIGHT_BRANCH]` (server on an unexpected branch) and
`[PREFLIGHT_NO_FF]` (history diverged).

## SSH failure

- No SSH connection is ever opened before you answer the deploy question,
  so an SSH error during planning means something else is wrong.
- Test the connection outside the workflow first:
  `ssh -p <port> <user>@<host> true`.
- Host-key prompts are never auto-accepted and host-key checking is never
  disabled. If the host is new, connect once manually to establish trust.
- Authentication uses SSH keys, ssh-agent, or your SSH config. Passwords
  are not supported and a password-like field in the config fails
  validation (`[DEPLOY_STORED_SECRET]`).

## Deployment config missing or invalid

```text
error: Deployment configuration not found at .claude/deployment.local.json [DEPLOY_NO_CONFIG]
```

```bash
cp /path/to/frappe-workflow/templates/state/deployment.local.json.example \
   .claude/deployment.local.json
bin/frappe-workflow deployment validate-config
```

Common validation failures: `[DEPLOY_PORT]` (port outside 1–65535 or given
as a string), `[DEPLOY_PATH]` (`bench_path` must be absolute and free of
`..`), `[DEPLOY_BRANCH_MISMATCH]` (config branch differs from the task's
branch), `[DEPLOY_NO_COMMIT]` (the task has no verified commit yet —
deployment is only available after `commit`).

## Testing task unavailable

The `testing` action requires stage `deployed` or `deployment_skipped`.
From `committed`, run `deploy` first and answer the question — choosing
"Skip deployment" is a perfectly valid path to the testing task, and it
adds the separate warning that the changes are not in the testing
environment yet.

## The safety hook blocked something I needed

The hook blocks destructive commands the workflow never issues:
`git reset --hard`, file-deleting `git clean`, force pushes,
`git checkout -- .`, `git restore .`, `rm -rf /`, `bench drop-site`,
`bench reinstall`, and `DROP DATABASE`. If you genuinely need one of them,
run it yourself in a normal terminal — the block is deliberate and there is
no bypass flag.

One known false positive: a command that merely *mentions* a dangerous
string, such as `grep -R 'git reset --hard' docs/`, is blocked. The guard
does not parse shell quoting and prefers over-blocking to under-blocking.
Work around it by searching with a different pattern (`grep -R 'reset --ha'`)
or by using the file-search tools.

## Tests fail after changing a template

Required sections and frontmatter keys are enumerated in
`scripts/core/validators.py`, and the fixtures in `tests/fixtures/` are
validated against them. Renaming a section in a template means updating the
validator, the fixture, and the skill reference that documents the format.
See [development.md](development.md) for the checklist.
