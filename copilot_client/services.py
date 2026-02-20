from __future__ import annotations

from typing import Any, Callable

from copilot_client.apis import ChatApi, RetrievalApi, SearchApi
from copilot_client.auth import AuthManager


class CopilotService:
    def __init__(
        self,
        auth_manager: AuthManager,
        chat_api: ChatApi,
        search_api: SearchApi,
        retrieval_api: RetrievalApi,
        request_timeout_seconds: int,
    ):
        self._auth_manager = auth_manager
        self._chat_api = chat_api
        self._search_api = search_api
        self._retrieval_api = retrieval_api
        self._request_timeout_seconds = request_timeout_seconds

    @property
    def request_timeout_seconds(self) -> int:
        return self._request_timeout_seconds

    def auth_state(self):
        return self._auth_manager.get_auth_state()

    def sign_in(self):
        return self._auth_manager.sign_in()

    def sign_out(self) -> None:
        self._auth_manager.sign_out()

    def send_chat(
        self,
        payload: dict[str, Any],
        on_stream_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        token = self._auth_manager.acquire_access_token()
        return self._chat_api.send(token, payload, on_stream_event=on_stream_event)

    def run_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._auth_manager.acquire_access_token()
        return self._search_api.search(token, payload)

    def run_search_next_page(self, next_link: str) -> dict[str, Any]:
        token = self._auth_manager.acquire_access_token()
        return self._search_api.search_next_page(token, next_link)

    def run_retrieval(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._auth_manager.acquire_access_token()
        return self._retrieval_api.retrieve(token, payload)

    def run_graph_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._auth_manager.acquire_access_token()

        requests_payload: list[dict[str, Any]] = []
        request_number = 1

        chat_payload = payload.get("chat")
        if isinstance(chat_payload, dict):
            prompt = str(chat_payload.get("prompt", "")).strip()
            if prompt:
                requests_payload.append(
                    self._chat_api.build_batch_request(
                        token,
                        str(request_number),
                        {
                            "prompt": prompt,
                            "webSearchEnabled": bool(chat_payload.get("webSearchEnabled", True)),
                        },
                    )
                )
                request_number += 1

        search_payload = payload.get("search")
        if isinstance(search_payload, dict):
            query = str(search_payload.get("query", "")).strip()
            if query:
                requests_payload.append(
                    self._search_api.build_batch_request(
                        str(request_number),
                        search_payload,
                        self._search_api.search_path,
                    )
                )
                request_number += 1

        retrieval_payload = payload.get("retrieval")
        if isinstance(retrieval_payload, dict):
            query_string = str(retrieval_payload.get("queryString", "")).strip()
            data_source = str(retrieval_payload.get("dataSource", "")).strip()
            if query_string and data_source:
                requests_payload.append(
                    self._retrieval_api.build_batch_request(
                        str(request_number),
                        retrieval_payload,
                        self._retrieval_api.retrieval_path,
                    )
                )

        if not requests_payload:
            raise ValueError(
                "Provide at least one operation for batch: Chat prompt, Search query, or Retrieval query+data source."
            )

        return self._search_api.run_graph_batch(token, requests_payload)
