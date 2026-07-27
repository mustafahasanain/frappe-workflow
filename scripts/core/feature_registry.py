"""Parsing, searching, ID generation, and validation for FEATURE_CHANGELOG.md.

Feature IDs follow ``<PREFIX>-<MODULE>-<NNN>`` where the prefix maps from the
entry type, the module token is uppercase, and the number is sequential per
(type, module) with three-digit padding. Next-ID calculation is deterministic:
it parses the existing registry, never guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TYPE_PREFIXES = {
    "FEATURE": "FEAT",
    "CHANGE": "CHANGE",
    "BUGFIX": "BUG",
    "INTEGRATION": "INT",
    "REMOVED": "REMOVE",
}
PREFIX_TYPES = {v: k for k, v in TYPE_PREFIXES.items()}

VALID_STATUSES = ("Active", "Deprecated", "Replaced", "Removed")

ID_RE = re.compile(r"^(FEAT|CHANGE|BUG|INT|REMOVE)-([A-Z0-9_]+)-(\d{3,})$")
ENTRY_HEADING_RE = re.compile(r"^## \[(FEATURE|CHANGE|BUGFIX|INTEGRATION|REMOVED)\]\s+(.+)$")


class RegistryError(Exception):
    pass


@dataclass
class IndexRow:
    feature_id: str
    type: str
    name: str
    module: str
    status: str
    keywords: str


@dataclass
class Entry:
    feature_id: str
    type: str
    name: str
    fields: dict = field(default_factory=dict)  # "Status", "Module", "Keywords", ...
    body: str = ""


def normalize_module_token(module: str) -> str:
    """Normalize a module name into a stable uppercase ID token.

    ``"Sales Invoice"`` → ``SALES_INVOICE``; punctuation collapses to ``_``.
    """
    token = re.sub(r"[^A-Za-z0-9]+", "_", module.strip()).strip("_").upper()
    if not token:
        raise RegistryError(f"Cannot derive a module token from {module!r}")
    return token


def parse_index(text: str) -> list[IndexRow]:
    """Parse the ``## Feature Index`` markdown table."""
    rows: list[IndexRow] = []
    in_index = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_index = stripped == "## Feature Index"
            continue
        if not in_index or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0] in ("ID", "") or set(cells[0]) <= {"-", " ", ":"}:
            continue
        rows.append(
            IndexRow(
                feature_id=cells[0],
                type=cells[1],
                name=cells[2],
                module=cells[3],
                status=cells[4],
                keywords=cells[5],
            )
        )
    return rows


def parse_entries(text: str) -> list[Entry]:
    """Parse detailed ``## [TYPE] Name`` entries and their metadata bullets."""
    entries: list[Entry] = []
    current: Optional[Entry] = None
    body_lines: list[str] = []
    in_code = False

    def flush():
        nonlocal current, body_lines
        if current is not None:
            current.body = "\n".join(body_lines)
            entries.append(current)
        current = None
        body_lines = []

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code:
            match = ENTRY_HEADING_RE.match(line.strip())
            if match:
                flush()
                current = Entry(feature_id="", type=match.group(1), name=match.group(2).strip())
                continue
            if line.strip().startswith("# ") or (
                line.strip().startswith("## ") and not ENTRY_HEADING_RE.match(line.strip())
            ):
                flush()
                continue
        if current is not None:
            body_lines.append(line)
            meta = re.match(r"^- \*\*([^:*]+):\*\*\s*(.*)$", line.strip())
            if meta:
                key, value = meta.group(1).strip(), meta.group(2).strip()
                if key not in current.fields:
                    current.fields[key] = value
                if key == "ID":
                    current.feature_id = value
    flush()
    return entries


def load_registry(path: Path) -> tuple[list[IndexRow], list[Entry]]:
    text = Path(path).read_text(encoding="utf-8")
    return parse_index(text), parse_entries(text)


def next_feature_id(text: str, entry_type: str, module: str) -> str:
    """Deterministically compute the next ID for (type, module).

    Scans both the index and the detailed entries so a half-updated file still
    produces a safe (never reused) number.
    """
    entry_type = entry_type.upper()
    if entry_type not in TYPE_PREFIXES:
        raise RegistryError(
            f"Unknown feature type {entry_type!r}; expected one of "
            f"{', '.join(TYPE_PREFIXES)}"
        )
    prefix = TYPE_PREFIXES[entry_type]
    token = normalize_module_token(module)

    seen_ids = {row.feature_id for row in parse_index(text)}
    seen_ids.update(e.feature_id for e in parse_entries(text) if e.feature_id)

    highest = 0
    for feature_id in seen_ids:
        match = ID_RE.match(feature_id)
        if match and match.group(1) == prefix and match.group(2) == token:
            highest = max(highest, int(match.group(3)))
    return f"{prefix}-{token}-{highest + 1:03d}"


def search(text: str, query: str) -> list[dict]:
    """Score index rows + entries against *query* terms.

    Advisory only (spec §14): the caller must still inspect actual files.
    Returns matches sorted by descending score with a coarse ``likelihood``.
    """
    terms = [t.lower() for t in re.split(r"\W+", query) if t]
    if not terms:
        return []
    index = parse_index(text)
    entries = {e.feature_id: e for e in parse_entries(text) if e.feature_id}

    results = []
    for row in index:
        entry = entries.get(row.feature_id)
        haystacks = {
            "name": row.name.lower(),
            "keywords": row.keywords.lower(),
            "module": row.module.lower(),
        }
        if entry:
            haystacks["doctypes"] = entry.fields.get("Doctypes", "").lower()
            haystacks["body"] = entry.body.lower()
        matched = 0
        for term in terms:
            weight = 0
            if term in haystacks["name"]:
                weight = max(weight, 3)
            if term in haystacks.get("keywords", ""):
                weight = max(weight, 3)
            if term in haystacks.get("doctypes", ""):
                weight = max(weight, 2)
            if term in haystacks.get("module", ""):
                weight = max(weight, 1)
            if term in haystacks.get("body", ""):
                weight = max(weight, 1)
            matched += weight
        max_score = 3 * len(terms)
        score = int(round(100 * matched / max_score)) if max_score else 0
        score = min(score, 100)
        if score > 0:
            if score >= 90:
                likelihood = "likely already implemented"
            elif score >= 60:
                likelihood = "related existing feature"
            else:
                likelihood = "likely new functionality"
            results.append(
                {
                    "id": row.feature_id,
                    "name": row.name,
                    "module": row.module,
                    "status": row.status,
                    "score": score,
                    "likelihood": likelihood,
                }
            )
    results.sort(key=lambda r: (-r["score"], r["id"]))
    return results


def validate_registry(text: str) -> list[str]:
    """Index/detail consistency checks (spec §14 'Index Validation')."""
    errors: list[str] = []
    index = parse_index(text)
    entries = [e for e in parse_entries(text)]

    index_ids = [row.feature_id for row in index]
    duplicates = {i for i in index_ids if index_ids.count(i) > 1}
    for dup in sorted(duplicates):
        errors.append(f"duplicate ID in index: {dup} [REG_DUP_INDEX_ID]")

    entry_ids = [e.feature_id for e in entries if e.feature_id]
    for dup in sorted({i for i in entry_ids if entry_ids.count(i) > 1}):
        errors.append(f"duplicate ID in entries: {dup} [REG_DUP_ENTRY_ID]")

    entry_map = {e.feature_id: e for e in entries if e.feature_id}
    index_map = {row.feature_id: row for row in index}

    for row in index:
        match = ID_RE.match(row.feature_id)
        if not match:
            errors.append(f"invalid ID format: {row.feature_id} [REG_ID_FORMAT]")
            continue
        expected_prefix = TYPE_PREFIXES.get(row.type.upper())
        if expected_prefix and match.group(1) != expected_prefix:
            errors.append(
                f"{row.feature_id}: prefix does not match type {row.type} [REG_PREFIX_TYPE]"
            )
        if row.status not in VALID_STATUSES:
            errors.append(f"{row.feature_id}: invalid status {row.status!r} [REG_STATUS]")
        if row.feature_id not in entry_map:
            errors.append(
                f"{row.feature_id}: listed in index but has no detailed entry [REG_NO_ENTRY]"
            )
    for entry in entries:
        if not entry.feature_id:
            errors.append(
                f"entry '{entry.name}': missing '- **ID:**' field [REG_ENTRY_NO_ID]"
            )
            continue
        if entry.feature_id not in index_map:
            errors.append(
                f"{entry.feature_id}: detailed entry not present in index [REG_NOT_IN_INDEX]"
            )
            continue
        row = index_map[entry.feature_id]
        if entry.type.upper() != row.type.upper():
            errors.append(
                f"{entry.feature_id}: entry type {entry.type} != index type {row.type} "
                "[REG_TYPE_MISMATCH]"
            )
        if entry.name.strip() != row.name.strip():
            errors.append(
                f"{entry.feature_id}: entry name {entry.name!r} != index name {row.name!r} "
                "[REG_NAME_MISMATCH]"
            )
        entry_status = entry.fields.get("Status", "")
        if entry_status and entry_status != row.status:
            errors.append(
                f"{entry.feature_id}: entry status {entry_status!r} != index status "
                f"{row.status!r} [REG_STATUS_MISMATCH]"
            )
        entry_module = entry.fields.get("Module", "")
        if entry_module and entry_module.strip() != row.module.strip():
            errors.append(
                f"{entry.feature_id}: entry module {entry_module!r} != index module "
                f"{row.module!r} [REG_MODULE_MISMATCH]"
            )
        # Replacement link validation.
        all_ids = set(index_map) | set(entry_map)
        replaced_by = entry.fields.get("Replaced By", "")
        if row.status == "Replaced" and not replaced_by:
            errors.append(
                f"{entry.feature_id}: status Replaced requires 'Replaced By' "
                "[REG_REPLACED_NO_LINK]"
            )
        if replaced_by and replaced_by not in all_ids:
            errors.append(
                f"{entry.feature_id}: 'Replaced By' target {replaced_by} does not exist "
                "[REG_REPLACED_BY_MISSING]"
            )
        replaces = entry.fields.get("Replaces", "")
        if replaces and replaces not in all_ids:
            errors.append(
                f"{entry.feature_id}: 'Replaces' target {replaces} does not exist "
                "[REG_REPLACES_MISSING]"
            )
    return errors
