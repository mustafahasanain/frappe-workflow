#!/usr/bin/env python3
"""frappe-workflow deterministic CLI.

Dispatches the helper commands used by the plugin skills. Human-readable
output by default, ``--json`` for machine output; errors go to stderr; exit
codes are stable and documented in scripts/core/exit_codes.py and docs/usage.md.

Validation-only commands never mutate state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from core import (  # noqa: E402
    clipboard,
    deployment,
    environment,
    exit_codes,
    feature_registry,
    git_checks,
    project_files,
    review_bundle,
    rtl_display,
    security,
    validators,
    workflow_state,
)


def _out(payload, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    elif isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _err(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def _repo_root(args) -> Path:
    root = Path(args.repo).resolve() if args.repo else Path.cwd()
    return root


def _print_errors(errors: list[str], as_json: bool, label: str) -> int:
    if errors:
        if as_json:
            _out({"valid": False, "errors": errors}, True)
        else:
            for error in errors:
                _err(error)
        return exit_codes.VALIDATION_FAILURE
    _out({"valid": True, "errors": []} if as_json else f"{label}: OK", as_json)
    return exit_codes.SUCCESS


# --------------------------------------------------------------------------
# Command handlers
# --------------------------------------------------------------------------

def cmd_detect(args) -> int:
    try:
        env = environment.detect(_repo_root(args))
    except environment.DetectionError as exc:
        _err(str(exc))
        return exit_codes.ENVIRONMENT_FAILURE
    data = env.to_dict()
    try:
        data["git"] = git_checks.inspect(env.git_root)
    except git_checks.GitError as exc:
        _err(str(exc))
        return exit_codes.ENVIRONMENT_FAILURE
    if args.json:
        _out(data, True)
    else:
        lines = [
            f"Bench:  {data['bench_path']}",
            f"App:    {data['app_name']} ({data['app_path']})",
            f"Branch: {data['git']['branch']}",
            f"HEAD:   {data['git']['head']}",
            "Sites:",
        ]
        for site in data["sites"]:
            mark = {True: "installed", False: "not installed", None: "unknown"}[
                site["app_installed"]
            ]
            lines.append(f"  - {site['name']}: {mark}")
        if not data["sites"]:
            lines.append("  (no sites found)")
        _out("\n".join(lines), False)
    return exit_codes.SUCCESS


def cmd_state(args) -> int:
    repo = _repo_root(args)
    try:
        if args.state_command == "show":
            state = workflow_state.load_state(repo)
            _out(state, True)
            return exit_codes.SUCCESS
        if args.state_command == "init":
            state = workflow_state.init_state(repo, overwrite=args.force)
            _out(state if args.json else "Initialized workflow state.", args.json)
            return exit_codes.SUCCESS
        if args.state_command == "set":
            value = args.value
            if args.json_value:
                try:
                    value = json.loads(args.value)
                except json.JSONDecodeError as exc:
                    _err(f"--json-value given but VALUE is not valid JSON: {exc}")
                    return exit_codes.INVALID_USAGE
            state = workflow_state.set_field(repo, args.path, value)
            _out(
                state if args.json else f"Set {args.path}.",
                args.json,
            )
            return exit_codes.SUCCESS
        if args.state_command == "transition":
            state = workflow_state.transition(repo, args.stage, reason=args.reason or "")
            _out(
                state if args.json else f"Stage is now '{state['current_stage']}'.",
                args.json,
            )
            return exit_codes.SUCCESS
        if args.state_command == "blocker":
            if args.blocker_command == "add":
                state = workflow_state.add_blocker(repo, args.message)
                _out(
                    state if args.json else f"Recorded blocker ({len(state['blockers'])} total).",
                    args.json,
                )
                return exit_codes.SUCCESS
            if args.blocker_command == "clear":
                workflow_state.clear_blockers(repo)
                _out({"blockers": []} if args.json else "Blockers cleared.", args.json)
                return exit_codes.SUCCESS
    except workflow_state.TransitionError as exc:
        _err(str(exc))
        return exit_codes.TRANSITION_REJECTED
    except workflow_state.StateError as exc:
        _err(str(exc))
        return exit_codes.VALIDATION_FAILURE
    _err("unknown state command")
    return exit_codes.INVALID_USAGE


def cmd_validate(args) -> int:
    repo = _repo_root(args)
    target = args.target
    if target == "project-context":
        errors = validators.validate_project_context(repo / project_files.PROJECT_CONTEXT)
    elif target == "feature-changelog":
        errors = validators.validate_feature_changelog(repo / project_files.FEATURE_CHANGELOG)
    elif target == "task-plan":
        errors = validators.validate_task_plan(repo / project_files.TASK_PLAN)
    elif target == "workflow-state":
        errors = validators.validate_workflow_state(repo)
    elif target == "completion-gate":
        errors = validators.validate_completion_gate(repo)
    elif target == "finalization-gate":
        errors = validators.validate_finalization_gate(repo)
    else:
        _err(f"unknown validate target '{target}'")
        return exit_codes.INVALID_USAGE
    return _print_errors(errors, args.json, target)


def cmd_feature(args) -> int:
    repo = _repo_root(args)
    changelog = repo / project_files.FEATURE_CHANGELOG
    if not changelog.is_file():
        _err(f"{changelog} not found")
        return exit_codes.VALIDATION_FAILURE
    text = changelog.read_text(encoding="utf-8")
    if args.feature_command == "search":
        results = feature_registry.search(text, args.query)
        if args.json:
            _out(results, True)
        elif results:
            for r in results:
                print(
                    f"{r['id']}  score={r['score']:3d}  [{r['likelihood']}]  "
                    f"{r['name']} ({r['module']}, {r['status']})"
                )
        else:
            print("No matching features found.")
        return exit_codes.SUCCESS
    if args.feature_command == "next-id":
        try:
            next_id = feature_registry.next_feature_id(text, args.type, args.module)
        except feature_registry.RegistryError as exc:
            _err(str(exc))
            return exit_codes.INVALID_USAGE
        _out({"next_id": next_id} if args.json else next_id, args.json)
        return exit_codes.SUCCESS
    if args.feature_command == "validate-index":
        errors = feature_registry.validate_registry(text)
        return _print_errors(errors, args.json, "feature index")
    _err("unknown feature command")
    return exit_codes.INVALID_USAGE


def cmd_git(args) -> int:
    repo = _repo_root(args)
    try:
        if args.git_command == "inspect":
            _out(git_checks.inspect(repo), True)
            return exit_codes.SUCCESS
        if args.git_command == "fingerprint":
            fingerprint = git_checks.implementation_fingerprint(repo)
            _out({"fingerprint": fingerprint} if args.json else fingerprint, args.json)
            return exit_codes.SUCCESS
        if args.git_command == "changed-files":
            data = {
                "changed": git_checks.changed_files(repo),
                "staged": git_checks.staged_files(repo),
                "untracked": git_checks.untracked_files(repo),
            }
            if args.json:
                _out(data, True)
            else:
                for kind, files in data.items():
                    print(f"{kind}:")
                    for f in files:
                        print(f"  {f}")
            return exit_codes.SUCCESS
    except git_checks.GitError as exc:
        _err(str(exc))
        return exit_codes.UNSAFE_REPOSITORY
    _err("unknown git command")
    return exit_codes.INVALID_USAGE


def cmd_review(args) -> int:
    repo = _repo_root(args)
    try:
        if args.review_command == "bundle":
            result = review_bundle.create_bundle(repo)
            _out(
                result
                if args.json
                else f"Created review prompt: {result['prompt_path']} "
                f"(round {result['round']}, fingerprint {result['fingerprint'][:12]}…)",
                args.json,
            )
            return exit_codes.SUCCESS
        if args.review_command == "fingerprint":
            fingerprint = git_checks.implementation_fingerprint(repo)
            _out({"fingerprint": fingerprint} if args.json else fingerprint, args.json)
            return exit_codes.SUCCESS
        if args.review_command == "parse-result":
            text = Path(args.file).read_text(encoding="utf-8")
            result = review_bundle.parse_result(text)
            _out(result, True)
            return exit_codes.SUCCESS
    except review_bundle.ReviewError as exc:
        _err(str(exc))
        return (
            exit_codes.SECURITY_FAILURE
            if "secret" in str(exc).lower()
            else exit_codes.VALIDATION_FAILURE
        )
    except (git_checks.GitError, OSError) as exc:
        _err(str(exc))
        return exit_codes.UNSAFE_REPOSITORY
    _err("unknown review command")
    return exit_codes.INVALID_USAGE


def cmd_deployment(args) -> int:
    repo = _repo_root(args)
    try:
        config = deployment.load_config(repo)
    except deployment.DeploymentError as exc:
        _err(str(exc))
        return exit_codes.DEPLOYMENT_PREFLIGHT_FAILURE

    if args.deployment_command == "validate-config":
        errors = deployment.validate_config(config)
        if errors:
            for error in errors:
                _err(error)
            return exit_codes.DEPLOYMENT_PREFLIGHT_FAILURE
        _out({"valid": True} if args.json else "deployment config: OK", args.json)
        return exit_codes.SUCCESS

    if args.deployment_command == "preflight":
        errors = deployment.validate_config(config)
        try:
            state = workflow_state.load_state(repo)
            errors += deployment.check_task_consistency(config, state)
        except workflow_state.StateError as exc:
            errors.append(str(exc))
        if errors:
            for error in errors:
                _err(error)
            return exit_codes.DEPLOYMENT_PREFLIGHT_FAILURE
        commands = deployment.remote_git_commands(config)
        payload = {
            "local_checks": "passed",
            "remote_preflight_commands": {
                name: deployment.build_ssh_command(config, argv)
                for name, argv in commands.items()
                if name != "pull"
            },
            "note": (
                "Remote commands are NOT executed by this CLI. Run them only "
                "after explicit user confirmation to deploy."
            ),
        }
        _out(payload, True)
        return exit_codes.SUCCESS

    if args.deployment_command == "required-commands":
        try:
            changed = git_checks.commit_files(repo, args.commit) if args.commit else (
                git_checks.changed_files(repo) + git_checks.staged_files(repo)
            )
        except git_checks.GitError as exc:
            _err(str(exc))
            return exit_codes.UNSAFE_REPOSITORY
        commands = deployment.required_frappe_commands(
            changed, config["app_name"], config["target_site"]
        )
        if args.json:
            _out(commands, True)
        elif commands:
            for item in commands:
                print(f"{' '.join(item['command'])}\n  reason: {item['reason']}")
        else:
            print("No bench commands required for these changes.")
        return exit_codes.SUCCESS

    if args.deployment_command == "verify":
        error = deployment.verify_deployment(args.expected, args.server_head)
        if error:
            _err(error)
            return exit_codes.DEPLOYMENT_PREFLIGHT_FAILURE
        _out({"verified": True} if args.json else "deployment verified", args.json)
        return exit_codes.SUCCESS

    _err("unknown deployment command")
    return exit_codes.INVALID_USAGE


def cmd_project(args) -> int:
    repo = _repo_root(args)

    if args.project_command == "paths":
        _out(
            {
                "ai_context_dir": project_files.AI_CONTEXT_DIR,
                "project_context": project_files.PROJECT_CONTEXT,
                "feature_changelog": project_files.FEATURE_CHANGELOG,
                "task_plan": project_files.TASK_PLAN,
                "workflow_state": project_files.WORKFLOW_STATE,
                "implementation_summary": project_files.IMPLEMENTATION_SUMMARY,
                "reviews_dir": project_files.REVIEWS_DIR,
                "claude_dir": project_files.CLAUDE_DIR,
                "deployment_config": project_files.DEPLOYMENT_CONFIG,
                "workflow_lock": project_files.WORKFLOW_LOCK,
                "tracked_shared_files": list(project_files.TRACKED_SHARED_FILES),
                "reset_paths": list(project_files.RESET_PATHS),
            },
            True,
        )
        return exit_codes.SUCCESS

    if args.project_command == "ensure-gitignore":
        result = project_files.ensure_gitignore_block(repo)
        if result["action"] == "conflict":
            _err(result["detail"])
            return exit_codes.VALIDATION_FAILURE
        _out(result if args.json else f".gitignore managed block: {result['action']}", args.json)
        return exit_codes.SUCCESS

    if args.project_command == "migrate":
        result = project_files.migrate_legacy_layout(repo, dry_run=args.dry_run)
        if result["conflicts"]:
            for item in result["conflicts"]:
                _err(
                    f"both {item['from']} and {item['to']} exist; move or remove "
                    "one of them manually [MIGRATE_CONFLICT]"
                )
            if args.json:
                _out(result, True)
            return exit_codes.VALIDATION_FAILURE
        if args.json:
            _out(result, True)
        elif result["moved"]:
            verb = "would move" if args.dry_run else "moved"
            for item in result["moved"]:
                print(f"{verb} {item['from']} -> {item['to']}")
        else:
            print("Layout is already current; nothing to migrate.")
        return exit_codes.SUCCESS

    _err("unknown project command")
    return exit_codes.INVALID_USAGE


# --- Terminal preview of the copied text -----------------------------------

# What the user is told after a successful copy. The clipboard holds the
# logical text; only these lines and the reordered block between them are
# terminal output, and the wording says which one to paste.
PREVIEW_HEADLINE = "Testing task copied to clipboard."
PREVIEW_FOOTER = "Paste from the clipboard for the original Unicode text."
PREVIEW_UNAVAILABLE = (
    "The terminal preview could not be formatted, so it is not shown. The "
    "clipboard already holds the original text — paste it from there."
)


def _preview_block(text: str) -> str:
    """Return the terminal-only rendering of *text*, or a warning instead.

    The copy has already succeeded by the time this runs, so no failure here
    may look like a failed hand-off: a broken rendering degrades to an
    English warning. The logical text is never printed as a fallback — a
    terminal without bidi support shows it backwards, and a task copied by
    hand out of that is corrupted.
    """
    try:
        visual = rtl_display.to_visual(text)
    except Exception:  # noqa: BLE001 - a preview must never fail a copy
        return f"{PREVIEW_HEADLINE}\n\n{PREVIEW_UNAVAILABLE}"
    return f"{PREVIEW_HEADLINE}\n\n{visual}\n\n{PREVIEW_FOOTER}"


def _print_preview(block: str) -> None:
    """Print *block*, falling back to UTF-8 bytes on an ASCII-only stdout."""
    try:
        print(block)
        return
    except UnicodeEncodeError:
        pass
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        print(f"{PREVIEW_HEADLINE}\n\n{PREVIEW_UNAVAILABLE}")
        return
    buffer.write(block.encode("utf-8") + b"\n")
    buffer.flush()


def cmd_clipboard(args) -> int:
    if args.clipboard_command != "copy":
        _err("unknown clipboard command")
        return exit_codes.INVALID_USAGE

    preview = getattr(args, "preview", False)
    if preview and args.json:
        _err("--preview is terminal-only output and cannot be combined with --json")
        return exit_codes.INVALID_USAGE

    # Read bytes, not text: the payload is Arabic UTF-8 and must not depend
    # on the locale encoding of the terminal it was piped from.
    try:
        text = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError as exc:
        _err(f"stdin is not valid UTF-8: {exc}")
        return exit_codes.INVALID_USAGE

    try:
        result = clipboard.copy(text)
    except clipboard.ClipboardError as exc:
        _err(f"{exc}; pipe the text to copy into this command on stdin")
        return exit_codes.INVALID_USAGE

    if args.json:
        _out(result.to_dict(), True)
    elif not result.copied:
        _err(result.render())
    elif preview:
        # The clipboard already holds the logical text; what follows is a
        # display rendering of that same text, built from a local copy and
        # kept nowhere.
        _print_preview(_preview_block(text.rstrip("\n")))
    else:
        _out(result.render(), False)
    return exit_codes.SUCCESS if result.copied else exit_codes.CLIPBOARD_UNAVAILABLE


def cmd_security(args) -> int:
    if args.security_command != "scan":
        _err("unknown security command")
        return exit_codes.INVALID_USAGE
    repo = _repo_root(args)
    if not git_checks.is_git_repo(repo):
        _err(f"{repo} is not a Git repository")
        return exit_codes.UNSAFE_REPOSITORY
    candidates = set(git_checks.changed_files(repo))
    candidates.update(git_checks.staged_files(repo))
    candidates.update(git_checks.untracked_files(repo))
    findings = security.scan_files(repo, candidates)
    blocking = security.blocking_findings(findings)
    if args.json:
        _out(
            {
                "findings": [f.to_dict() for f in findings],
                "blocking": len(blocking),
            },
            True,
        )
    else:
        for finding in findings:
            print(finding.render())
            print()
        if not findings:
            print("No possible secrets detected.")
    return exit_codes.SECURITY_FAILURE if blocking else exit_codes.SUCCESS


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frappe-workflow",
        description="Deterministic helper CLI for the frappe-workflow Claude Code plugin.",
    )
    parser.add_argument(
        "--repo",
        help="Target application repository root (default: current directory)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("detect", help="Detect bench, app, git, and candidate Sites")

    p_state = sub.add_parser("state", help="Workflow state operations")
    state_sub = p_state.add_subparsers(dest="state_command", required=True)
    state_sub.add_parser("show", help="Print the validated workflow state")
    p_init = state_sub.add_parser("init", help="Create a fresh workflow state")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing state (controlled reset)")
    p_set = state_sub.add_parser(
        "set", help="Set one existing state field atomically (not the stage)"
    )
    p_set.add_argument("path", help="Dotted field path, e.g. codex_review.status")
    p_set.add_argument("value")
    p_set.add_argument(
        "--json-value",
        action="store_true",
        dest="json_value",
        help="Parse VALUE as JSON so numbers, booleans, and null keep their type",
    )
    p_trans = state_sub.add_parser("transition", help="Move to a new stage")
    p_trans.add_argument("stage")
    p_trans.add_argument("--reason", default="")
    p_block = state_sub.add_parser("blocker", help="Manage blockers")
    block_sub = p_block.add_subparsers(dest="blocker_command", required=True)
    p_badd = block_sub.add_parser("add")
    p_badd.add_argument("message")
    block_sub.add_parser("clear")

    p_validate = sub.add_parser("validate", help="Run a validator")
    p_validate.add_argument(
        "target",
        choices=[
            "project-context",
            "feature-changelog",
            "task-plan",
            "workflow-state",
            "completion-gate",
            "finalization-gate",
        ],
    )

    p_feature = sub.add_parser("feature", help="Feature registry operations")
    feature_sub = p_feature.add_subparsers(dest="feature_command", required=True)
    p_search = feature_sub.add_parser("search")
    p_search.add_argument("query")
    p_next = feature_sub.add_parser("next-id")
    p_next.add_argument("--type", required=True)
    p_next.add_argument("--module", required=True)
    feature_sub.add_parser("validate-index")

    p_git = sub.add_parser("git", help="Read-only Git inspection")
    git_sub = p_git.add_subparsers(dest="git_command", required=True)
    git_sub.add_parser("inspect")
    git_sub.add_parser("fingerprint")
    git_sub.add_parser("changed-files")

    p_review = sub.add_parser("review", help="Codex review helpers")
    review_sub = p_review.add_subparsers(dest="review_command", required=True)
    review_sub.add_parser("bundle")
    review_sub.add_parser("fingerprint")
    p_parse = review_sub.add_parser("parse-result")
    p_parse.add_argument("file")

    p_deploy = sub.add_parser("deployment", help="Deployment helpers (never opens SSH)")
    deploy_sub = p_deploy.add_subparsers(dest="deployment_command", required=True)
    deploy_sub.add_parser("validate-config")
    deploy_sub.add_parser("preflight")
    p_req = deploy_sub.add_parser("required-commands")
    p_req.add_argument("--commit", help="Classify files of this commit instead of the working tree")
    p_verify = deploy_sub.add_parser("verify")
    p_verify.add_argument("--expected", required=True)
    p_verify.add_argument("--server-head", required=True, dest="server_head")

    p_project = sub.add_parser(
        "project", help="Managed project files, .gitignore block, and layout migration"
    )
    project_sub = p_project.add_subparsers(dest="project_command", required=True)
    project_sub.add_parser("paths", help="Print the centralized managed-file paths")
    project_sub.add_parser(
        "ensure-gitignore", help="Idempotently write the managed .gitignore block"
    )
    p_migrate = project_sub.add_parser(
        "migrate", help="Move an old-layout application onto docs/ai-context/"
    )
    p_migrate.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Report what would move without touching any file",
    )

    p_clipboard = sub.add_parser(
        "clipboard", help="Copy text to the clipboard of the detected environment"
    )
    clipboard_sub = p_clipboard.add_subparsers(dest="clipboard_command", required=True)
    p_copy = clipboard_sub.add_parser(
        "copy",
        help=(
            "Copy UTF-8 text read from stdin to the Windows host clipboard "
            "(WSL) or the desktop clipboard (native Linux)"
        ),
    )
    p_copy.add_argument(
        "--preview",
        action="store_true",
        help=(
            "After a successful copy, print the copied text reordered for a "
            "terminal that does not implement the Unicode bidirectional "
            "algorithm. Display only: the clipboard keeps the original text"
        ),
    )

    p_security = sub.add_parser("security", help="Secret scanning")
    security_sub = p_security.add_subparsers(dest="security_command", required=True)
    security_sub.add_parser(
        "scan", help="Scan changed, staged, and untracked files for possible secrets"
    )

    return parser


HANDLERS = {
    "detect": cmd_detect,
    "state": cmd_state,
    "validate": cmd_validate,
    "feature": cmd_feature,
    "git": cmd_git,
    "review": cmd_review,
    "deployment": cmd_deployment,
    "project": cmd_project,
    "clipboard": cmd_clipboard,
    "security": cmd_security,
}


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 2 on usage errors, 0 on --help; keep those codes.
        return int(exc.code or 0)
    handler = HANDLERS.get(args.command)
    if handler is None:
        _err(f"unknown command '{args.command}'")
        return exit_codes.INVALID_USAGE
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
