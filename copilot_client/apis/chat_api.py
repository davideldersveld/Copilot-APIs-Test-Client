from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Callable

from copilot_client.config import AppSettings
from copilot_client.http import HttpClient


class ChatApi:
    def __init__(self, settings: AppSettings, http_client: HttpClient):
        self._settings = settings
        self._http_client = http_client
        self._conversation_id: str | None = None

    def send(
        self,
        token: str,
        payload: dict[str, Any],
        on_stream_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        use_stream = bool(payload.get("useStream", False))
        if not self._conversation_id:
            created = self._http_client.post_json(token, self._settings.chat_path, {})
            self._conversation_id = str(created.get("id", "")).strip() or None
            if not self._conversation_id:
                raise RuntimeError("Chat API did not return a conversation id")

        normalized_payload = self._normalize_payload(payload)
        if use_stream:
            stream_path = f"{self._settings.chat_path}/{self._conversation_id}/chatOverStream"
            stream_events = self._http_client.post_sse_json(
                token,
                stream_path,
                normalized_payload,
                on_event=on_stream_event,
            )
            final_conversation = stream_events[-1] if stream_events else {}
            return {
                "streamEvents": stream_events,
                "finalConversation": final_conversation,
            }

        chat_path = f"{self._settings.chat_path}/{self._conversation_id}/chat"
        return self._http_client.post_json(token, chat_path, normalized_payload)

    def build_batch_request(self, token: str, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._conversation_id:
            created = self._http_client.post_json(token, self._settings.chat_path, {})
            self._conversation_id = str(created.get("id", "")).strip() or None
            if not self._conversation_id:
                raise RuntimeError("Chat API did not return a conversation id")

        normalized_payload = self._normalize_payload(payload)
        chat_path = f"{self._settings.chat_path}/{self._conversation_id}/chat"
        return {
            "id": request_id,
            "method": "POST",
            "url": chat_path,
            "headers": {"Content-Type": "application/json"},
            "body": normalized_payload,
        }

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if "message" in payload and "locationHint" in payload:
            return payload

        text = ""
        messages = payload.get("messages")
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, dict):
                text = str(first.get("content", "")).strip()

        if not text:
            text = str(payload.get("prompt", "")).strip()

        if not text:
            raise ValueError("Chat message text is required")

        is_web_enabled = bool(payload.get("webSearchEnabled", True))

        return {
            "message": {
                "text": text,
            },
            "locationHint": {
                "timeZone": ChatApi._resolve_timezone(),
            },
            "contextualResources": {
                "webContext": {
                    "isWebEnabled": is_web_enabled,
                }
            },
        }

    @staticmethod
    def _resolve_timezone() -> str:
        configured_timezone = os.getenv("COPILOT_TIMEZONE", "").strip()
        if configured_timezone:
            return configured_timezone

        local_tzinfo = datetime.now(timezone.utc).astimezone().tzinfo
        local_key = getattr(local_tzinfo, "key", None)
        if isinstance(local_key, str) and "/" in local_key:
            return local_key

        local_name = datetime.now(timezone.utc).astimezone().tzname() or ""
        if "/" in local_name:
            return local_name

        return "Etc/UTC"
