"""Retrieval-grounded hiring assistant for the HAI experimental prototype."""

from .conditions import CONDITIONS, Condition, get_condition
from .engine import Assessment, HiringRAGAssistant

# rag_agent imports chromadb/langchain — loaded lazily to avoid import-time
# crashes when those packages are not yet installed or incompatible.
def __getattr__(name):
    if name in ("OpenAIChromaHiringAgent", "create_decision_agent"):
        from .rag_agent import OpenAIChromaHiringAgent, create_decision_agent  # noqa: F401
        globals()["OpenAIChromaHiringAgent"] = OpenAIChromaHiringAgent
        globals()["create_decision_agent"] = create_decision_agent
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Assessment",
    "CONDITIONS",
    "Condition",
    "HiringRAGAssistant",
    "OpenAIChromaHiringAgent",
    "create_decision_agent",
    "get_condition",
]
