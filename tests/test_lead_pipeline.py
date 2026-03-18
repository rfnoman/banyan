"""
End-to-end lead pipeline tests.
Uses mocks for Neo4j, ClickHouse, and RabbitMQ — no external services needed.
"""
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase

FAKE_LEAD_EVENT = {
    "event_type": "lead.created",
    "source_app": "test",
    "source_product": "ProductA",
    "person": {
        "name": "Test Person",
        "email": f"test.{uuid.uuid4().hex[:6]}@example.com",
        "title": "VP of Engineering",
        "company": "TestCorp",
        "linkedin_url": "https://linkedin.com/in/testperson",
        "location": "San Francisco",
    },
    "company": {"name": "TestCorp", "industry": "SaaS", "size": "150", "website": "https://testcorp.com"},
    "trigger": "contact_updated",
    "score_hints": {"is_paid": True},
    "raw_context": "Test context for LLM.",
    "timestamp": "2026-01-01T00:00:00Z",
}


class LeadPipelineTest(TestCase):

    @patch("core.tasks.lead_tasks._write_to_clickhouse")
    @patch("core.tasks.lead_tasks._publish_lead_saved")
    @patch("core.graph.queries.link_person_to_business")
    @patch("core.graph.queries.create_lead_relationship")
    @patch("core.graph.queries.update_person_score")
    @patch("core.graph.queries.create_or_merge_business", return_value="biz-123")
    @patch("core.graph.queries.create_or_merge_person", return_value="person-123")
    def test_process_incoming_lead(
        self, mock_person, mock_biz, mock_score, mock_lead_rel,
        mock_link, mock_publish, mock_clickhouse
    ):
        from core.tasks.lead_tasks import process_incoming_lead
        result = process_incoming_lead.apply(args=[FAKE_LEAD_EVENT]).result
        self.assertEqual(result["person_id"], "person-123")
        self.assertGreater(result["score"], 40)
        mock_person.assert_called_once()
        mock_biz.assert_called_once()
        mock_link.assert_called_once_with("person-123", "biz-123")
        mock_clickhouse.assert_called_once()
        mock_publish.assert_called_once()

    @patch("core.tasks.lead_tasks._write_to_clickhouse")
    @patch("core.tasks.lead_tasks._publish_lead_saved")
    @patch("core.graph.queries.link_person_to_business")
    @patch("core.graph.queries.create_lead_relationship")
    @patch("core.graph.queries.update_person_score")
    @patch("core.graph.queries.create_or_merge_business", return_value="biz-456")
    @patch("core.graph.queries.create_or_merge_person", return_value="person-456")
    def test_senior_title_score_boost(self, mock_person, mock_biz, *args):
        from core.tasks.lead_tasks import process_incoming_lead, _compute_initial_score
        from core.messaging.events import LeadCreatedEvent
        event = LeadCreatedEvent(**FAKE_LEAD_EVENT)
        score = _compute_initial_score(event)
        # VP title (+20) + is_paid (+15) + large company (+10) + linkedin_url (+5) + base (40)
        self.assertGreaterEqual(score, 75)

    def test_score_capped_at_100(self):
        from core.tasks.lead_tasks import _compute_initial_score
        from core.messaging.events import LeadCreatedEvent, PersonData, CompanyData
        event = LeadCreatedEvent(
            source_app="linkedin_scraper",
            source_product="ProductA",
            person=PersonData(name="X", email="x@x.com", title="CEO", linkedin_url="https://li.com/in/x"),
            company=CompanyData(name="BigCo", size="10000"),
            trigger="contact_updated",
            score_hints={"is_paid": True},
        )
        score = _compute_initial_score(event)
        self.assertLessEqual(score, 100.0)
