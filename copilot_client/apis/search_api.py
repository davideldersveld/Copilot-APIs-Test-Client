from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from copilot_client.config import AppSettings
from copilot_client.http import ApiHttpError, HttpClient


class SearchApi:
    def __init__(self, settings: AppSettings, http_client: HttpClient):
        self._settings = settings
        self._http_client = http_client

    @property
    def search_path(self) -> str:
        return self._settings.search_path

    def search(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._http_client.post_json(token, self._settings.search_path, payload)

    def search_next_page(self, token: str, next_link: str) -> dict[str, Any]:
        next_url = next_link.strip()
        if not next_url:
            raise ValueError("Search next link is required")

        if next_url.startswith("/"):
            return self._http_client.post_json(token, next_url, {})

        parsed = urlparse(next_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Invalid search next link")

        try:
            return self._http_client.post_absolute_json(token, next_url, {})
        except ApiHttpError as exc:
            if exc.status_code in (400, 404, 405):
                return self._http_client.get_absolute_json(token, next_url)
            raise

    @staticmethod
    def build_batch_request(request_id: str, payload: dict[str, Any], search_path: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "method": "POST",
            "url": search_path,
            "headers": {"Content-Type": "application/json"},
            "body": payload,
        }

    def run_graph_batch(self, token: str, requests_payload: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"requests": requests_payload}
        return self._http_client.post_json(token, self._settings.batch_path, payload)
