---
project_name: <app name>
context_version: 1
generated_at: <YYYY-MM-DD>
analyzed_commit: <full or short commit hash>
frappe_version: <e.g. 15.x, or Unknown>
erpnext_version: <e.g. 15.x, not installed, or Unknown>
---

# Project Overview

One or two paragraphs: what this application does, who uses it, and the
business domain it serves.

# Application Structure

```text
<app_name>/
├── <app_name>/
│   ├── hooks.py
│   ├── modules.txt
│   └── <module>/
└── ...
```

Short notes on where each top-level area lives.

# Architecture

How the application is put together: layering, main services, how modules
relate, notable patterns (service modules, controller overrides, mixins).

# Core DocTypes

For each important DocType, a component block:

## <Component Name>

- **Purpose:** What it exists for.
- **Primary Service:** `path/to/service.py`
- **Primary DocType:** `DocType Name`
- **Used By:** Consuming transactions or features.
- **Frontend Entry Points:**
  - `path/to/client_script.js`
- **Related Feature IDs:**
  - `FEAT-...`
- **Important Constraint:** The one rule a future change must not break.

# Business Logic

Where the meaningful business rules live and which files implement them.
Reference files; do not copy their contents.

# Hooks and Overrides

What `hooks.py` wires up: doc_events, overrides, fixtures, scheduled jobs,
whitelisted methods, and where each handler is implemented.

# APIs and Integrations

Whitelisted endpoints, external services, webhooks, and the files that
implement them.

# Background Jobs

Scheduled and queued jobs, their triggers, and their handler locations.

# Permissions and Roles

Custom roles, permission logic, and any permission query conditions.

# Testing and Development

How tests are organized and run for this app; anything unusual about the
development loop (build steps, required fixtures, seed data).

# Deployment Notes

Environment-specific requirements that affect future tasks: migration
expectations, asset builds, workers, or external service configuration.

# Navigation Map

Task-oriented pointers: "to change X, look at Y".

| Area | Start Here |
|---|---|
| <feature area> | `path/to/entry_point.py` |

# Known Constraints

Technical and business constraints that future tasks must respect.
