"""Merge participant session CSV with Qualtrics pre/post exports by Prolific ID.

Example:

  PYTHONPATH=src conda run -n esd_platform python scripts/merge_qualtrics_with_sessions.py \
    --sessions outputs/analysis/participant_sessions_flat.csv \
    --pre data/qualtrics/pre_interaction.csv \
    --post data/qualtrics/post_interaction.csv \
    --out outputs/analysis/merged_sessions_qualtrics.csv
"""

from __future__ import annotations

import argparse
import json

from agentic_hiring.qualtrics_merge import merge_sessions_with_qualtrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge session flat CSV with Qualtrics pre/post by Prolific ID."
    )
    parser.add_argument(
        "--sessions",
        default="outputs/analysis/participant_sessions_flat.csv",
        help="Participant-level session CSV",
    )
    parser.add_argument("--pre", required=True, help="Qualtrics pre-interaction CSV")
    parser.add_argument("--post", required=True, help="Qualtrics post-interaction CSV")
    parser.add_argument(
        "--out",
        default="outputs/analysis/merged_sessions_qualtrics.csv",
        help="Merged output CSV",
    )
    parser.add_argument(
        "--pre-key",
        default=None,
        help="Optional explicit key column for pre CSV",
    )
    parser.add_argument(
        "--post-key",
        default=None,
        help="Optional explicit key column for post CSV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    summary = merge_sessions_with_qualtrics(
        session_csv=args.sessions,
        pre_csv=args.pre,
        post_csv=args.post,
        output_csv=args.out,
        pre_key=args.pre_key,
        post_key=args.post_key,
    )

    print("✅ Merge complete")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
