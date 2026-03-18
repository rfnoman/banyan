"""
LLM tagging tests — mocks Anthropic API, validates AITagResult schema.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase


MOCK_LLM_RESPONSE = {
    "tags": ["decision-maker", "high-intent", "technical-buyer"],
    "persona": "Technical Executive",
    "product_fit": "ProductA",
    "urgency": "high",
    "reasoning": "This lead is a VP of Engineering at a 150-person SaaS company with a paid plan, indicating budget authority and active engagement.",
    "suggested_stage": "Qualified",
    "confidence": 0.87,
}


def _make_anthropic_response(content: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=content)]
    mock_msg.usage = MagicMock(input_tokens=300, output_tokens=150)
    return mock_msg


class AITagResultSchemaTest(TestCase):

    def test_valid_tag_result(self):
        from core.llm.schema import AITagResult
        result = AITagResult(**MOCK_LLM_RESPONSE)
        self.assertEqual(result.persona, "Technical Executive")
        self.assertEqual(result.urgency, "high")
        self.assertIn("decision-maker", result.tags)
        self.assertAlmostEqual(result.confidence, 0.87)

    def test_invalid_tag_rejected(self):
        from core.llm.schema import AITagResult
        from pydantic import ValidationError
        bad = {**MOCK_LLM_RESPONSE, "tags": ["decision-maker", "INVALID_TAG"]}
        with self.assertRaises(ValidationError):
            AITagResult(**bad)

    def test_invalid_urgency_rejected(self):
        from core.llm.schema import AITagResult
        from pydantic import ValidationError
        bad = {**MOCK_LLM_RESPONSE, "urgency": "extreme"}
        with self.assertRaises(ValidationError):
            AITagResult(**bad)

    def test_all_valid_tags_accepted(self):
        from core.llm.schema import AITagResult, VALID_TAGS
        result = AITagResult(**{**MOCK_LLM_RESPONSE, "tags": list(VALID_TAGS)})
        self.assertEqual(set(result.tags), VALID_TAGS)


class LeadTaggerTest(TestCase):

    @patch("core.graph.queries.update_ai_tags")
    @patch("core.graph.queries.get_person_with_connections")
    @patch("anthropic.Anthropic")
    def test_tag_person(self, MockAnthropic, mock_get_person, mock_update_tags):
        mock_get_person.return_value = {
            "id": "p1", "name": "Test", "email": "test@example.com",
            "title": "VP Engineering", "score": 75,
            "company": {"name": "TestCorp", "industry": "SaaS", "size": "150"},
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_anthropic_response(json.dumps(MOCK_LLM_RESPONSE))
        MockAnthropic.return_value = mock_client

        from core.llm.tagger import LeadTagger
        tagger = LeadTagger()
        result = tagger.tag_person("p1", raw_context="Test context", trigger="test", source_app="test")

        self.assertEqual(result.persona, "Technical Executive")
        self.assertEqual(result.urgency, "high")
        self.assertIn("decision-maker", result.tags)
        mock_update_tags.assert_called_once()
        mock_client.messages.create.assert_called_once()

    def test_prompt_builder_system(self):
        from core.llm.prompt_builder import build_system_prompt
        prompt = build_system_prompt(["ProductA", "ProductB"])
        self.assertIn("ProductA", prompt)
        self.assertIn("ProductB", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn("decision-maker", prompt)

    def test_prompt_builder_user(self):
        from core.llm.prompt_builder import build_user_prompt
        person = {"name": "Alice", "title": "CTO", "email": "alice@corp.com", "score": 80}
        company = {"name": "Corp", "industry": "SaaS", "size": "200"}
        prompt = build_user_prompt(person, company, "Test context", "contact_updated", "bookkeeper")
        self.assertIn("Alice", prompt)
        self.assertIn("CTO", prompt)
        self.assertIn("bookkeeper", prompt)
        self.assertIn("Test context", prompt)
