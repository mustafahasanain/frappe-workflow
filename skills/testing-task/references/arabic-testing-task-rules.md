# Arabic Testing Task Rules

## Output Shape

Generate only two labeled parts, with Arabic content, and print them
directly in the terminal so the user can copy them into the testing team's
task-management system. Nothing is written to disk:

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

## Terminal Output Only

- The two blocks above are the whole deliverable, printed in the terminal.
- **Never** create `docs/ai-context/testing-task-ar.md`,
  `.claude/testing-task-ar.md`, or any other file holding this content, and
  never store the Arabic text in the workflow state.
- Applications initialized by an older plugin version may still contain a
  `testing-task-ar.md` from the days when the file was saved. It is a
  legacy artifact: not read, not updated, not staged, not migrated, and not
  deleted — not even by a confirmed `reset`.
- If the user loses the printed text after the workflow reached
  `completed`, print it again from the same approved behavior and write
  nothing: no state change, no transition, no file.

## Closing

Record only that the task was generated, and when:

```bash
bin/frappe-workflow state set testing_task.status generated
bin/frappe-workflow state set testing_task.generated_at <UTC timestamp>
bin/frappe-workflow state transition completed --reason "testing task generated"
```

There is no `testing_task.path` to set. On a state file written by an older
plugin version the key may still exist; leave it alone.
