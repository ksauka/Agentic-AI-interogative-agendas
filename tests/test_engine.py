import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentic_hiring.conditions import CONDITIONS, control_prompt
from agentic_hiring.documents import extract_cv_text, validate_cv_text
from agentic_hiring.engine import HiringRAGAssistant
from agentic_hiring.logger import EventLogger
from agentic_hiring.rag_agent import (
    GroundedBasis, OpenAIChromaHiringAgent, create_decision_agent,
    initialize_internal_knowledge_base, load_project_openai_config,
)


class HiringRAGAssistantTests(unittest.TestCase):
    def setUp(self):
        self.assistant = HiringRAGAssistant()
        self.assessment = self.assistant.assess()

    def test_fixed_recommendation_is_grounded_in_retrieved_evidence(self):
        self.assertEqual(self.assessment.recommendation, "Hold for further review")
        retrieved_ids = {item.evidence_id for item in self.assessment.retrieved}
        expected_ids = {
            "company_1", "cv_1", "cv_2", "cv_3", "role_section_5", "role_section_6",
            "policy_section_7", "policy_section_6",
        }
        self.assertTrue(expected_ids.issubset(retrieved_ids))

    def test_canonical_role_exposes_directly_citable_provisions(self):
        role = self.assistant.material("role_description")
        role_text = "\n".join(section["text"] for section in role["sections"])
        self.assertEqual(len(role["sections"]), 11)
        self.assertIn("structured evaluation, tracking, screening, scheduling", role_text)
        self.assertIn("Transferable Competence Rule", role_text)

    def test_canonical_policy_exposes_directly_citable_provisions(self):
        policy_text = "\n".join(
            section["text"] for section in self.assistant.material("screening_policy")["sections"]
        )
        self.assertIn("A candidate shall be assigned the outcome **Hold for Further Review**", policy_text)
        self.assertIn("No candidate shall be rejected solely because", policy_text)
        self.assertIn("The final screening decision shall always remain", policy_text)

    def test_every_condition_uses_same_recommendation(self):
        recommendations = {
            self.assistant.assess().recommendation for _condition in CONDITIONS.values()
        }
        self.assertEqual(recommendations, {"Hold for further review"})

    def test_explainability_changes_visible_provenance_only(self):
        low = self.assistant.response(CONDITIONS["E0_A0_C0"], self.assessment)
        high = self.assistant.response(CONDITIONS["E1_A0_C0"], self.assessment)
        self.assertNotIn("Candidate evidence", low)
        self.assertIn("Company-context basis", high)
        self.assertIn("Role Description", high)
        self.assertIn("Screening Policy", high)
        self.assertIn("Section 5.4", high)
        self.assertIn("Section 7.2", high)

    def test_anthropomorphic_overlay_adds_mild_first_person_cue(self):
        neutral = self.assistant.response(CONDITIONS["E0_A0_C0"], self.assessment)
        social = self.assistant.response(CONDITIONS["E0_A1_C0"], self.assessment)
        self.assertNotIn("I would currently recommend", neutral)
        self.assertIn("I would currently recommend", social)

    def test_mixed_initiative_control_cue_exists_only_in_control_condition(self):
        self.assertEqual(control_prompt(CONDITIONS["E0_A0_C0"]), "")
        self.assertIn("final decision", control_prompt(CONDITIONS["E0_A0_C1"]))


class FakeEmbeddings:
    def __init__(self):
        self.document_batches: list[list[str]] = []

    def embed_documents(self, texts):
        texts = list(texts)
        self.document_batches.append(texts)
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)

    @staticmethod
    def _vector(text):
        lowered = text.lower()
        return [
            float("screen" in lowered or "screening" in lowered),
            float("criteria" in lowered or "evaluation" in lowered),
            float("uncertain" in lowered or "uncertainty" in lowered),
            float("coordination" in lowered or "stakeholder" in lowered),
        ]


class FakeResponse:
    output_parsed = GroundedBasis(
        recommendation="Hold for further review",
        candidate_evidence="The CV describes application review against published eligibility criteria.",
        company_basis="The organisation is scaling and needs consistent hiring decisions.",
        company_citation="Company context",
        uncertain_capability="The CV does not show independent recruitment screening decisions.",
        role_basis="Structured evaluation support is relevant to the required qualification.",
        role_citation="Section 5.4",
        policy_basis="Plausible role fit with material uncertainty warrants further review.",
        policy_citation="Section 6.4",
    )


class FakeClient:
    class Responses:
        @staticmethod
        def parse(**_kwargs):
            return FakeResponse()

    responses = Responses()


class LiveRAGAgentTests(unittest.TestCase):
    def test_persisted_internal_index_and_uploaded_cv_drive_assessment(self):
        embeddings = FakeEmbeddings()
        candidate = "Reviewed applications against criteria and coordinated stakeholder decisions."
        with tempfile.TemporaryDirectory() as directory:
            assistant = OpenAIChromaHiringAgent(
                candidate_text=candidate, candidate_name="candidate.txt",
                persist_directory=directory, client=FakeClient(), embeddings=embeddings,
            )
            assessment = assistant.assess()
            first_session_batches = len(embeddings.document_batches)
            OpenAIChromaHiringAgent(
                candidate_text=candidate, candidate_name="candidate.txt",
                persist_directory=directory, client=FakeClient(), embeddings=embeddings,
            )
        retrieved_ids = {item.evidence_id for item in assessment.retrieved}
        self.assertIn("cv_uploaded", retrieved_ids)
        self.assertIn("company_1", retrieved_ids)
        self.assertIn("role_section_5", retrieved_ids)
        self.assertIn("policy_section_6", retrieved_ids)
        self.assertIn("policy_section_7", retrieved_ids)
        self.assertEqual(assessment.recommendation, "Hold for further review")
        self.assertEqual(
            assessment.retrieval_backend,
            "chroma_persisted_internal_plus_uploaded_cv:text-embedding-3-small",
        )
        self.assertEqual(len(embeddings.document_batches), first_session_batches + 1)
        self.assertIn("application review", assessment.generated_basis["candidate_evidence"])
        self.assertEqual(assessment.generated_basis["company_citation"], "Company context")
        self.assertEqual(assessment.generated_basis["role_citation"], "Section 5.4")
        self.assertEqual(assessment.generated_basis["policy_citation"], "Section 6.4")

    def test_generated_company_citation_requires_retrieved_company_context(self):
        with self.assertRaises(ValueError):
            OpenAIChromaHiringAgent._validate_company_citation(
                "",
                (type("EvidenceStub", (), {"evidence_id": "company_1"})(),),
            )
        with self.assertRaises(ValueError):
            OpenAIChromaHiringAgent._validate_company_citation(
                "Company context",
                (type("EvidenceStub", (), {"evidence_id": "role_section_5"})(),),
            )

    def test_section_citations_are_normalized_for_visible_provenance(self):
        self.assertEqual(
            OpenAIChromaHiringAgent._normalize_section_citation(
                "Section 5.4: qualification; Section 8.5: uncertainty"
            ),
            "Section 5.4, Section 8.5",
        )

    def test_generated_role_citation_must_come_from_retrieved_section(self):
        with self.assertRaises(ValueError):
            OpenAIChromaHiringAgent._validate_role_citation(
                "Section 8.5",
                (type("EvidenceStub", (), {"evidence_id": "role_section_5"})(),),
            )

    def test_generated_policy_citation_must_come_from_retrieved_section(self):
        with self.assertRaises(ValueError):
            OpenAIChromaHiringAgent._validate_policy_citation(
                "Section 14.2",
                (type("EvidenceStub", (), {"evidence_id": "policy_section_6"})(),),
            )
        with self.assertRaises(ValueError):
            OpenAIChromaHiringAgent._validate_policy_citation(
                "Section 6.4 and Section 10.1",
                (type("EvidenceStub", (), {"evidence_id": "policy_section_6"})(),),
            )

    def test_internal_knowledge_base_can_be_preindexed_without_a_candidate(self):
        embeddings = FakeEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            path = initialize_internal_knowledge_base(
                directory, client=FakeClient(), embeddings=embeddings
            )
        self.assertEqual(Path(path), Path(directory))
        self.assertEqual(len(embeddings.document_batches), 1)
        embedded_text = "\n".join(embeddings.document_batches[0])
        self.assertNotIn("Jordan Meyer", embedded_text)
        self.assertNotIn("Programme Operations Coordinator, BrightPath", embedded_text)
        self.assertIn("Northstar Health Analytics", embedded_text)

    def test_local_env_loader_reads_only_agent_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "OPENAI_API_KEY = \"test-key\"\nDROPBOX_APP_SECRET = \"do-not-load\"\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                load_project_openai_config(env_path)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "test-key")
                self.assertNotIn("DROPBOX_APP_SECRET", os.environ)

    def test_factory_falls_back_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(create_decision_agent(require_live=False), HiringRAGAssistant)


class DocumentIngestionTests(unittest.TestCase):
    def test_text_cv_is_normalized(self):
        self.assertEqual(validate_cv_text("Candidate\n  Experience  "), "Candidate\n  Experience")
        self.assertEqual(extract_cv_text("cv.txt", b"Recruitment screening"), "Recruitment screening")

    def test_pdf_cv_text_is_extracted(self):
        page = type("Page", (), {"extract_text": lambda self: "PDF candidate screening work"})()
        reader = type("Reader", (), {"pages": [page]})()
        with patch("agentic_hiring.documents.PdfReader", return_value=reader):
            self.assertEqual(extract_cv_text("cv.pdf", b"pdf"), "PDF candidate screening work")


class EventLoggerTests(unittest.TestCase):
    def test_log_file_is_created_for_local_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = EventLogger(
                CONDITIONS["E1_A1_C1"], "pilot_1", session_id="test_session", log_dir=directory
            )
            record = logger.log("recommendation_presented", recommendation="Hold for further review")
            self.assertEqual(record["condition_id"], "E1_A1_C1")
            self.assertTrue((Path(directory) / "test_session.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
