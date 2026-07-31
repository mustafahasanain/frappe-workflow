# Security Rules

Enforced by `scripts/core/security.py` (run it via
`bin/frappe-workflow security scan`) and by the review/commit/deployment
gates. A blocking finding stops review-bundle creation, commit preparation,
and deployment until resolved or explicitly confirmed as a safe fixture.

## What the Scanner Detects

- Private keys (`-----BEGIN ... PRIVATE KEY-----`) and SSH key files
  (`id_rsa`, `id_ed25519`, …).
- API/access/auth token assignments and secret-key assignments.
- Password and database-credential assignments.
- Database URLs containing embedded credentials.
- Telegram bot tokens, AWS access key IDs, GitHub/Slack token formats.
- `Authorization: Bearer/Basic …` headers with real-looking values.
- `.env` files and `.claude/deployment.local.json` staged or committed
  (forbidden by filename, regardless of content).

## What It Deliberately Ignores

Interpolation placeholders are the *shape* of a value, not a value, so they
never produce a finding: `{API_KEY}`, `{{ api_key }}`, `${DB_PASSWORD}`,
`$DB_PASSWORD`, `%(token)s`, `<your client secret here>`. This keeps the
scanner usable on Frappe configuration templates, f-strings, and Jinja
templates. A real value in the same position is still caught.

Values containing an obviously-fake marker (`example`, `fake`, `dummy`,
`sample`, `your-`, `changeme`, `xxxx`, `test-token`) are reported as
non-blocking rather than suppressed — you still see them, they just do not
stop the workflow.

## Redaction

Findings never contain the full secret. Values are reported as
`abc...xyz` (first three + last three characters):

```text
Possible secret detected in path/file.py:42
Pattern: token assignment
Value: abc...xyz
```

## What It Always Scans

The scan covers changed, staged, and untracked files. `docs/ai-context/` is
excluded from the *implementation fingerprint*, never from *scanning*: the
plan, the implementation summary, the review bundle, and the testing note
routinely quote configuration and command output, so they are exactly where
a pasted credential is most likely to land. A blocking finding in one of
them stops review, staging, and completion like any other.

## Deployment Configuration Privacy

- `.claude/deployment.local.json` is local-only, ignored via the managed
  `.gitignore` block, and never staged, bundled, or printed in full.
- It must not contain passwords or key material — fields whose names look
  like credentials fail validation. Use SSH keys / ssh-agent / SSH config.
- Private key contents are never printed; identity files are referenced by
  path only.

## No Logging Passwords

- CLI output, state files, review bundles, and deployment records never
  contain secret values.
- Remote command results are recorded with secrets redacted.

## No Command Interpolation

- All subprocess calls use argument arrays; `shell=True` is forbidden.
- Remote SSH commands are built from validated fields
  (host/user/branch/site/path character allow-lists) and shell-quoted with
  `shlex.quote` for the remote side.

## Review Prompts and Commits

- Review bundles are secret-scanned before being written; a blocking
  finding aborts bundle creation.
- The completion and finalization gates re-scan changed, staged, and
  untracked files, so a secret cannot reach a commit unnoticed.
- Tests must use obviously fake values (containing markers like `example`,
  `fake`, `dummy`, `sample`) so the scanner reports them as non-blocking.
