"""Build analysis-ready flat CSVs from extracted session logs.

Input can be either:
- Directory of downloaded session JSON files
- JSONL file where each line is one session object

Outputs:
- participant_sessions_flat.csv (one row per session)
- events_flat.csv (one row per event)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from agentic_hiring.session_flatten import (
    flatten_event_rows,
    flatten_participant_rows,
    load_sessions,
    write_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flatten session JSON data into participant/event CSV files."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input directory of JSON files or JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/analysis",
        help="Directory for generated CSV files",
    )
    parser.add_argument(
        "--participant-csv",
        default="participant_sessions_flat.csv",
        help="Participant-level output CSV filename",
    )
    parser.add_argument(
        "--events-csv",
        default="events_flat.csv",
        help="Event-level output CSV filename",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    sessions = load_sessions(args.input)
    if not sessions:
        print("⚠️ No session payloads found in input.")
        return 1

    participant_rows = flatten_participant_rows(sessions)
    event_rows = flatten_event_rows(sessions)

    out_dir = Path(args.output_dir)
    participant_path = out_dir / args.participant_csv
    events_path = out_dir / args.events_csv

    participant_fields = list(participant_rows[0].keys()) if participant_rows else []
    event_fields = list(event_rows[0].keys()) if event_rows else []

    p_count = write_csv(participant_rows, participant_path, participant_fields)
    e_count = write_csv(event_rows, events_path, event_fields)

    print("✅ Flat CSV generation complete")
    print(f"- sessions loaded: {len(sessions)}")
    print(f"- participant rows: {p_count} -> {participant_path}")
    print(f"- event rows: {e_count} -> {events_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
