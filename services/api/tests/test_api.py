import unittest

from fastapi.testclient import TestClient

from services.api.app.main import app


class PersonaBridgeApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def create_session(self, memory_enabled: bool = True) -> dict:
        response = self.client.post(
            "/api/sessions",
            json={"display_name": "Test session", "memory_enabled": memory_enabled},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_session_message_and_memory_deletion(self) -> None:
        session = self.create_session()
        session_id = session["session_id"]

        response = self.client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Remember that I prefer concise architecture notes."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[-1]["role"], "assistant")

        candidates = self.client.get(f"/api/sessions/{session_id}/memory-candidates").json()
        self.assertEqual(len(candidates), 1)

        deleted = self.client.delete(f"/api/memory-candidates/{candidates[0]['candidate_id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["summary"], "[deleted]")
        self.assertEqual(self.client.get(f"/api/sessions/{session_id}/memory-candidates").json(), [])

    def test_secret_text_is_not_promoted_to_memory(self) -> None:
        session_id = self.create_session()["session_id"]
        self.client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "My API key should never become durable memory."},
        )
        candidates = self.client.get(f"/api/sessions/{session_id}/memory-candidates").json()
        self.assertEqual(candidates, [])

    def test_external_action_requires_approval(self) -> None:
        session_id = self.create_session(memory_enabled=False)["session_id"]
        messages = self.client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Send an email for me."},
        ).json()
        self.assertIsNotNone(messages[-1]["approval_request_id"])

        approvals = self.client.get(f"/api/sessions/{session_id}/approvals").json()
        self.assertEqual(approvals[0]["status"], "pending")
        decided = self.client.post(
            f"/api/approvals/{approvals[0]['request_id']}/decision",
            json={"decision": "rejected"},
        )
        self.assertEqual(decided.json()["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
