"""Utilities for extracting session data from a private GitHub repository.

Pattern follows DS_Project github_saver style (requests + GitHub REST API),
but adds bulk retrieval for analysis pipelines.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Optional

import requests


class GitHubLoaderError(RuntimeError):
    """Raised when GitHub session extraction fails."""


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def resolve_github_credentials(
    repo: Optional[str] = None,
    token: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve GitHub repo/token from args or environment.

    Priority:
      - explicit args
      - GITHUB_REPO / GITHUB_TOKEN
      - GITHUB_DATA_REPO / GITHUB_DATA_TOKEN (legacy compatibility)
    """
    resolved_repo = repo or os.getenv("GITHUB_REPO") or os.getenv("GITHUB_DATA_REPO")
    resolved_token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_DATA_TOKEN")

    if not resolved_repo:
        raise GitHubLoaderError("Missing GitHub repo. Set GITHUB_REPO or pass --repo.")
    if not resolved_token:
        raise GitHubLoaderError("Missing GitHub token. Set GITHUB_TOKEN or pass --token.")

    return resolved_repo, resolved_token


def list_session_paths(
    repo: str,
    token: str,
    prefix: str = "sessions/agentic_hiring/",
    ref: str = "main",
) -> list[str]:
    """List all JSON session blob paths under a prefix.

    Uses Git Trees API recursive listing for efficient traversal.
    """
    # Ensure trailing slash for strict prefix matching.
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"

    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}"
    resp = requests.get(
        url,
        headers=_headers(token),
        params={"recursive": "1"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise GitHubLoaderError(
            f"Could not list repo tree ({resp.status_code}): {resp.text.strip()}"
        )

    payload = resp.json()
    tree = payload.get("tree", [])
    paths = [
        item["path"]
        for item in tree
        if item.get("type") == "blob"
        and item.get("path", "").startswith(normalized_prefix)
        and item.get("path", "").endswith(".json")
    ]
    return sorted(paths)


def fetch_json_file(
    repo: str,
    token: str,
    path: str,
    ref: str = "main",
) -> dict[str, Any]:
    """Fetch and decode a JSON file from a private GitHub repository."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    resp = requests.get(
        url,
        headers=_headers(token),
        params={"ref": ref},
        timeout=30,
    )
    if resp.status_code != 200:
        raise GitHubLoaderError(
            f"Could not fetch {path} ({resp.status_code}): {resp.text.strip()}"
        )

    payload = resp.json()
    encoded = payload.get("content", "")
    if not encoded:
        raise GitHubLoaderError(f"No content returned for {path}")

    raw = base64.b64decode(encoded).decode("utf-8")
    return json.loads(raw)


def download_sessions(
    repo: str,
    token: str,
    out_dir: str | Path,
    prefix: str = "sessions/agentic_hiring/",
    ref: str = "main",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download all session JSON files from private repo to local directory.

    Returns a summary dict with counts and downloaded paths.
    """
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    paths = list_session_paths(repo=repo, token=token, prefix=prefix, ref=ref)
    downloaded: list[str] = []
    skipped: list[str] = []

    for remote_path in paths:
        local_path = out_root / remote_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.exists() and not overwrite:
            skipped.append(remote_path)
            continue

        data = fetch_json_file(repo=repo, token=token, path=remote_path, ref=ref)
        with local_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=True, default=str)
        downloaded.append(remote_path)

    return {
        "repo": repo,
        "ref": ref,
        "prefix": prefix,
        "found": len(paths),
        "downloaded": len(downloaded),
        "skipped": len(skipped),
        "downloaded_paths": downloaded,
        "skipped_paths": skipped,
        "out_dir": str(out_root),
    }


def consolidate_sessions_to_jsonl(
    source_dir: str | Path,
    output_jsonl: str | Path,
) -> int:
    """Consolidate downloaded session JSON files into one JSONL file.

    Each line contains one full session object with an added `_source_path`.
    Returns number of records written.
    """
    src_root = Path(source_dir)
    out_path = Path(output_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records_written = 0
    with out_path.open("w", encoding="utf-8") as out_fh:
        for path in sorted(src_root.rglob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as in_fh:
                    payload = json.load(in_fh)
                payload["_source_path"] = str(path.relative_to(src_root))
                out_fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
                records_written += 1
            except Exception:
                # Skip malformed files but continue extraction.
                continue

    return records_written
