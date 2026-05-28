"""Merge GitHub session flat CSV with Qualtrics pre/post exports by Prolific ID."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Optional

_KEY_CANDIDATES = [
    "PROLIFIC_PID",
    "prolific_pid",
    "participant_id",
    "participantid",
    "pid",
    "externalreference",
    "ExternalReference",
]


def _norm_key(value: Any) -> str:
    if value is None:
        return ""
    key = str(value).strip()
    # Skip unresolved Qualtrics placeholders.
    if key.startswith("${") and "PROLIFIC_PID" in key:
        return ""
    return key


def _load_csv_rows(path: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return rows, fieldnames


def _detect_key_column(fieldnames: list[str], preferred: Optional[str] = None) -> str:
    if preferred and preferred in fieldnames:
        return preferred

    lowered = {f.lower(): f for f in fieldnames}
    for c in _KEY_CANDIDATES:
        if c in fieldnames:
            return c
        if c.lower() in lowered:
            return lowered[c.lower()]

    raise ValueError(
        "Could not detect Prolific key column. "
        "Pass explicit --pre-key/--post-key with the right column name."
    )


def _index_by_key(rows: list[dict[str, str]], key_col: str) -> dict[str, dict[str, str]]:
    """Index rows by normalized key, keeping the last non-empty row per key."""
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        key = _norm_key(row.get(key_col, ""))
        if not key:
            continue
        out[key] = row
    return out


def _session_join_key(row: dict[str, str]) -> str:
    for candidate in ("prolific_pid", "participant_id", "survey_linkage_id"):
        key = _norm_key(row.get(candidate, ""))
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
    pre_rows, pre_fields = _load_csv_rows(pre_csv)
    post_rows, post_fields = _load_csv_rows(post_csv)

    pre_key_col = _detect_key_column(pre_fields, pre_key)
    post_key_col = _detect_key_column(post_fields, post_key)

    pre_index = _index_by_key(pre_rows, pre_key_col)
    post_index = _index_by_key(post_rows, post_key_col)

    pre_prefixed_fields = [f"pre__{c}" for c in pre_fields]
    post_prefixed_fields = [f"post__{c}" for c in post_fields]

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

        for col in pre_fields:
            row[f"pre__{col}"] = (pre or {}).get(col, "")
        for col in post_fields:
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
        "pre_rows": len(pre_rows),
        "post_rows": len(post_rows),
        "matched_pre": pre_match,
        "matched_post": post_match,
        "matched_both": both_match,
        "output": str(out),
        "pre_key_col": pre_key_col,
        "post_key_col": post_key_col,
    }
