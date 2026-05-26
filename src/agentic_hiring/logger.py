"""JSONL event logger for local pilot and GitHub-backed session logging."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .conditions import Condition


DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "study" / "data" / "raw" / "interaction_logs"


class EventLogger:
    def __init__(
        self,
        condition: Condition,
        participant_id: str,
        session_id: str | None = None,
        log_dir: Path | str = DEFAULT_LOG_DIR,
    ) -> None:
        self.condition = condition
        self.participant_id = participant_id.strip() or "pilot_anonymous"
        self.session_id = session_id or uuid4().hex
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"{self.session_id}.jsonl"
        self.turn_id = 0
        # Aggregate fields populated by streamlit_app at completion
        self.session_meta: dict = {}

    def log(self, event_type: str, **fields: object) -> dict[str, object]:
        self.turn_id += 1
        record: dict[str, object] = {
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "turn_id": self.turn_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "condition_id": self.condition.condition_id,
            "explainability_on": self.condition.explainability,
            "anthropomorphic_cues_on": self.condition.anthropomorphic_cues,
            "control_cues_on": self.condition.mixed_initiative_control_cues,
            "event_type": event_type,
        }
        record.update(fields)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        return record

    def read_events(self) -> list[dict]:
        """Return all events written to the local JSONL log file."""
        if not self.path.exists():
            return []
        events = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return events

    def push_to_github(
        self,
        repo: Optional[str] = None,
        github_token: Optional[str] = None,
        extra_meta: Optional[dict] = None,
    ) -> bool:
        """Push the full session JSONL log to a private GitHub repository.

        Falls back gracefully if credentials are absent.  Returns True on
        success, False otherwise.
        """
        from .github_saver import save_to_github

        _token = github_token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_DATA_TOKEN")
        _repo = repo or os.getenv("GITHUB_REPO") or os.getenv("GITHUB_DATA_REPO")

        # Try Streamlit secrets when running inside a Streamlit app
        if not _token or not _repo:
            try:
                import streamlit as st
                if not _token:
                    _token = (
                        st.secrets.get("GITHUB_TOKEN")
                        or st.secrets.get("GITHUB_DATA_TOKEN")
                    )
                if not _repo:
                    _repo = (
                        st.secrets.get("GITHUB_REPO")
                        or st.secrets.get("GITHUB_DATA_REPO")
                    )
            except Exception:
                pass

        if not _token or not _repo:
            print("⚠️  GitHub push skipped: no credentials found.")
            return False

        events = self.read_events()
        payload = {
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "condition_id": self.condition.condition_id,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            **(extra_meta or {}),
            **(self.session_meta or {}),
            "events": events,
        }
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = f"sessions/agentic_hiring/{date_str}/{self.session_id}.json"
        content = json.dumps(payload, indent=2, ensure_ascii=True, default=str)
        commit_msg = f"Session: {self.participant_id} | {self.condition.condition_id}"
        success, error = save_to_github(_repo, path, content, commit_msg, _token)
        if not success:
            print(f"❌ GitHub push failed: {error}")
        return success


def restored_logger(condition: Condition, state: dict[str, object]) -> EventLogger:
    """Construct a logger that continues a Streamlit session across reruns."""
    logger = EventLogger(
        condition,
        str(state.get("participant_id", "pilot_anonymous")),
        str(state["session_id"]) if state.get("session_id") else None,
    )
    logger.turn_id = int(state.get("turn_id", 0))
    state["session_id"] = logger.session_id
    return logger
