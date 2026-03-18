"""
Unit tests for Neo4j Cypher query functions.
Mocks the driver — no live Neo4j needed.
"""
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase


def _make_session_mock():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


class GraphQueriesTest(TestCase):

    @patch("core.graph.queries.get_driver")
    def test_create_or_merge_person(self, mock_driver):
        session = _make_session_mock()
        mock_driver.return_value.session.return_value = session

        from core.graph.queries import create_or_merge_person
        person_id = create_or_merge_person({"name": "Test", "email": "test@example.com"})
        self.assertTrue(len(person_id) > 0)
        session.run.assert_called_once()

    @patch("core.graph.queries.get_driver")
    def test_create_or_merge_person_preserves_provided_id(self, mock_driver):
        session = _make_session_mock()
        mock_driver.return_value.session.return_value = session
        from core.graph.queries import create_or_merge_person
        custom_id = str(uuid.uuid4())
        person_id = create_or_merge_person({"id": custom_id, "name": "Test", "email": "test@example.com"})
        self.assertEqual(person_id, custom_id)

    @patch("core.graph.queries.get_driver")
    def test_create_or_merge_business(self, mock_driver):
        session = _make_session_mock()
        mock_driver.return_value.session.return_value = session
        from core.graph.queries import create_or_merge_business
        biz_id = create_or_merge_business({"name": "TestCorp"})
        self.assertTrue(len(biz_id) > 0)
        session.run.assert_called_once()

    @patch("core.graph.queries.get_driver")
    def test_log_action(self, mock_driver):
        session = _make_session_mock()
        mock_driver.return_value.session.return_value = session
        from core.graph.queries import log_action
        action_id = log_action("person-123", "email_sent", "Test note", "email")
        self.assertTrue(len(action_id) > 0)
        session.run.assert_called_once()

    @patch("core.graph.queries.get_driver")
    def test_get_person_with_connections_not_found(self, mock_driver):
        session = _make_session_mock()
        session.run.return_value.single.return_value = None
        mock_driver.return_value.session.return_value = session
        from core.graph.queries import get_person_with_connections
        result = get_person_with_connections("nonexistent")
        self.assertEqual(result, {})

    @patch("core.graph.queries.get_driver")
    def test_update_ai_tags(self, mock_driver):
        session = _make_session_mock()
        mock_driver.return_value.session.return_value = session
        from core.graph.queries import update_ai_tags
        update_ai_tags("person-123", {
            "tags": ["decision-maker"],
            "persona": "Technical Executive",
            "product_fit": "ProductA",
            "urgency": "high",
            "reasoning": "Test reasoning",
            "suggested_stage": "Qualified",
            "confidence": 0.9,
        })
        session.run.assert_called_once()
