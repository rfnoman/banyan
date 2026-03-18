"""
API tests for /api/people/ endpoints.
Mocks Neo4j so no live database is needed.
"""
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient


class PeopleAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("testuser", password="password")
        self.client.force_authenticate(user=self.user)

    @patch("core.api.views.people.get_all_people", return_value=[
        {"id": "p1", "name": "Alice", "email": "alice@test.com", "score": 70, "ai_tags": "[]"},
    ])
    def test_list_people(self, mock_get):
        response = self.client.get("/api/people/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Alice")

    @patch("core.api.views.people.get_person_with_connections", return_value={"id": "p1", "name": "Alice", "email": "alice@test.com"})
    @patch("core.api.views.people.create_or_merge_person", return_value="p1")
    def test_create_person(self, mock_create, mock_get):
        response = self.client.post("/api/people/", {"name": "Alice", "email": "alice@test.com"}, format="json")
        self.assertEqual(response.status_code, 201)
        mock_create.assert_called_once()

    def test_create_person_missing_fields(self):
        response = self.client.post("/api/people/", {"name": "NoEmail"}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("core.api.views.people.get_person_with_connections", return_value={"id": "abc", "name": "Bob", "email": "bob@test.com"})
    def test_get_person_detail(self, mock_get):
        response = self.client.get("/api/people/abc/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Bob")

    @patch("core.api.views.people.get_person_with_connections", return_value={})
    def test_person_not_found(self, mock_get):
        response = self.client.get("/api/people/nonexistent/")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/people/")
        self.assertEqual(response.status_code, 401)
