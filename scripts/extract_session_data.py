"""Extract all session data from the private GitHub logging repository.

Usage examples:

  PYTHONPATH=src python scripts/extract_session_data.py \
      --repo ksauka/hicxai-data-private \
      --out-dir outputs/extracted_sessions

  PYTHONPATH=src python scripts/extract_session_data.py \
      --out-dir outputs/extracted_sessions \
      --combine-jsonl outputs/extracted_sessions/all_sessions.jsonl

If --repo/--token are omitted, environment variables are used:
  GITHUB_REPO / GITHUB_TOKEN (preferred)
  GITHUB_DATA_REPO / GITHUB_DATA_TOKEN (legacy)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentic_hiring.github_loader import (
    GitHubLoaderError,
    consolidate_sessions_to_jsonl,
    download_sessions,
    resolve_github_credentials,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all session JSON logs from private GitHub repo."
    )
    parser.add_argument("--repo", default=None, help="GitHub repo slug (owner/repo)")
    parser.add_argument("--token", default=None, help="GitHub PAT with repo access")
    parser.add_argument(
        "--prefix",
        default="sessions/agentic_hiring/",
        help="Repo path prefix to extract from",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref/branch/tag to read from",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/extracted_sessions",
        help="Local output directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite already-downloaded local files",
    )
    parser.add_argument(
        "--combine-jsonl",
        default=None,
        help="Optional output JSONL path to consolidate downloaded sessions",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        repo, token = resolve_github_credentials(repo=args.repo, token=args.token)
    except GitHubLoaderError as e:
        print(f"❌ {e}")
        return 1

    try:
        summary = download_sessions(
            repo=repo,
            token=token,
            out_dir=Path(args.out_dir),
            prefix=args.prefix,
            ref=args.ref,
            overwrite=args.overwrite,
        )
    except GitHubLoaderError as e:
        print(f"❌ Extraction failed: {e}")
        return 1

    print("✅ Session extraction completed")
    print(json.dumps(summary, indent=2))

    if args.combine_jsonl:
        count = consolidate_sessions_to_jsonl(
            source_dir=Path(args.out_dir),
            output_jsonl=Path(args.combine_jsonl),
        )
        print(f"✅ Consolidated {count} session files to {args.combine_jsonl}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
