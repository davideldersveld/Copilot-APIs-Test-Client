from __future__ import annotations

import time
from typing import Any, Callable

import requests

from copilot_client.config import AppSettings


class ApiHttpError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class HttpClient:
    def __init__(self, settings: AppSettings):
        self._settings = settings
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def post_json(self, token: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.base_url}{path}"
        return self.post_absolute_json(token, url, payload)

    def post_absolute_json(self, token: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"}

        last_error: ApiHttpError | None = None
        attempts = self._settings.retry_attempts + 1
        for attempt in range(1, attempts + 1):
            response = self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._settings.timeout_seconds,
            )

            if response.ok:
                if not response.content:
                    return {}
                return response.json()

            message = response.text[:500]
            last_error = ApiHttpError(
                status_code=response.status_code,
                message=f"HTTP {response.status_code}: {message}",
            )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(1.5 * attempt)
                continue
            raise last_error

        if last_error is None:
            raise ApiHttpError(status_code=0, message="Request failed")
        raise last_error

    def get_json(
        self,
        token: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._settings.base_url}{path}"
        return self.get_absolute_json(token, url, params)

    def get_absolute_json(
        self,
        token: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"}

        response = self._session.get(
            url,
            headers=headers,
            params=params,
            timeout=self._settings.timeout_seconds,
        )

        if response.ok:
            if not response.content:
                return {}
            return response.json()

        message = response.text[:500]
        raise ApiHttpError(
            status_code=response.status_code,
            message=f"HTTP {response.status_code}: {message}",
        )

    def post_sse_json(
        self,
        token: str,
        path: str,
        payload: dict[str, Any],
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._settings.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }

        response = self._session.post(
            url,
            headers=headers,
            json=payload,
            timeout=self._settings.timeout_seconds,
            stream=True,
        )

        if not response.ok:
            message = response.text[:500]
            raise ApiHttpError(
                status_code=response.status_code,
                message=f"HTTP {response.status_code}: {message}",
            )

        events: list[dict[str, Any]] = []
        data_lines: list[str] = []

        for raw_line in response.iter_lines(decode_unicode=True):
            line = (raw_line or "").strip()

            if not line:
                if data_lines:
                    event_payload = "\n".join(data_lines).strip()
                    data_lines.clear()
                    if event_payload:
                        event = self._parse_sse_event(event_payload)
                        events.append(event)
                        if on_event is not None:
                            on_event(event)
                continue

            if line.startswith("data:"):
                data_lines.append(line[5:].strip())

        if data_lines:
            event_payload = "\n".join(data_lines).strip()
            if event_payload:
                event = self._parse_sse_event(event_payload)
                events.append(event)
                if on_event is not None:
                    on_event(event)

        return events

    @staticmethod
    def _parse_sse_event(event_payload: str) -> dict[str, Any]:
        try:
            parsed = requests.models.complexjson.loads(event_payload)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except Exception:
            return {"raw": event_payload}
