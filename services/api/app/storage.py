import os
from typing import Any

import httpx


class SupabaseStore:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.service_key)

    def request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        prefer: str = "return=representation",
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError("Supabase storage is not configured.")

        headers = {
            "apikey": self.service_key,
            "Content-Type": "application/json",
            "Prefer": prefer,
        }
        if not self.service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.service_key}"

        response = httpx.request(
            method,
            f"{self.url}/rest/v1/{table}",
            params=params,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        if not response.content:
            return []
        return response.json()


store = SupabaseStore()
