---
task_id: TASK-2026-001
task_title: Add Telegram Reporting
task_type: integration
status: planned
created_at: 2026-07-26
updated_at: 2026-07-26
suggested_branch: feature/almasah-telegram-reports
app_name: general_trading
target_site: car.wash
bench_path: /home/mustafa/frappe-bench
related_features:
  - INT-TELEGRAM-001
---

# Task Summary

Add scheduled Telegram reporting for daily sales totals.

## Objective

Send a daily sales summary to a configured Telegram chat.

## Business Requirement

Management wants daily sales numbers in Telegram without opening the ERP.

## Current Behavior

Telegram integration sends stock reports only; no sales summary exists.

## Required Behavior

A daily scheduled job sends the sales summary to the configured chat.

## Existing Feature Analysis

Search matched INT-TELEGRAM-001 (score 78, related existing feature).
Inspected `general_trading/telegram/reports.py`: sales summaries are not
implemented. This task extends INT-TELEGRAM-001.

## Scope

### In Scope

- Daily sales summary report content.
- Scheduler entry for daily sending.

### Out of Scope

- New report types beyond sales summary.
- Changing existing stock reports.

## Assumptions

- The Telegram bot credentials are already configured in settings.

## Dependencies

- Existing Telegram Report Settings DocType.

## Repository Verification Required

- Confirm the scheduler section format in `hooks.py`.

## Implementation Plan

### 1. Add sales summary builder

- **Status:** Pending
- **Action:** Create the sales summary content builder.
- **Location:** `general_trading/telegram/sales_summary.py`
- **Purpose:** Produce the daily sales totals message.
- **Implementation Details:**
  - Aggregate submitted Sales Invoices for the previous day.
  - Format totals as a short message.
- **Expected Result:** Builder returns the formatted summary text.
- **Validation:** Unit test with two fixture invoices asserts the total line.
- **Dependencies:** None.

### 2. Schedule daily sending

- **Status:** Pending
- **Action:** Register a daily scheduler event that sends the summary.
- **Location:** `general_trading/hooks.py`
- **Purpose:** Deliver the summary automatically every day.
- **Implementation Details:**
  - Add scheduler_events daily entry calling the sender.
  - Reuse the existing Telegram send helper.
- **Expected Result:** The job appears in the scheduler and sends the message.
- **Validation:** bench --site car.wash migrate succeeds; scheduled job listed.
- **Dependencies:** Step 1.

## Expected Files

### Files to Create

- `general_trading/telegram/sales_summary.py`

### Files to Modify

- `general_trading/hooks.py`

### Files Requiring Verification

- `general_trading/telegram/reports.py`

## Data Model Changes

None.

## Permissions and Security

No new permissions; bot token stays in existing settings DocType.

## Backward Compatibility

Existing stock reports must continue to send unchanged.

## Migration and Deployment Requirements

Migrate required for the scheduler hook change; restart workers.

## Testing Plan

### Automated Tests

- Unit test for the summary builder.

### Manual UI Tests

- Trigger the job manually and confirm the Telegram message arrives.

### Regression Tests

- Existing stock report still sends.

### Integration Tests

- End-to-end scheduled run on the development Site.

## Acceptance Criteria

- Daily summary message arrives in the configured chat with correct totals.
- Existing reports are unaffected.

## Risks and Constraints

- Telegram API rate limits on large messages.

## Optional Follow-up Improvements

- Weekly summary variant.
