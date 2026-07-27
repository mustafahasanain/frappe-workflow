# Feature Changelog

## Feature Index

| ID | Type | Feature | Module | Status | Keywords |
|---|---|---|---|---|---|
| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Active | reservation, stock, availability |

---

# Stock

## [FEATURE] Temporary Stock Reservation

- **ID:** FEAT-STOCK-001
- **Status:** Active
- **Added:** 2026-07-20
- **Last Updated:** 2026-07-20
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
