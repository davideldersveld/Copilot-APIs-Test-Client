from __future__ import annotations

from typing import Any

from copilot_client.config import AppSettings
from copilot_client.http import HttpClient


class AiInteractionsApi:
    def __init__(self, settings: AppSettings, http_client: HttpClient):
        self._settings = settings
        self._http_client = http_client

    def get_all_enterprise_interactions(
        self,
        token: str,
        user_id: str,
        top: int | None = None,
        filter_expression: str | None = None,
    ) -> dict[str, Any]:
        path = self._settings.ai_interactions_path_template.format(user_id=user_id)
        params: dict[str, Any] = {}
        if top is not None:
            params["$top"] = top
        if filter_expression:
            params["$filter"] = filter_expression

        return self._http_client.get_json(
            token,
            path,
            params=params or None,
        )
