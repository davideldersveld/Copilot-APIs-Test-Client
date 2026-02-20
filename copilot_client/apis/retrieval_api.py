from __future__ import annotations

from typing import Any

from copilot_client.config import AppSettings
from copilot_client.http import HttpClient


class RetrievalApi:
    def __init__(self, settings: AppSettings, http_client: HttpClient):
        self._settings = settings
        self._http_client = http_client

    @property
    def retrieval_path(self) -> str:
        return self._settings.retrieval_path

    def retrieve(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._http_client.post_json(token, self._settings.retrieval_path, payload)

    @staticmethod
    def build_batch_request(request_id: str, payload: dict[str, Any], retrieval_path: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "method": "POST",
            "url": retrieval_path,
            "headers": {"Content-Type": "application/json"},
            "body": payload,
        }
