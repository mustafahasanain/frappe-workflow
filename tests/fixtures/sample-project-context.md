---
project_name: general_trading
context_version: 1
generated_at: 2026-07-20
analyzed_commit: 2f08f96
frappe_version: 15.x
erpnext_version: not installed
---

# Project Overview

General Trading manages stock reservation and purchasing behavior for a
trading company. Used by sales and warehouse staff.

# Application Structure

```text
general_trading/
├── general_trading/
│   ├── hooks.py
│   ├── modules.txt
│   ├── temp_reservation/
│   └── doctype/
```

# Architecture

Service modules per feature area; DocType controllers delegate to services.

# Core DocTypes

## Temporary Stock Reservation

- **Purpose:** Reserve stock during incomplete transactions.
- **Primary Service:** `general_trading/temp_reservation/service.py`
- **Primary DocType:** `Temporary Stock Reservation`
- **Used By:** Sales Invoice, Sales Order
- **Frontend Entry Points:**
  - `general_trading/public/js/sales.js`
- **Related Feature IDs:**
  - `FEAT-STOCK-001`
- **Important Constraint:** Reservation quantity must not exceed available stock.

# Business Logic

Reservation rules live in `general_trading/temp_reservation/service.py`.

# Hooks and Overrides

`hooks.py` wires Sales Invoice validate to the reservation service.

# APIs and Integrations

No external integrations yet.

# Background Jobs

None.

# Permissions and Roles

Standard Frappe roles; no custom permission logic.

# Testing and Development

`bench --site car.wash run-tests --app general_trading`

# Deployment Notes

Migrate required after DocType changes; no asset pipeline beyond public/js.

# Navigation Map

| Area | Start Here |
|---|---|
| Stock reservation | `general_trading/temp_reservation/service.py` |

# Known Constraints

Reservations must never exceed available quantity.
