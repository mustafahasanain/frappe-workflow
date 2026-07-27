# SSH Safety

## Building Commands

Always through `scripts/core/deployment.build_ssh_command`:

- Local side: subprocess **argument arrays** — never a concatenated shell
  string, never `shell=True`.
- Remote side: the remote command is an argv list joined with
  `shlex.quote` per argument — no untrusted value is ever interpolated
  into a shell script.
- All values (host, user, remote, branch, site, paths) passed validation
  first (character allow-lists in `validate_config`); a value that fails
  validation never reaches an SSH command line.
- `ssh -p <port> [-i <identity_file>] -- user@host '<quoted command>'` —
  the `--` prevents option injection from the host field.

## Host Keys

- Never disable host-key checking (`StrictHostKeyChecking=no` is
  forbidden).
- Never auto-accept unknown host keys. On a host-key failure or
  first-contact prompt, stop and tell the user to establish the trust
  relationship themselves (one manual `ssh` login) before deploying.

## Credentials

- No passwords in config, commands, output, or records.
- Keys come from ssh-agent, the user's SSH config, or the configured
  `identity_file` **path** — key contents are never read or printed.
- Command output is checked before recording; anything secret-looking is
  redacted (security-rules.md).

## Connection Discipline

- First SSH connection happens only after the explicit "Deploy now"
  answer.
- Only the documented preflight, pull, bench, and verification commands
  run — no exploratory shells, no server edits.
- One failure = stop. The server is left exactly as found (all preflight
  commands are read-only; the only mutating commands are the ff-only pull
  and the required bench commands, in that order).
