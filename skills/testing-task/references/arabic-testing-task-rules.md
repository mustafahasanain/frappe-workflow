# Arabic Testing Task Rules

## Output Shape

Generate only two labeled parts, with Arabic content:

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

## Storage and Closing

- Save the generated content to `.claude/testing-task-ar.md`.
- Record it and close the workflow:

```bash
bin/frappe-workflow state set testing_task.status generated
bin/frappe-workflow state set testing_task.path .claude/testing-task-ar.md
bin/frappe-workflow state set testing_task.generated_at <UTC timestamp>
bin/frappe-workflow state transition completed --reason "testing task generated"
```
