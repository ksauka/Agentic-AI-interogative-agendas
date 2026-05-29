"""Build the canonical merged analysis dataset for the HAI hiring experiment.

This script regenerates:
- outputs/analysis/participant_sessions_flat.csv
- outputs/analysis/events_flat.csv
- outputs/analysis/merged_all3_session_prior_post_full.csv
- outputs/analysis/merged_all3_session_prior_post_final_no_empty.csv
- outputs/analysis/merge_validation_report.csv
- outputs/analysis/duplicate_identifier_report.csv
- outputs/analysis/merge_validation_summary.json

It archives older derived analysis outputs so the analysis folder keeps one clear
canonical merged file. Raw data under study/data/raw is never modified.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_hiring.qualtrics_merge import merge_sessions_with_qualtrics
from agentic_hiring.session_flatten import (
    flatten_event_rows,
    flatten_participant_rows,
    load_sessions,
    write_csv,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "study" / "data" / "raw"
SESSION_SOURCE = RAW_DIR / "agentic_hiring"
PRIOR_CSV = RAW_DIR / "Agentic AI prior.csv"
POST_CSV = RAW_DIR / "Agentic AI post.csv"
ANALYSIS_DIR = PROJECT_ROOT / "outputs" / "analysis"

PARTICIPANT_OUT = ANALYSIS_DIR / "participant_sessions_flat.csv"
EVENTS_OUT = ANALYSIS_DIR / "events_flat.csv"
MERGED_OUT = ANALYSIS_DIR / "merged_all3_session_prior_post_full.csv"
FINAL_NO_EMPTY_OUT = ANALYSIS_DIR / "merged_all3_session_prior_post_final_no_empty.csv"
VALIDATION_REPORT_OUT = ANALYSIS_DIR / "merge_validation_report.csv"
DUPLICATE_REPORT_OUT = ANALYSIS_DIR / "duplicate_identifier_report.csv"
VALIDATION_SUMMARY_OUT = ANALYSIS_DIR / "merge_validation_summary.json"
README_OUT = ANALYSIS_DIR / "README.md"


def archive_existing_outputs() -> Path | None:
    """Move old derived outputs out of the top-level analysis folder."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in ANALYSIS_DIR.iterdir() if p.is_file()]
    if not files:
        return None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_dir = ANALYSIS_DIR / "archive" / f"pre_canonical_rebuild_{stamp}"
    archive_dir.mkdir(parents=True, exist_ok=False)

    for path in files:
        shutil.move(str(path), archive_dir / path.name)

    return archive_dir


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _session_pid(row: dict[str, Any]) -> str:
    for key in ("prolific_pid", "participant_id", "survey_linkage_id"):
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _session_quality(row: dict[str, Any]) -> tuple[int, float, float, int, str]:
    """Higher is better for choosing among same-condition repeat sessions."""
    has_final = 1 if str(row.get("final_decision", "") or "").strip() else 0
    rec_dwell = _safe_float(row.get("recommendation_dwell_seconds"))
    final_dwell = _safe_float(row.get("screen_dwell_final_decision"))
    event_count = int(_safe_float(row.get("events_count")))
    saved_at = str(row.get("saved_at_utc", "") or "")
    return (has_final, rec_dwell + final_dwell, float(event_count), len(saved_at), saved_at)


def _deduplicate_session_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Remove contaminated and repeated app sessions before Qualtrics merge.

    Rules:
    - Same PID in multiple conditions: exclude all sessions for that PID.
    - Same PID repeated in one condition: keep the most complete/engaged session.
    - Missing/nonstandard PID: keep row; validation report flags it later.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for row in rows:
        pid = _session_pid(row)
        if not pid:
            passthrough.append(row)
        else:
            groups.setdefault(pid, []).append(row)

    kept: list[dict[str, Any]] = list(passthrough)
    cross_contaminated_pids: list[str] = []
    same_condition_deduped: dict[str, int] = {}

    for pid, group in groups.items():
        conditions = {str(row.get("condition_id", "") or "").strip() for row in group}
        conditions.discard("")
        if len(group) > 1 and len(conditions) > 1:
            cross_contaminated_pids.append(pid)
            continue
        if len(group) == 1:
            kept.append(group[0])
            continue
        best = sorted(group, key=_session_quality, reverse=True)[0]
        kept.append(best)
        same_condition_deduped[pid] = len(group) - 1

    return kept, {
        "sessions_before_dedup": len(rows),
        "sessions_after_dedup": len(kept),
        "cross_contaminated_pids_excluded": sorted(cross_contaminated_pids),
        "same_condition_duplicates_dropped": sum(same_condition_deduped.values()),
        "same_condition_dedup_detail": dict(sorted(same_condition_deduped.items())),
    }


def _condition_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(row.get("condition_id", "") for row in rows).items()))


def _duplicate_ids(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(row.get("join_prolific_id", "").strip() for row in rows)
    return dict(sorted((key, count) for key, count in counts.items() if key and count > 1))


def write_no_empty_columns_file(rows: list[dict[str, str]], fields: list[str]) -> dict[str, Any]:
    """Write the analysis-facing file after dropping fully empty columns."""
    keep_fields = [
        field
        for field in fields
        if any(str(row.get(field, "") or "").strip() for row in rows)
    ]
    dropped_fields = [field for field in fields if field not in keep_fields]

    with FINAL_NO_EMPTY_OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keep_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "final_no_empty_output": str(FINAL_NO_EMPTY_OUT),
        "final_no_empty_rows": len(rows),
        "final_no_empty_columns": len(keep_fields),
        "final_no_empty_dropped_column_count": len(dropped_fields),
        "final_no_empty_dropped_columns": dropped_fields,
    }


def _id_issue(join_id: str) -> str:
    if not join_id:
        return "missing_join_id"
    if join_id.startswith("${"):
        return "unresolved_qualtrics_placeholder"
    if re.search(r"\s", join_id):
        return "contains_whitespace"
    if len(join_id) < 16:
        return "short_or_nonstandard_id"
    return ""


def write_validation_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    report_fields = [
        "session_id",
        "join_prolific_id",
        "condition_id",
        "matched_pre",
        "matched_post",
        "final_decision",
        "recommendation_final",
        "validation_issue",
    ]

    report_rows: list[dict[str, str]] = []
    for row in rows:
        issues: list[str] = []
        id_issue = _id_issue(row.get("join_prolific_id", "").strip())
        if id_issue:
            issues.append(id_issue)
        if row.get("matched_pre") != "1":
            issues.append("no_prior_match")
        if row.get("matched_post") != "1":
            issues.append("no_post_match")
        if not row.get("final_decision", "").strip():
            issues.append("missing_final_decision")

        report_rows.append(
            {
                "session_id": row.get("session_id", ""),
                "join_prolific_id": row.get("join_prolific_id", ""),
                "condition_id": row.get("condition_id", ""),
                "matched_pre": row.get("matched_pre", ""),
                "matched_post": row.get("matched_post", ""),
                "final_decision": row.get("final_decision", ""),
                "recommendation_final": row.get("recommendation_final", ""),
                "validation_issue": "|".join(issues),
            }
        )

    write_csv(report_rows, VALIDATION_REPORT_OUT, report_fields)

    issue_counts = Counter()
    for report_row in report_rows:
        for issue in report_row["validation_issue"].split("|"):
            if issue:
                issue_counts[issue] += 1

    return {
        "validation_report_rows": len(report_rows),
        "issue_counts": dict(sorted(issue_counts.items())),
    }


def write_duplicate_identifier_report(rows: list[dict[str, str]], fields: list[str]) -> dict[str, Any]:
    """Write duplicate identifier groups for audit and exclusion decisions."""
    id_fields = [
        field
        for field in fields
        if any(
            token in field.lower()
            for token in (
                "ipid",
                "ipaddress",
                "prolific",
                "participant_id",
                "responseid",
                "session_id",
            )
        )
    ]

    report_rows: list[dict[str, str]] = []
    for field in id_fields:
        buckets: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            value = str(row.get(field, "") or "").strip()
            if value:
                buckets.setdefault(value, []).append(row)

        for value, group in sorted(buckets.items()):
            if len(group) <= 1:
                continue
            report_rows.append(
                {
                    "id_column": field,
                    "id_value": value,
                    "duplicate_count": str(len(group)),
                    "session_ids": "|".join(g.get("session_id", "") for g in group),
                    "join_prolific_ids": "|".join(g.get("join_prolific_id", "") for g in group),
                    "condition_ids": "|".join(g.get("condition_id", "") for g in group),
                    "final_decisions": "|".join(g.get("final_decision", "") for g in group),
                }
            )

    report_fields = [
        "id_column",
        "id_value",
        "duplicate_count",
        "session_ids",
        "join_prolific_ids",
        "condition_ids",
        "final_decisions",
    ]
    write_csv(report_rows, DUPLICATE_REPORT_OUT, report_fields)

    duplicate_pid_groups = [
        row
        for row in report_rows
        if row["id_column"] in {"participant_id", "prolific_pid", "join_prolific_id"}
    ]
    return {
        "duplicate_identifier_report_rows": len(report_rows),
        "duplicate_pid_report_rows": len(duplicate_pid_groups),
    }


def write_readme(archive_dir: Path | None, summary: dict[str, Any]) -> None:
    archive_text = str(archive_dir.relative_to(PROJECT_ROOT)) if archive_dir else "No prior outputs archived."
    README_OUT.write_text(
        "\n".join(
            [
                "# Analysis Outputs",
                "",
                "Canonical files for the Agentic AI interrogative agendas hiring experiment.",
                "",
                "- `merged_all3_session_prior_post_final_no_empty.csv`: final analysis-facing session-level dataset. It drops columns that are empty across all rows.",
                "- `merged_all3_session_prior_post_full.csv`: canonical session-level dataset. It keeps all flattened app/session fields and all Qualtrics columns using `pre__` and `post__` prefixes.",
                "- `participant_sessions_flat.csv`: flattened app/session data before Qualtrics merge.",
                "- `events_flat.csv`: long-form interaction event log for process and dwell-time analysis.",
                "- `merge_validation_report.csv`: row-level join and missingness checks.",
                "- `duplicate_identifier_report.csv`: duplicate PID, response ID, session ID, and IP audit report.",
                "- `merge_validation_summary.json`: machine-readable build summary.",
                "",
                f"Previous derived outputs were archived at `{archive_text}`.",
                "",
                "Raw data in `study/data/raw/` is not modified by the build script.",
                "",
                "Last build summary:",
                "",
                "```json",
                json.dumps(summary, indent=2, sort_keys=True),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    archive_dir = archive_existing_outputs()

    sessions = load_sessions(SESSION_SOURCE)
    participant_rows = flatten_participant_rows(sessions)
    participant_rows, dedup_stats = _deduplicate_session_rows(participant_rows)
    event_rows = flatten_event_rows(sessions)

    participant_fields = list(participant_rows[0].keys()) if participant_rows else []
    event_fields = list(event_rows[0].keys()) if event_rows else []

    participant_count = write_csv(participant_rows, PARTICIPANT_OUT, participant_fields)
    event_count = write_csv(event_rows, EVENTS_OUT, event_fields)

    merge_summary = merge_sessions_with_qualtrics(
        session_csv=PARTICIPANT_OUT,
        pre_csv=PRIOR_CSV,
        post_csv=POST_CSV,
        output_csv=MERGED_OUT,
    )

    merged_rows, merged_fields = _read_csv_rows(MERGED_OUT)
    clean_summary = write_no_empty_columns_file(merged_rows, merged_fields)
    validation_summary = write_validation_report(merged_rows)
    duplicate_summary = write_duplicate_identifier_report(merged_rows, merged_fields)

    summary: dict[str, Any] = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_session_json_count": len(sessions),
        "participant_session_rows": participant_count,
        "event_rows": event_count,
        "merged_rows": len(merged_rows),
        "merged_columns": len(merged_fields),
        "condition_counts": _condition_counts(merged_rows),
        "duplicate_join_prolific_ids": _duplicate_ids(merged_rows),
        "archived_previous_outputs": str(archive_dir.relative_to(PROJECT_ROOT)) if archive_dir else "",
        **merge_summary,
        **clean_summary,
        **validation_summary,
        **duplicate_summary,
        **dedup_stats,
    }

    VALIDATION_SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_readme(archive_dir, summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
