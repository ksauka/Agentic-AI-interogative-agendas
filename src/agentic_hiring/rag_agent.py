"""Live LangChain + Chroma + OpenAI implementation of the single hiring agent."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
from typing import Iterable, Literal
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pydantic import BaseModel

from .engine import DEFAULT_CASE_PATH, Assessment, Evidence, HiringRAGAssistant


GENERATION_MODEL = "gpt-4o-mini-2024-07-18"
EMBEDDING_MODEL = "text-embedding-3-small"
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
            os.environ[key] = value.strip().strip("\"").strip("\047")

DEFAULT_VECTOR_STORE_DIR = (
    Path(__file__).resolve().parents[2] / "study" / "vector_store" / "company_knowledge"
)


class GroundedBasis(BaseModel):
    """Structured evidence-grounded screening output from the single agent."""

    recommendation: Literal["Reject", "Advance to human interview", "Hold for further review"]
    candidate_evidence: str
    company_basis: str
    company_citation: str
    uncertain_capability: str
    role_basis: str
    role_citation: str
    policy_basis: str
    policy_citation: str


class OpenAIChromaHiringAgent(HiringRAGAssistant):
    """One agent with persisted internal knowledge and session CV retrieval.

    Company materials persist in Chroma; uploaded CVs remain session-scoped.
    """

    def __init__(
        self,
        case_path: Path | str = DEFAULT_CASE_PATH,
        *,
        candidate_text: str | None = None,
        candidate_name: str = "Uploaded candidate CV",
        persist_directory: Path | str = DEFAULT_VECTOR_STORE_DIR,
        index_candidate: bool = True,
        generation_model: str = GENERATION_MODEL,
        embedding_model: str = EMBEDDING_MODEL,
        client: OpenAI | None = None,
        embeddings: object | None = None,
    ) -> None:
        super().__init__(case_path, candidate_text=candidate_text, candidate_name=candidate_name)
        self.generation_model = generation_model
        self.embedding_model = embedding_model
        self.persist_directory = Path(persist_directory)
        self._client = client or OpenAI()
        self._embeddings = embeddings or OpenAIEmbeddings(model=embedding_model)
        self._internal_store = self._build_internal_store()
        self._candidate_store = self._build_candidate_store() if index_candidate else None

    def _documents_for(self, evidence_items: Iterable[Evidence]) -> list[Document]:
        documents = [
            Document(
                page_content=f"{item.heading}\n{item.text}",
                metadata={
                    "evidence_id": item.evidence_id,
                    "document": item.document,
                    "heading": item.heading,
                    "text": item.text,
                },
            )
            for item in evidence_items
        ]
        return RecursiveCharacterTextSplitter(
            chunk_size=700, chunk_overlap=50
        ).split_documents(documents)

    def _build_internal_store(self) -> Chroma:
        internal = tuple(
            item for item in self.documents
            if item.evidence_id.startswith(("company_", "role_", "policy_"))
        )
        chunks = self._documents_for(internal)
        digest_source = "\n".join(item.page_content for item in chunks).encode("utf-8")
        digest = hashlib.sha256(digest_source).hexdigest()[:12]
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        store = Chroma(
            collection_name=f"internal_hiring_knowledge_{digest}",
            persist_directory=str(self.persist_directory),
            embedding_function=self._embeddings,
        )
        if not store.get(limit=1)["ids"]:
            store.add_documents(chunks, ids=[f"internal_{digest}_{index}" for index in range(len(chunks))])
        return store

    def _build_candidate_store(self) -> Chroma:
        candidate = tuple(item for item in self.documents if item.evidence_id.startswith("cv_"))
        return Chroma.from_documents(
            documents=self._documents_for(candidate),
            embedding=self._embeddings,
            collection_name=f"candidate_cv_{uuid4().hex}",
        )

    @staticmethod
    def _to_evidence(results: list[tuple[Document, float]]) -> tuple[Evidence, ...]:
        evidence: list[Evidence] = []
        seen: set[str] = set()
        for document, score in results:
            evidence_id = str(document.metadata["evidence_id"])
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            evidence.append(
                Evidence(
                    evidence_id=evidence_id,
                    document=str(document.metadata["document"]),
                    heading=str(document.metadata["heading"]),
                    text=str(document.metadata["text"]),
                    score=round(float(score), 3),
                )
            )
        return tuple(evidence)

    def retrieve(self, query: str, top_k: int = 8) -> tuple[Evidence, ...]:
        if self._candidate_store is None:
            raise RuntimeError("A candidate CV must be indexed before assessment.")
        candidate_results = self._candidate_store.similarity_search_with_score(query, k=3)
        internal_results = self._internal_store.similarity_search_with_score(query, k=top_k)
        return self._to_evidence(candidate_results + internal_results)

    def assess(self, user_focus: str = "") -> Assessment:
        rule = self.case["fixed_assessment"]
        retrieved = self.retrieve(rule["retrieval_query"], top_k=64)
        grounded = self._ground_recommendation(retrieved, user_focus=user_focus)
        self._validate_company_citation(grounded.company_citation, retrieved)
        self._validate_role_citation(grounded.role_citation, retrieved)
        self._validate_policy_citation(grounded.policy_citation, retrieved)
        basis = grounded.model_dump()
        basis["company_citation"] = "Company context"
        basis["role_citation"] = self._normalize_section_citation(grounded.role_citation)
        basis["policy_citation"] = self._normalize_section_citation(grounded.policy_citation)
        recommendation = basis.pop("recommendation")
        return Assessment(
            recommendation=recommendation,
            retrieved=retrieved,
            supporting=retrieved,
            caution=(),
            generated_basis=basis,
            retrieval_backend=f"chroma_persisted_internal_plus_uploaded_cv:{self.embedding_model}",
            generation_backend=f"openai_responses:{self.generation_model}",
        )


    @staticmethod
    def _validate_company_citation(citation: str, retrieved: tuple[Evidence, ...]) -> None:
        if not citation.strip():
            raise ValueError("The generated company citation must identify its provenance source.")
        if not any(item.evidence_id.startswith("company_") for item in retrieved):
            raise ValueError("The generated company context basis was not retrieved.")

    @staticmethod
    def _normalize_section_citation(citation: str) -> str:
        sections = re.findall(r"Section\s+\d+(?:\.\d+)?", citation)
        return ", ".join(dict.fromkeys(sections))

    @staticmethod
    def _validate_role_citation(citation: str, retrieved: tuple[Evidence, ...]) -> None:
        section_numbers = re.findall(r"Section\s+(\d+)(?:\.\d+)?", citation)
        if not section_numbers:
            raise ValueError("The generated role citation does not contain a section number.")
        retrieved_ids = {item.evidence_id for item in retrieved}
        missing = [
            number for number in section_numbers
            if f"role_section_{number}" not in retrieved_ids
        ]
        if missing:
            raise ValueError(f"The generated role citation was not retrieved: {citation}")

    @staticmethod
    def _validate_policy_citation(citation: str, retrieved: tuple[Evidence, ...]) -> None:
        section_numbers = re.findall(r"Section\s+(\d+)(?:\.\d+)?", citation)
        if not section_numbers:
            raise ValueError("The generated policy citation does not contain a section number.")
        retrieved_ids = {item.evidence_id for item in retrieved}
        missing = [
            number for number in section_numbers
            if f"policy_section_{number}" not in retrieved_ids
        ]
        if missing:
            raise ValueError(f"The generated policy citation was not retrieved: {citation}")

    def _ground_recommendation(self, retrieved: tuple[Evidence, ...], user_focus: str = "") -> GroundedBasis:
        context = "\n\n".join(
            f"[{item.evidence_id}] {item.document} / {item.heading}: {item.text}"
            for item in retrieved
        )
        focus_clause = (
            f"\n\nThe recruiter has asked you to pay particular attention to the following "
            f"priorities when forming the recommendation: {user_focus.strip()}"
            if user_focus.strip() else ""
        )
        response = self._client.responses.parse(
            model=self.generation_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are one bounded recruitment screening assistant in a "
                        "controlled HAI experiment. Use only retrieved evidence. "
                        "Choose Reject, Advance to human interview, or Hold for further "
                        "review using the retrieved internal knowledge documents: company context, "
                        "role description as requirements, and screening policy as interpretation "
                        "and outcome rules; compare the candidate CV as the submitted evidence against them. "
                        "Where the recruiter has provided stated priorities, ensure those dimensions "
                        "are explicitly addressed in the candidate_evidence and role_basis fields. "
                        "Produce concise evidence-grounded fields. "
                        "For company_citation, write only Company context and ground company_basis "
                        "only in retrieved company-context evidence. "
                        "For role_citation, provide only retrieved section references, for "
                        "example Section 5.4, Section 7.2, or Section 8.5. "
                        "For policy_citation, provide only retrieved section references, for "
                        "example Section 6.4, Section 7.3, or Section 10.1. "
                        "Do not infer protected traits or unstated experience."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Assess the uploaded candidate against these retrieved "
                        f"materials:\n\n{context}{focus_clause}"
                    ),
                },
            ],
            text_format=GroundedBasis,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no structured grounding for the recommendation.")
        return parsed


def initialize_internal_knowledge_base(
    persist_directory: Path | str = DEFAULT_VECTOR_STORE_DIR,
    *,
    client: OpenAI | None = None,
    embeddings: object | None = None,
) -> Path:
    """Embed and persist company/role/policy knowledge before participant use."""
    load_project_openai_config()
    agent = OpenAIChromaHiringAgent(
        persist_directory=persist_directory, index_candidate=False,
        client=client, embeddings=embeddings,
    )
    return agent.persist_directory


def create_decision_agent(
    candidate_text: str | None = None,
    candidate_name: str = "Uploaded candidate CV",
    require_live: bool | None = None,
) -> HiringRAGAssistant:
    """Use live vector RAG when configured; retain a clear offline fallback."""
    load_project_openai_config()
    if require_live is None:
        require_live = os.getenv("AGENTIC_REQUIRE_LIVE_RAG", "").lower() in {"1", "true", "yes"}
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIChromaHiringAgent(candidate_text=candidate_text, candidate_name=candidate_name)
    if require_live:
        raise RuntimeError(
            "AGENTIC_REQUIRE_LIVE_RAG is enabled, but OPENAI_API_KEY is not configured."
        )
    return HiringRAGAssistant(candidate_text=candidate_text, candidate_name=candidate_name)


def is_live_agent(agent: HiringRAGAssistant) -> bool:
    return isinstance(agent, OpenAIChromaHiringAgent)
