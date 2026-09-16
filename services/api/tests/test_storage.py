import os
import unittest
from unittest.mock import patch

from services.api.app.storage import SupabaseStore


class SupabaseStoreTest(unittest.TestCase):
    def test_new_secret_key_is_not_sent_as_bearer_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test_key_value_1234567890",
            },
        ):
            store = SupabaseStore()

        with patch("services.api.app.storage.httpx.request") as request:
            request.return_value.content = b"[]"
            request.return_value.json.return_value = []
            request.return_value.raise_for_status.return_value = None
            store.request("GET", "sessions")

        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["apikey"], "sb_secret_test_key_value_1234567890")
        self.assertNotIn("Authorization", headers)

    def test_legacy_service_role_key_keeps_bearer_header(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "legacy-jwt",
            },
        ):
            store = SupabaseStore()

        with patch("services.api.app.storage.httpx.request") as request:
            request.return_value.content = b"[]"
            request.return_value.json.return_value = []
            request.return_value.raise_for_status.return_value = None
            store.request("GET", "sessions")

        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer legacy-jwt")


if __name__ == "__main__":
    unittest.main()
