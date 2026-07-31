# Frappe Project Detection

How the plugin locates the Bench, the current application, and candidate
Sites. The deterministic implementation lives in
`scripts/core/environment.py`; run it via `bin/frappe-workflow detect --json`.

## Bench Detection

Walk upward from the current working directory until a directory contains
**all** of:

```text
apps/
sites/
sites/apps.txt
```

- Works from the app root, an app subdirectory, the bench root, or any
  subdirectory under the bench.
- Stops at the filesystem root; never searches the whole filesystem.
- No bench found → clear error, exit code 3.

## App Detection

1. Resolve the real current path.
2. Require it to be inside `<bench>/apps/`.
3. The app name is the first path component after `apps/`.
4. The app directory must exist.
5. The app must be listed in `sites/apps.txt`.
6. The app must be a Git repository.

Recorded facts: `bench_path`, `app_name`, `app_path`, `git_root`.

Do not rely on the folder name alone: the apps.txt listing and Git checks
must both pass. If run from the bench root (app ambiguous), report the
installed applications and require the user to select one.

## App versus Site

```text
Current App = Git repository containing application code
Target Site = Frappe Site used for migrate, testing, and development
```

One bench can host many apps and many Sites; one app may be installed on
zero, one, or many Sites. Never permanently bind an app to a Site — the
selected Site lives in task-level state (`target_site` in
`docs/ai-context/task-workflow.json`), not in
`docs/ai-context/PROJECT_CONTEXT.md`.

## Site Detection

Candidate Sites are directories under `sites/` that contain a
`site_config.json`. Always excluded:

```text
assets
common_site_config.json
apps.txt
apps.json
```

Installation status per Site is read with the supported command:

```bash
bench --site all list-apps        # preferred, at the bench root
bench --site <site> list-apps     # per-site fallback
```

Parsing safety: take only the first whitespace-separated token of each
output line (bench may append version/branch columns). When the `bench`
executable is unavailable or the command fails, installation status is
reported as **unknown** — never guessed.

## Multi-Site Behavior

- Installed on exactly **one** Site → select it automatically and record it
  in task state.
- Installed on **multiple** Sites → present the list; the user selects.
- Installed on **no** Site → explain the options (create a new Site, select
  an existing Site, install the app on a selected Site) and stop. Never
  create a Site or install an app automatically.

## Git Detection

`bin/frappe-workflow git inspect` reports (read-only, never mutates):

```text
current branch, HEAD commit, working tree status, staged files,
unstaged files, untracked files, configured remotes, tracking branch
```
