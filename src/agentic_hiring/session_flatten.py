"""Flatten extracted session logs into analysis-ready CSV rows.

Supports both:
- Directory of session JSON files (downloaded from private repo)
- Consolidated JSONL file (one session object per line)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _join_list(values: Any, sep: str = "|") -> str:
    if not isinstance(values, list):
        return ""
    return sep.join(str(v) for v in values)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get(payload: dict[str, Any], path: list[str], default: Any = None) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def load_sessions(source: str | Path) -> list[dict[str, Any]]:
    """Load session payloads from a directory of JSON files or a JSONL file."""
    src = Path(source)
    sessions: list[dict[str, Any]] = []

    if src.is_file() and src.suffix.lower() == ".jsonl":
        with src.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        sessions.append(item)
                except json.JSONDecodeError:
                    continue
        return sessions

    if src.is_dir():
        for path in sorted(src.rglob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                if isinstance(payload, dict):
                    payload.setdefault("_source_path", str(path.relative_to(src)))
                    sessions.append(payload)
            except Exception:
                continue
        return sessions

    raise FileNotFoundError(f"Session source not found: {source}")


def _derive_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    recommendation_presented = None
    judgement_settled = None
    final_decision = None
    citation_clicked_ids: list[str] = []
    screen_dwell: dict[str, float] = {}

    for e in events:
        et = e.get("event_type")
        if et == "recommendation_presented":
            recommendation_presented = e
        elif et == "judgement_settledness_recorded":
            judgement_settled = e
        elif et == "final_decision_recorded":
            final_decision = e
        elif et == "citation_clicked":
            cid = e.get("citation_id")
            if cid:
                citation_clicked_ids.append(str(cid))
        elif et == "screen_completed":
            sname = e.get("screen_name")
            sdwell = _safe_float(e.get("screen_dwell_seconds"), 0.0)
            if sname:
                screen_dwell[str(sname)] = round(screen_dwell.get(str(sname), 0.0) + sdwell, 2)

    return {
        "recommendation_presented": recommendation_presented or {},
        "judgement_settled": judgement_settled or {},
        "final_decision": final_decision or {},
        "citation_clicked_ids": citation_clicked_ids,
        "screen_dwell_seconds": screen_dwell,
    }


def flatten_participant_rows(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per participant/session for modeling and aggregate plots."""
    rows: list[dict[str, Any]] = []

    for s in sessions:
        events = s.get("events", []) if isinstance(s.get("events"), list) else []
        derived = _derive_from_events(events)

        citations_shown = s.get("citations_shown", []) or _get(s, ["recommendation", "citations_shown"], [])
        citations_clicked = s.get("citations_clicked", [])
        if not citations_clicked:
            citations_clicked = derived["citation_clicked_ids"]

        shown_count = len(citations_shown) if isinstance(citations_shown, list) else 0
        clicked_count = len(citations_clicked) if isinstance(citations_clicked, list) else 0
        unique_clicked = len(set(citations_clicked)) if isinstance(citations_clicked, list) else 0
        citation_ctr = round((unique_clicked / shown_count), 4) if shown_count > 0 else 0.0

        screen_dwell = s.get("screen_dwell_seconds")
        if not isinstance(screen_dwell, dict) or not screen_dwell:
            screen_dwell = derived["screen_dwell_seconds"]

        row = {
            "session_id": s.get("session_id", ""),
            "participant_id": s.get("participant_id", ""),
            "prolific_pid": s.get("prolific_pid", ""),
            "survey_linkage_id": s.get("survey_linkage_id", ""),
            "condition_id": s.get("condition_id", ""),
            "explainability": s.get("explainability", ""),
            "anthropomorphic_cues": s.get("anthropomorphic_cues", ""),
            "hic": s.get("hic", ""),
            "recommendation_base": _get(s, ["recommendation_change", "recommendation_base"], ""),
            "recommendation_final": _get(s, ["recommendation_change", "recommendation_final"], "") or _get(derived["recommendation_presented"], ["recommendation"], ""),
            "recommendation_changed_by_hic": _get(s, ["recommendation_change", "recommendation_changed_by_hic"], ""),
            "hic_triggered_hold": _get(s, ["recommendation_change", "hic_triggered_hold"], ""),
            "hic_uncertain_areas_selected": _join_list(_get(s, ["recommendation_change", "hic_uncertain_areas_selected"], [])),
            "hic_stage2_shown": _get(s, ["hic_stage2", "hic_stage2_shown"], ""),
            "hic_stage2_used": _get(s, ["hic_stage2", "hic_stage2_used"], ""),
            "hic_stage2_skip_latency_seconds": _get(s, ["hic_stage2", "hic_stage2_skip_latency_seconds"], ""),
            "hic2_option": _get(s, ["hic_stage2", "hic2_option"], ""),
            "hic_stage2_done": _get(s, ["hic_stage2", "stage2_done"], ""),
            "judgement_settledness": s.get("judgement_settledness", "") or _get(derived["judgement_settled"], ["judgement_settledness"], ""),
            "final_decision": _get(s, ["decision", "final_decision"], "") or _get(derived["final_decision"], ["final_human_decision"], ""),
            "recommendation_followed": _get(s, ["decision", "recommendation_followed"], "") or _get(derived["final_decision"], ["recommendation_followed"], ""),
            "hold_reasons": _join_list(_get(s, ["decision", "hold_reasons"], [])),
            "recommendation_dwell_seconds": s.get("recommendation_dwell_seconds", ""),
            "time_from_recommendation_to_final_decision_seconds": s.get("time_from_recommendation_to_final_decision_seconds", ""),
            "time_from_judgement_settledness_to_final_decision_seconds": s.get("time_from_judgement_settledness_to_final_decision_seconds", ""),
            "provenance_clicks": s.get("provenance_clicks", 0),
            "citation_evidence_inspected": _as_bool(s.get("citation_evidence_inspected", unique_clicked > 0)),
            "full_document_inspected": _as_bool(s.get("full_document_inspected", False)),
            "role_full_viewed": _as_bool(s.get("role_full_viewed", False)),
            "policy_full_viewed": _as_bool(s.get("policy_full_viewed", False)),
            "citation_click_count": int(s.get("citation_click_count", clicked_count) or 0),
            "unique_citations_clicked": int(s.get("unique_citations_clicked", unique_clicked) or 0),
            "cited_sections_viewed": _join_list(s.get("cited_sections_viewed", [])),
            "citation_view_dwell_seconds_total": _safe_float(s.get("citation_view_dwell_seconds_total", 0.0), 0.0),
            "citations_shown_count": shown_count,
            "citations_clicked_count": clicked_count,
            "citation_ctr_unique_clicked_over_shown": citation_ctr,
            "screen_dwell_role_summary": _safe_float(screen_dwell.get("role_summary", 0.0), 0.0),
            "screen_dwell_policy_summary": _safe_float(screen_dwell.get("policy_summary", 0.0), 0.0),
            "screen_dwell_candidate_cv_and_recommendation": _safe_float(screen_dwell.get("candidate_cv_and_recommendation", 0.0), 0.0),
            "screen_dwell_final_decision": _safe_float(screen_dwell.get("final_decision", 0.0), 0.0),
            "qualtrics_returned": _as_bool(s.get("qualtrics_returned", False)),
            "saved_at_utc": s.get("saved_at_utc", ""),
            "events_count": len(events),
            "source_path": s.get("_source_path", ""),
        }
        rows.append(row)

    return rows


def flatten_event_rows(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per event for sequence/process analysis and visualization."""
    rows: list[dict[str, Any]] = []

    for s in sessions:
        sid = s.get("session_id", "")
        pid = s.get("participant_id", "")
        cond = s.get("condition_id", "")
        events = s.get("events", []) if isinstance(s.get("events"), list) else []

        for e in events:
            row = {
                "session_id": sid,
                "participant_id": pid,
                "condition_id": cond,
                "turn_id": e.get("turn_id", ""),
                "timestamp_utc": e.get("timestamp_utc", ""),
                "event_type": e.get("event_type", ""),
                "screen": e.get("screen", ""),
                "screen_name": e.get("screen_name", ""),
                "citation_id": e.get("citation_id", ""),
                "document": e.get("document", e.get("document_type", "")),
                "section_number": e.get("section_number", ""),
                "dwell_seconds": e.get("dwell_seconds", e.get("screen_dwell_seconds", "")),
                "recommendation": e.get("recommendation", ""),
                "final_human_decision": e.get("final_human_decision", ""),
                "judgement_settledness": e.get("judgement_settledness", ""),
                "recommendation_followed": e.get("recommendation_followed", ""),
                "hic_option": e.get("hic_option", ""),
                "hic_free_text": e.get("hic_free_text", ""),
                "provenance_click_count": e.get("provenance_click_count", ""),
                "raw_event_json": json.dumps(e, ensure_ascii=True),
            }
            rows.append(row)

    return rows


def write_csv(rows: Iterable[dict[str, Any]], output_path: str | Path, fieldnames: list[str]) -> int:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count
