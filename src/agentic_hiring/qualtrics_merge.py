"""Merge GitHub session flat CSV with Qualtrics pre/post exports by Prolific ID.

Updated to use qualtrics_clean.py for PID validation and deduplication before
the join, so duplicate submissions and malformed IDs never reach the output.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .qualtrics_clean import load_and_clean, _detect_pid_column, _is_metadata_row


def _load_csv_rows(path: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        raw_rows = [dict(r) for r in reader]
    rows = [r for r in raw_rows if not _is_metadata_row(r)]
    return rows, fieldnames


def _session_join_key(row: dict[str, str]) -> str:
    for candidate in ("prolific_pid", "participant_id", "survey_linkage_id"):
        key = (row.get(candidate) or "").strip()
        if key:
            return key
    return ""


def merge_sessions_with_qualtrics(
    session_csv: str | Path,
    pre_csv: str | Path,
    post_csv: str | Path,
    output_csv: str | Path,
    pre_key: Optional[str] = None,
    post_key: Optional[str] = None,
) -> dict[str, int | str]:
    sessions, s_fields = _load_csv_rows(session_csv)

    # Clean + deduplicate each Qualtrics file before indexing
    pre_rows, pre_stats = load_and_clean(pre_csv, pid_col=pre_key, source_label="pre")
    post_rows, post_stats = load_and_clean(post_csv, pid_col=post_key, source_label="post")

    # Use original fieldnames from raw file for column headers (without internal _ columns)
    _, pre_fields_raw = _load_csv_rows(pre_csv)
    _, post_fields_raw = _load_csv_rows(post_csv)

    # Index by PID (already validated and deduped by load_and_clean)
    pre_index = {r["_pid_raw"]: r for r in pre_rows}
    post_index = {r["_pid_raw"]: r for r in post_rows}

    pre_prefixed_fields = [f"pre__{c}" for c in pre_fields_raw]
    post_prefixed_fields = [f"post__{c}" for c in post_fields_raw]

    merged: list[dict[str, str]] = []
    pre_match = 0
    post_match = 0
    both_match = 0

    for s in sessions:
        key = _session_join_key(s)
        pre = pre_index.get(key)
        post = post_index.get(key)

        if pre:
            pre_match += 1
        if post:
            post_match += 1
        if pre and post:
            both_match += 1

        row: dict[str, str] = dict(s)
        row["join_prolific_id"] = key
        row["matched_pre"] = "1" if pre else "0"
        row["matched_post"] = "1" if post else "0"

        for col in pre_fields_raw:
            row[f"pre__{col}"] = (pre or {}).get(col, "")
        for col in post_fields_raw:
            row[f"post__{col}"] = (post or {}).get(col, "")

        merged.append(row)

    out_fields = list(s_fields) + [
        "join_prolific_id",
        "matched_pre",
        "matched_post",
    ] + pre_prefixed_fields + post_prefixed_fields

    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)

    return {
        "sessions": len(sessions),
        "pre_total_pid_rows": pre_stats["total_rows"],
        "post_total_pid_rows": post_stats["total_rows"],
        "pre_validated_pids": pre_stats["valid_pids"],
        "post_validated_pids": post_stats["valid_pids"],
        "pre_rows_after_clean": pre_stats["final_rows"],
        "post_rows_after_clean": post_stats["final_rows"],
        "pre_duplicates_dropped": pre_stats["duplicates_dropped"],
        "post_duplicates_dropped": post_stats["duplicates_dropped"],
        "pre_invalid_pids": pre_stats["invalid_pids"],
        "post_invalid_pids": post_stats["invalid_pids"],
        "pre_empty_pids": pre_stats["empty_pids"],
        "post_empty_pids": post_stats["empty_pids"],
        "matched_pre": pre_match,
        "matched_post": post_match,
        "matched_both": both_match,
        "output": str(out),
        "pre_pid_col": pre_stats["pid_col"],
        "post_pid_col": post_stats["pid_col"],
    }
