# Arabic Testing Task Rules

## Output Shape

Generate only two labeled parts, with Arabic content. Copy them to the
host clipboard first — in their original logical Unicode order, which is
what the user pastes into the testing team's task-management system — then
show the terminal preview the copy command prints. Nothing is written to
disk:

```text
العنوان:
<short title>

الوصف:
<concise description>
```

## Title (العنوان)

- Short: one line, ideally ≤ 8 words.
- Names the behavior under test, not the development task
  ("اختبار نظام حجز المخزون المؤقت", not "تنفيذ ميزة الحجز").

## Description (الوصف)

- Concise: 2–4 sentences.
- Written from the tester's perspective: what to do, what must happen,
  which edge cases matter.
- Based strictly on the **approved implemented behavior** (plan Required
  Behavior + Acceptance Criteria as finally approved, and the finalized
  changelog entry) — not on the original request text.
- Cover: the main flow, the important negative/edge case(s), and the
  expected outcome of each.

## Example

```text
العنوان:
اختبار نظام حجز المخزون المؤقت

الوصف:
يرجى اختبار منطق حجز الكميات مؤقتاً، والتأكد من منع استخدام الكمية
المحجوزة في عمليات أخرى، مع تحرير الحجز عند إكمال أو إلغاء المستند.
```

## Never Include

- File paths, function names, DocType internal fieldnames, or any
  implementation detail.
- English text inside the Arabic content (product names that are
  inherently Latin-script are acceptable when the testers know them).
- The deployment-skipped warning (it is shown separately, in English).
- A restatement of only the original task title.

## Clipboard First, Then Terminal

The two blocks above are the whole deliverable. Deliver them in this order,
and never through a file.

### 1. Copy to the clipboard

Pipe the finished text into the helper on stdin, with a quoted here-doc so
nothing in the content is expanded or reinterpreted:

```bash
bin/frappe-workflow clipboard copy --preview <<'AR'
العنوان:
<Arabic title>

الوصف:
<Arabic description>
AR
```

The helper detects the environment on every run: inside WSL it copies to
the **Windows host clipboard** through `powershell.exe`, on a native Linux
desktop to the **session clipboard** through `wl-copy`, `xclip`, or `xsel`.
Nothing has to be configured, and the text never touches disk.

What reaches the clipboard is the text exactly as written above — logical
Unicode order, not reordered, not reshaped, not reversed. That is also the
only form to count characters of or validate against.

### 2. On success (exit `0`)

`--preview` makes the command print the hand-off block itself:

```text
Testing task copied to clipboard.

العنوان:
<the title, reordered for this terminal>

الوصف:
<the description, reordered for this terminal>

Paste from the clipboard for the original Unicode text.
```

Repeat that output verbatim in your reply, then the deployment-skipped
warning if the stage calls for it, then record the state and close the
workflow.

The preview exists because this terminal draws text strictly left to right
and has no Unicode bidirectional support, so logical Arabic reads backwards
in it. The preview is display-only: **never** print the logical Arabic text
yourself, never put the preview on the clipboard, in a file, or in the
workflow state, and never produce a reordered form by hand — the command is
the only source of it.

If the command reports instead that the preview could not be formatted, the
hand-off is still complete, because the clipboard already holds the text.
Pass that English warning on, do not print the logical Arabic as a
substitute, and continue normally.

### 3. On a missing clipboard (exit `8`)

Stop. The command prints which methods it checked and why each was
unavailable; show that, and ask the user to install `wl-clipboard`, `xclip`,
or `xsel` — or to run from a session that has a clipboard — and then to ask
for the testing task again. **Never** install a package yourself.

Do **not** print the Arabic text in this case — neither the logical form,
which this terminal shows backwards, nor a preview, which is not safe to
paste. And do not record `testing_task`, do not transition to `completed`,
and do not "rescue" the text into a file.

### Never a File

- **Never** create `docs/ai-context/testing-task-ar.md`,
  `.claude/testing-task-ar.md`, or any other file holding this content, and
  never store the Arabic text in the workflow state.
- Applications initialized by an older plugin version may still contain a
  `testing-task-ar.md` from the days when the file was saved. It is a
  legacy artifact: not read, not updated, not staged, not migrated, and not
  deleted — not even by a confirmed `reset`.
- If the user loses the text after the workflow reached `completed`,
  regenerate it from the same approved behavior, copy it with
  `--preview` again, show that preview, and write nothing: no state change,
  no transition, no file.

## Closing

Only after a successful copy — record only that the task was generated, and
when:

```bash
bin/frappe-workflow state set testing_task.status generated
bin/frappe-workflow state set testing_task.generated_at <UTC timestamp>
bin/frappe-workflow state transition completed --reason "testing task generated"
```

There is no `testing_task.path` to set. On a state file written by an older
plugin version the key may still exist; leave it alone.
