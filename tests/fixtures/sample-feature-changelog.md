# Feature Changelog

## Feature Index

| ID | Type | Feature | Module | Status | Keywords |
|---|---|---|---|---|---|
| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Active | reservation, stock, availability |
| CHANGE-PURCHASE-001 | Change | Purchase Unit Price Calculation | Purchase | Active | unit price, base rate |
| INT-TELEGRAM-001 | Integration | Telegram Reports | Telegram | Active | telegram, bot, reporting |

---

# Stock

## [FEATURE] Temporary Stock Reservation

- **ID:** FEAT-STOCK-001
- **Status:** Active
- **Added:** 2026-07-20
- **Last Updated:** 2026-07-26
- **Module:** Stock
- **Doctypes:** Temporary Stock Reservation, Sales Invoice
- **Keywords:** stock reservation, reserved quantity, availability, temporary hold

### Purpose

Prevent reserved stock quantities from being consumed by other transactions.

### Behavior

- Creates a temporary reservation while the transaction is in progress.
- Deducts reserved quantities from available stock.
- Releases the reservation when the transaction is completed or cancelled.

### Main Files

- `general_trading/temp_reservation/service.py`
- `general_trading/doctype/temporary_stock_reservation/`
- `general_trading/public/js/sales.js`

### Notes

Reservation quantity must not exceed available stock.

### Change History

#### 2026-07-20 — Initial implementation

Added temporary stock reservation support.

#### 2026-07-26 — Added Sales Order support

Extended the existing reservation logic to support Sales Order.

# Purchase

## [CHANGE] Purchase Unit Price Calculation

- **ID:** CHANGE-PURCHASE-001
- **Status:** Active
- **Added:** 2026-07-22
- **Last Updated:** 2026-07-22
- **Module:** Purchase
- **Doctypes:** Purchase Invoice
- **Keywords:** unit price, base rate, purchase calculation

### Purpose

Calculate base unit prices consistently across purchase documents.

### Behavior

- Derives the base unit price from the supplier rate and conversion factor.

### Main Files

- `general_trading/purchase/pricing.py`

### Change History

#### 2026-07-22 — Initial implementation

Corrected base unit price calculation.

# Telegram

## [INTEGRATION] Telegram Reports

- **ID:** INT-TELEGRAM-001
- **Status:** Active
- **Added:** 2026-07-24
- **Last Updated:** 2026-07-24
- **Module:** Telegram
- **Doctypes:** Telegram Report Settings
- **Keywords:** telegram, bot, reporting, scheduled reports

### Purpose

Send scheduled business reports to Telegram chats.

### Behavior

- Sends configured reports to Telegram on a schedule.

### Main Files

- `general_trading/telegram/reports.py`

### Change History

#### 2026-07-24 — Initial implementation

Added scheduled Telegram reporting.
