# Arabic Testing Task Rules

## Output Shape

Generate only two labeled parts, with Arabic content. Copy them to the
host clipboard first, then print them directly in the terminal, so the user
can paste them into the testing team's task-management system. Nothing is
written to disk:

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
bin/frappe-workflow clipboard copy <<'AR'
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

### 2. On success (exit `0`)

Print the same two blocks in the terminal and say that they are already on
the clipboard. Then record the state and close the workflow.

### 3. On a missing clipboard (exit `8`)

Stop. The command prints which methods it checked and why each was
unavailable; show that, and ask the user to install `wl-clipboard`, `xclip`,
or `xsel` — or to run from a session that has a clipboard — and then to ask
for the testing task again. **Never** install a package yourself.

Do **not** print the Arabic text in this case: a terminal shows it visually
reordered, so copying it by hand from there produces a corrupted task. And
do not record `testing_task`, do not transition to `completed`, and do not
"rescue" the text into a file.

### Never a File

- **Never** create `docs/ai-context/testing-task-ar.md`,
  `.claude/testing-task-ar.md`, or any other file holding this content, and
  never store the Arabic text in the workflow state.
- Applications initialized by an older plugin version may still contain a
  `testing-task-ar.md` from the days when the file was saved. It is a
  legacy artifact: not read, not updated, not staged, not migrated, and not
  deleted — not even by a confirmed `reset`.
- If the user loses the text after the workflow reached `completed`, copy
  and print it again from the same approved behavior and write nothing: no
  state change, no transition, no file.

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
