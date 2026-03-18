"""
Tests for lead scoring logic.
"""
from django.test import TestCase
from core.messaging.events import LeadCreatedEvent, PersonData, CompanyData


def make_event(**kwargs):
    defaults = dict(
        source_app="test",
        source_product="ProductA",
        person=PersonData(name="Test User", email="test@example.com"),
        company=CompanyData(name="TestCorp"),
        trigger="contact_updated",
        score_hints={},
    )
    defaults.update(kwargs)
    return LeadCreatedEvent(**defaults)


class ScoringTest(TestCase):

    def _score(self, **kwargs):
        from core.tasks.lead_tasks import _compute_initial_score
        return _compute_initial_score(make_event(**kwargs))

    def test_base_score(self):
        score = self._score()
        self.assertEqual(score, 40.0)

    def test_senior_title_boost(self):
        score = self._score(person=PersonData(name="X", email="x@x.com", title="VP of Engineering"))
        self.assertEqual(score, 60.0)  # base 40 + 20

    def test_ceo_title_boost(self):
        score = self._score(person=PersonData(name="X", email="x@x.com", title="CEO"))
        self.assertEqual(score, 60.0)

    def test_is_paid_boost(self):
        score = self._score(score_hints={"is_paid": True})
        self.assertEqual(score, 55.0)  # base 40 + 15

    def test_large_company_boost(self):
        score = self._score(company=CompanyData(name="Big Co", size="500"))
        self.assertEqual(score, 50.0)  # base 40 + 10

    def test_linkedin_url_boost(self):
        score = self._score(person=PersonData(name="X", email="x@x.com", linkedin_url="https://linkedin.com/in/x"))
        self.assertEqual(score, 45.0)  # base 40 + 5

    def test_linkedin_source_boost(self):
        score = self._score(source_app="linkedin_scraper")
        self.assertEqual(score, 50.0)  # base 40 + 10

    def test_combined_senior_paid_large(self):
        score = self._score(
            person=PersonData(name="X", email="x@x.com", title="Director of Sales",
                              linkedin_url="https://linkedin.com/in/x"),
            company=CompanyData(name="BigCo", size="200"),
            score_hints={"is_paid": True},
        )
        # base 40 + 20 (senior) + 15 (paid) + 10 (large) + 5 (linkedin url) = 90
        self.assertEqual(score, 90.0)

    def test_score_capped_at_100(self):
        score = self._score(
            source_app="linkedin_scraper",
            person=PersonData(name="X", email="x@x.com", title="CEO", linkedin_url="https://linkedin.com/in/x"),
            company=CompanyData(name="HugeCo", size="1000"),
            score_hints={"is_paid": True},
        )
        self.assertLessEqual(score, 100.0)
