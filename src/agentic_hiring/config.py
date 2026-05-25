"""Lightweight config helpers — no heavy dependencies (no chromadb, no langchain)."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_project_openai_config(env_path: Path | str = PROJECT_ENV_PATH) -> None:
    """Load only agent-related settings from a local .env without exposing other secrets."""
    path = Path(env_path)
    if not path.exists():
        return
    permitted = {"OPENAI_API_KEY", "AGENTIC_REQUIRE_LIVE_RAG"}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line or raw_line.lstrip().startswith("#"):
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key in permitted and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")
