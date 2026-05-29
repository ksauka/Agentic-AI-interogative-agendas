"""Qualtrics CSV cleaner for agentic-hiring study data.

Handles three issues present in the raw Qualtrics exports:
  1. Metadata rows — Qualtrics inserts a human-label row and an ImportId row
     after the CSV header. Both are stripped before any processing.
  2. Invalid Prolific IDs — valid IDs are exactly 24 lowercase hex characters.
     Rows with empty, placeholder (${...}), or malformed IDs are flagged.
  3. Duplicate submissions — same PID submitted multiple times. The latest
     response (by RecordedDate) is kept; earlier ones are discarded.

Designed for a pre/post within-subjects design where the same participant
appears in both the prior and post export with the same column schema.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

_PROLIFIC_RE = re.compile(r"^[a-f0-9]{24}$", re.IGNORECASE)
_PID_CANDIDATES = [
    "PROLIFIC_PID",
    "prolific_pid",
    "pid",
    "participant_id",
    "participantid",
    "ExternalReference",
    "externalreference",
]
_META_SIGNALS = frozenset({"ImportId", "Response ID", "_recordId", "Start Date", "startDate"})


def _is_metadata_row(row: dict[str, str]) -> bool:
    joined = " ".join(str(v) for v in row.values())
    return any(sig in joined for sig in _META_SIGNALS)


def _detect_pid_column(fieldnames: list[str], preferred: Optional[str] = None) -> str:
    if preferred and preferred in fieldnames:
        return preferred
    lowered = {f.lower(): f for f in fieldnames}
    for candidate in _PID_CANDIDATES:
        if candidate in fieldnames:
            return candidate
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    raise ValueError(
        f"Could not detect Prolific PID column in: {fieldnames[:10]}. "
        "Pass pid_col explicitly."
    )


def validate_prolific_pid(pid: str) -> bool:
    """Return True if pid is a well-formed 24-char hex Prolific ID."""
    return bool(pid and _PROLIFIC_RE.match(pid.strip()))


def load_and_clean(
    path: str | Path,
    pid_col: Optional[str] = None,
    source_label: Optional[str] = None,
    keep: str = "latest",
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Load one Qualtrics CSV, strip metadata rows, validate/deduplicate PIDs.

    Args:
        path: Path to the Qualtrics CSV export.
        pid_col: Explicit PID column name. Auto-detected if None.
        source_label: Value written into the '_qualtrics_source' column.
            Defaults to the filename stem.
        keep: Deduplication strategy — 'latest' keeps the row with the
            most recent RecordedDate; 'first' keeps the earliest.

    Returns:
        (rows, stats) where rows is a list of cleaned dicts and stats is
        a dict with counts for total/valid/invalid/empty/deduplicated.
    """
    p = Path(path)
    label = source_label or p.stem

    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        raw_rows = [dict(r) for r in reader]

    detected_pid_col = _detect_pid_column(fieldnames, pid_col)

    data_rows = [r for r in raw_rows if not _is_metadata_row(r)]

    valid: list[dict[str, str]] = []
    invalid: list[dict[str, str]] = []
    empty_count = 0

    for row in data_rows:
        pid = row.get(detected_pid_col, "").strip()
        row["_pid_raw"] = pid
        row["_qualtrics_source"] = label
        row["_pid_col_used"] = detected_pid_col
        if not pid or pid.startswith("${"):
            empty_count += 1
            row["_pid_valid"] = "0"
            invalid.append(row)
        elif not validate_prolific_pid(pid):
            row["_pid_valid"] = "0"
            invalid.append(row)
        else:
            row["_pid_valid"] = "1"
            valid.append(row)

    # Deduplicate: group by PID, keep latest (or first) by RecordedDate
    pid_groups: dict[str, list[dict[str, str]]] = {}
    for row in valid:
        pid = row["_pid_raw"]
        pid_groups.setdefault(pid, []).append(row)

    dedup_count = 0
    deduped: list[dict[str, str]] = []
    for pid, group in pid_groups.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            dedup_count += len(group) - 1
            reverse = keep == "latest"
            try:
                sorted_group = sorted(
                    group,
                    key=lambda r: r.get("RecordedDate", r.get("EndDate", "")),
                    reverse=reverse,
                )
            except Exception:
                sorted_group = group
            deduped.append(sorted_group[0])

    stats = {
        "total_rows": len(data_rows),
        "valid_pids": len(valid),
        "invalid_pids": len(invalid),
        "empty_pids": empty_count,
        "duplicates_dropped": dedup_count,
        "final_rows": len(deduped),
        "pid_col": detected_pid_col,
        "source": label,
    }
    return deduped, stats


def stack_and_clean(
    paths: list[str | Path],
    pid_col: Optional[str] = None,
    keep: str = "latest",
    source_labels: Optional[list[str]] = None,
) -> tuple[list[dict[str, str]], list[dict[str, int]]]:
    """Load, clean, and stack multiple Qualtrics exports.

    When the same PID appears across files (e.g., test/retest batches),
    the final deduplication step retains the latest response across all files.

    Args:
        paths: List of CSV paths to stack.
        pid_col: Explicit PID column name passed to load_and_clean.
        keep: Deduplication strategy passed to load_and_clean.
        source_labels: Optional per-file source labels. Defaults to stems.

    Returns:
        (rows, stats_list) where rows is the stacked + deduped list and
        stats_list has one stats dict per input file.
    """
    all_rows: list[dict[str, str]] = []
    all_stats: list[dict[str, int]] = []

    for i, path in enumerate(paths):
        label = (source_labels[i] if source_labels and i < len(source_labels) else None)
        rows, stats = load_and_clean(path, pid_col=pid_col, source_label=label, keep=keep)
        all_rows.extend(rows)
        all_stats.append(stats)

    # Cross-file deduplication: keep the latest per PID across all files
    pid_groups: dict[str, list[dict[str, str]]] = {}
    for row in all_rows:
        pid_groups.setdefault(row["_pid_raw"], []).append(row)

    final: list[dict[str, str]] = []
    cross_dupes = 0
    for pid, group in pid_groups.items():
        if len(group) == 1:
            final.append(group[0])
        else:
            cross_dupes += len(group) - 1
            try:
                sorted_group = sorted(
                    group,
                    key=lambda r: r.get("RecordedDate", r.get("EndDate", "")),
                    reverse=(keep == "latest"),
                )
            except Exception:
                sorted_group = group
            final.append(sorted_group[0])

    if all_stats:
        all_stats[-1]["cross_file_duplicates_dropped"] = cross_dupes
        all_stats[-1]["final_stacked_rows"] = len(final)

    return final, all_stats


def write_cleaned_csv(rows: list[dict[str, str]], output_path: str | Path) -> int:
    """Write cleaned rows to CSV. Returns number of rows written."""
    if not rows:
        return 0
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
