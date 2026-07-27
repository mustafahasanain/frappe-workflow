"""Deterministic core utilities for the frappe-workflow Claude Code plugin.

Every module in this package is standard-library only, side-effect free on
import, and safe to run outside a real Frappe bench (tests use synthetic
fixtures). Exit-code conventions used by the CLI live in :mod:`.exit_codes`.
"""

from . import exit_codes

__all__ = ["exit_codes"]
