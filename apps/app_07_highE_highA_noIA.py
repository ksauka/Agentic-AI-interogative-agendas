"""Condition 7: High explainability, high anthropomorphic cues, no mixed-initiative control cues."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentic_hiring.streamlit_app import run

run("E1_A1_C0")
