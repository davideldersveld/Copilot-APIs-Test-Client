from __future__ import annotations

from datetime import datetime
import json
import threading
import traceback

import customtkinter as ctk

from copilot_client.apis import ChatApi, RetrievalApi, SearchApi
from copilot_client.auth import AuthManager
from copilot_client.config import AppSettings, ConfigurationError
from copilot_client.http import HttpClient
from copilot_client.logging_utils import configure_logging
from copilot_client.services import CopilotService


class MainWindow(ctk.CTk):
	def __init__(self, service: CopilotService):
		super().__init__()
		self._service = service
		self.title("Intelligence & Trust: Copilot APIs Test Client")
		self.geometry("1100x800")
		self.minsize(960, 700)

		self._status_label = ctk.CTkLabel(self, text="Not signed in")
		self._status_label.pack(anchor="w", padx=16, pady=(16, 8))

		self._request_progress_label = ctk.CTkLabel(
			self,
			text="",
		)
		self._request_progress_label.pack(anchor="w", padx=16, pady=(0, 4))

		self._request_progress_bar = ctk.CTkProgressBar(self)
		self._request_progress_bar.pack(fill="x", padx=16, pady=(0, 8))
		self._request_progress_bar.set(0)

		self._progress_active = False
		self._progress_total_seconds = max(1, int(self._service.request_timeout_seconds))
		self._progress_elapsed_seconds = 0.0
		self._progress_update_interval_seconds = 0.1
		self._set_progress_idle()

		action_row = ctk.CTkFrame(self)
		action_row.pack(fill="x", padx=16, pady=(0, 8))

		self._sign_in_btn = ctk.CTkButton(action_row, text="Sign in", command=self._sign_in)
		self._sign_in_btn.pack(side="left", padx=(8, 6), pady=8)

		self._sign_out_btn = ctk.CTkButton(action_row, text="Sign out", command=self._sign_out)
		self._sign_out_btn.pack(side="left", padx=6, pady=8)

		self._tabview = ctk.CTkTabview(self)
		self._tabview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

		self._tabview.add("Chat")
		self._tabview.add("Search")
		self._tabview.add("Retrieval")
		self._tabview.add("Batch")

		self._chat_prompt = ctk.CTkTextbox(self._tabview.tab("Chat"), height=140)
		self._chat_prompt.pack(fill="x", padx=12, pady=(12, 6))
		self._chat_prompt.insert("1.0", "Ask a grounded enterprise question...")

		self._web_grounding = ctk.BooleanVar(value=True)
		ctk.CTkCheckBox(
			self._tabview.tab("Chat"),
			text="Enable web grounding",
			variable=self._web_grounding,
		).pack(anchor="w", padx=12, pady=4)

		self._chat_mode = ctk.StringVar(value="Chat")
		self._chat_mode_selector = ctk.CTkSegmentedButton(
			self._tabview.tab("Chat"),
			values=["Chat", "Chat over Stream"],
			variable=self._chat_mode,
		)
		self._chat_mode_selector.pack(anchor="w", padx=12, pady=4)

		ctk.CTkButton(
			self._tabview.tab("Chat"),
			text="Send Chat Request",
			command=self._send_chat,
		).pack(anchor="w", padx=12, pady=8)

		self._chat_stream_status_label = ctk.CTkLabel(
			self._tabview.tab("Chat"),
			text="Stream status: idle",
		)
		self._chat_stream_status_label.pack(anchor="w", padx=12, pady=(0, 8))

		self._chat_formatted_output, self._chat_output = self._create_output_panes(
			self._tabview.tab("Chat"),
			height=400,
		)

		search_tab = self._tabview.tab("Search")
		ctk.CTkLabel(
			search_tab,
			text="Natural Language Query (required)",
			text_color="#d14343",
		).pack(anchor="w", padx=12, pady=(12, 2))
		self._search_query = ctk.CTkEntry(search_tab, placeholder_text="Natural language query")
		self._search_query.pack(fill="x", padx=12, pady=(0, 6))

		self._search_validation_label = ctk.CTkLabel(
			search_tab,
			text="",
			text_color="#d14343",
		)
		self._search_validation_label.pack(anchor="w", padx=12, pady=(0, 6))

		self._search_filter = ctk.CTkEntry(search_tab, placeholder_text="Optional KQL filterExpression")
		self._search_filter.pack(fill="x", padx=12, pady=6)

		self._search_page_size = ctk.CTkEntry(search_tab, placeholder_text="Page size (max 100)")
		self._search_page_size.pack(fill="x", padx=12, pady=6)
		self._search_page_size.insert(0, "10")

		self._search_next_link: str = ""
		self._search_next_page_btn = ctk.CTkButton(
			search_tab,
			text="Run Search Next Page",
			command=self._run_search_next_page,
			state="disabled",
		)
		self._search_next_page_btn.pack(anchor="w", padx=12, pady=(2, 2))

		self._search_next_page_label = ctk.CTkLabel(search_tab, text="")
		self._search_next_page_label.pack(anchor="w", padx=12, pady=(0, 6))

		ctk.CTkButton(search_tab, text="Run Search", command=self._run_search).pack(
			anchor="w", padx=12, pady=8
		)

		self._search_formatted_output, self._search_output = self._create_output_panes(
			search_tab,
			height=420,
		)

		retrieval_tab = self._tabview.tab("Retrieval")
		ctk.CTkLabel(
			retrieval_tab,
			text="Query String (required)",
			text_color="#d14343",
		).pack(anchor="w", padx=12, pady=(12, 2))
		self._retrieval_query = ctk.CTkEntry(retrieval_tab, placeholder_text="Natural language queryString")
		self._retrieval_query.pack(fill="x", padx=12, pady=(0, 6))

		ctk.CTkLabel(
			retrieval_tab,
			text="Data Source (required)",
			text_color="#d14343",
		).pack(anchor="w", padx=12, pady=(2, 2))
		self._retrieval_source = ctk.CTkEntry(
			retrieval_tab,
			placeholder_text="Data source (ex: sharePoint, oneDrive, externalItem)",
		)
		self._retrieval_source.pack(fill="x", padx=12, pady=(0, 6))

		self._retrieval_validation_label = ctk.CTkLabel(
			retrieval_tab,
			text="",
			text_color="#d14343",
		)
		self._retrieval_validation_label.pack(anchor="w", padx=12, pady=(0, 6))

		self._retrieval_filter = ctk.CTkEntry(
			retrieval_tab,
			placeholder_text="Optional KQL filterExpression",
		)
		self._retrieval_filter.pack(fill="x", padx=12, pady=6)

		self._retrieval_max_results = ctk.CTkEntry(retrieval_tab, placeholder_text="Max results (max 25)")
		self._retrieval_max_results.pack(fill="x", padx=12, pady=6)
		self._retrieval_max_results.insert(0, "10")

		ctk.CTkButton(retrieval_tab, text="Run Retrieval", command=self._run_retrieval).pack(
			anchor="w", padx=12, pady=8
		)

		self._retrieval_formatted_output, self._retrieval_output = self._create_output_panes(
			retrieval_tab,
			height=390,
		)

		batch_tab = self._tabview.tab("Batch")

		ctk.CTkLabel(batch_tab, text="Batch Chat Prompt (optional)").pack(
			anchor="w", padx=12, pady=(12, 2)
		)
		self._batch_chat_prompt = ctk.CTkTextbox(batch_tab, height=80)
		self._batch_chat_prompt.pack(fill="x", padx=12, pady=(0, 6))

		self._batch_web_grounding = ctk.BooleanVar(value=True)
		ctk.CTkCheckBox(
			batch_tab,
			text="Enable web grounding for batch chat",
			variable=self._batch_web_grounding,
		).pack(anchor="w", padx=12, pady=(0, 6))

		ctk.CTkLabel(batch_tab, text="Batch Search Query (optional)").pack(
			anchor="w", padx=12, pady=(2, 2)
		)
		self._batch_search_query = ctk.CTkEntry(
			batch_tab,
			placeholder_text="Natural language search query",
		)
		self._batch_search_query.pack(fill="x", padx=12, pady=(0, 6))

		ctk.CTkLabel(batch_tab, text="Batch Retrieval Query (optional)").pack(
			anchor="w", padx=12, pady=(2, 2)
		)
		self._batch_retrieval_query = ctk.CTkEntry(
			batch_tab,
			placeholder_text="Natural language retrieval queryString",
		)
		self._batch_retrieval_query.pack(fill="x", padx=12, pady=(0, 6))

		self._batch_retrieval_source = ctk.CTkEntry(
			batch_tab,
			placeholder_text="Retrieval data source when query provided (ex: sharePoint)",
		)
		self._batch_retrieval_source.pack(fill="x", padx=12, pady=(0, 6))
		self._batch_retrieval_source.insert(0, "sharePoint")

		self._batch_validation_label = ctk.CTkLabel(batch_tab, text="", text_color="#d14343")
		self._batch_validation_label.pack(anchor="w", padx=12, pady=(0, 6))

		ctk.CTkButton(batch_tab, text="Run Graph Batch", command=self._run_batch).pack(
			anchor="w", padx=12, pady=8
		)

		self._batch_formatted_output, self._batch_output = self._create_output_panes(
			batch_tab,
			height=320,
		)

		self._refresh_auth_state()

	def _run_in_background(
		self,
		formatted_widget: ctk.CTkTextbox,
		raw_widget: ctk.CTkTextbox,
		call,
		payload,
		on_success=None,
	):
		self._render_output(formatted_widget, "Running request...")
		self._render_output(raw_widget, "Running request...")
		self._start_request_progress()

		def worker():
			try:
				response = call(payload)
				raw_rendered = json.dumps(response, indent=2)
				formatted_rendered = self._extract_formatted_text(response)
				if on_success:
					self.after(0, lambda: on_success(response))
			except Exception as exc:
				raw_rendered = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
				formatted_rendered = f"{type(exc).__name__}: {exc}"

			self.after(
				0,
				lambda: self._render_dual_output(
					formatted_widget,
					raw_widget,
					formatted_rendered,
					raw_rendered,
				),
			)
			self.after(0, self._stop_request_progress)

		threading.Thread(target=worker, daemon=True).start()

	def _set_progress_idle(self):
		self._request_progress_label.configure(
			text=f"Request timeout: {self._progress_total_seconds}s"
		)
		self._request_progress_bar.set(0)

	def _start_request_progress(self):
		self._progress_active = True
		self._progress_elapsed_seconds = 0.0
		self._request_progress_bar.set(0)
		self._request_progress_label.configure(
			text=(
				f"Request in progress: 0.0s / {self._progress_total_seconds}s "
				"(timeout window)"
			)
		)
		self._tick_request_progress()

	def _tick_request_progress(self):
		if not self._progress_active:
			return

		self._progress_elapsed_seconds += self._progress_update_interval_seconds
		progress = min(1.0, self._progress_elapsed_seconds / self._progress_total_seconds)
		self._request_progress_bar.set(progress)

		if progress >= 1.0:
			self._request_progress_label.configure(
				text=(
					f"Reached timeout window ({self._progress_total_seconds}s). "
					"Waiting for response or timeout result..."
				)
			)
		else:
			self._request_progress_label.configure(
				text=(
					f"Request in progress: {self._progress_elapsed_seconds:.1f}s / "
					f"{self._progress_total_seconds}s (timeout window)"
				)
			)

		self.after(
			int(self._progress_update_interval_seconds * 1000),
			self._tick_request_progress,
		)

	def _stop_request_progress(self):
		self._progress_active = False
		self._set_progress_idle()

	def _create_output_panes(self, parent, height: int):
		container = ctk.CTkFrame(parent)
		container.pack(fill="both", expand=True, padx=12, pady=(4, 12))
		container.grid_columnconfigure(0, weight=1)
		container.grid_columnconfigure(1, weight=1)
		container.grid_rowconfigure(1, weight=1)

		formatted_label = ctk.CTkLabel(container, text="Formatted Text")
		formatted_label.grid(row=0, column=0, sticky="w", padx=(8, 6), pady=(8, 4))

		raw_label = ctk.CTkLabel(container, text="Raw JSON")
		raw_label.grid(row=0, column=1, sticky="w", padx=(6, 8), pady=(8, 4))

		formatted_widget = ctk.CTkTextbox(container, height=height)
		formatted_widget.grid(row=1, column=0, sticky="nsew", padx=(8, 6), pady=(0, 8))

		raw_widget = ctk.CTkTextbox(container, height=height)
		raw_widget.grid(row=1, column=1, sticky="nsew", padx=(6, 8), pady=(0, 8))

		return formatted_widget, raw_widget

	def _render_dual_output(
		self,
		formatted_widget: ctk.CTkTextbox,
		raw_widget: ctk.CTkTextbox,
		formatted_text: str,
		raw_text: str,
	):
		self._render_output(formatted_widget, formatted_text)
		self._render_output(raw_widget, raw_text)

	@staticmethod
	def _render_output(text_widget: ctk.CTkTextbox, text: str):
		text_widget.delete("1.0", "end")
		text_widget.insert("1.0", text)

	@staticmethod
	def _extract_formatted_text(response: dict[str, object]) -> str:
		batch_responses = response.get("responses") if isinstance(response, dict) else None
		if isinstance(batch_responses, list):
			formatted_parts = []
			for item in batch_responses:
				if not isinstance(item, dict):
					continue
				body = item.get("body")
				if not isinstance(body, dict):
					continue
				body_text = MainWindow._extract_formatted_text(body)
				if body_text and body_text != "No formatted text found in the response.":
					request_id = str(item.get("id", "?")).strip() or "?"
					formatted_parts.append(f"Batch Request {request_id}\n{body_text}")
			if formatted_parts:
				return "\n\n===\n\n".join(formatted_parts)

		final_conversation = response.get("finalConversation") if isinstance(response, dict) else None
		if isinstance(final_conversation, dict):
			response = final_conversation

		messages = response.get("messages") if isinstance(response, dict) else None
		if isinstance(messages, list):
			chat_texts = []
			for message in messages:
				if isinstance(message, dict):
					text = str(message.get("text", "")).strip()
					if text:
						chat_texts.append(text)
			if chat_texts:
				return "\n\n---\n\n".join(chat_texts)

		search_hits = response.get("searchHits") if isinstance(response, dict) else None
		if isinstance(search_hits, list):
			search_previews = []
			for hit in search_hits:
				if not isinstance(hit, dict):
					continue
				preview = str(hit.get("preview", "")).strip()
				if not preview:
					continue
				resource_metadata = hit.get("resourceMetadata")
				title = ""
				if isinstance(resource_metadata, dict):
					title = str(resource_metadata.get("title", "")).strip()
				if not title:
					title = str(hit.get("webUrl", "")).strip()
				search_previews.append(f"{title}\n{preview}" if title else preview)
			if search_previews:
				return "\n\n---\n\n".join(search_previews)

		retrieval_hits = response.get("retrievalHits") if isinstance(response, dict) else None
		if isinstance(retrieval_hits, list):
			retrieval_texts = []
			for hit in retrieval_hits:
				if not isinstance(hit, dict):
					continue
				extracts = hit.get("extracts")
				if not isinstance(extracts, list):
					continue
				for extract in extracts:
					if isinstance(extract, dict):
						text = str(extract.get("text", "")).strip()
						if text:
							retrieval_texts.append(text)
			if retrieval_texts:
				return "\n\n---\n\n".join(retrieval_texts)

		return "No formatted text found in the response."

	def _refresh_auth_state(self):
		try:
			state = self._service.auth_state()
			if state.is_signed_in:
				username = self._mask_username_domain(state.username or "signed-in user")
				tenant = self._mask_tenant_id(state.tenant_id or "unknown tenant")
				self._status_label.configure(text=f"Signed in as {username} | Tenant: {tenant}")
				self._set_auth_button_state(is_signed_in=True)
			else:
				self._status_label.configure(text="Not signed in")
				self._set_auth_button_state(is_signed_in=False)
		except Exception as exc:
			self._status_label.configure(text=f"Sign in failed: {exc}")
			self._set_auth_button_state(is_signed_in=False)

	def _set_auth_button_state(self, is_signed_in: bool):
		if is_signed_in:
			self._sign_in_btn.configure(state="disabled")
			self._sign_out_btn.configure(state="normal")
			return

		self._sign_in_btn.configure(state="normal")
		self._sign_out_btn.configure(state="disabled")

	def _sign_in(self):
		self._status_label.configure(text="Signing in...")
		self._sign_in_btn.configure(state="disabled")

		def worker():
			try:
				state = self._service.sign_in()
				if state.is_signed_in:
					username = self._mask_username_domain(state.username or "signed-in user")
					tenant = self._mask_tenant_id(state.tenant_id or "unknown tenant")
					text = f"Signed in as {username} | Tenant: {tenant}"
					is_signed_in = True
				else:
					text = "Not signed in"
					is_signed_in = False
			except Exception as exc:
				text = f"Sign in failed: {exc}"
				is_signed_in = False

			self.after(
				0,
				lambda: (
					self._status_label.configure(text=text),
					self._set_auth_button_state(is_signed_in=is_signed_in),
				),
			)

		threading.Thread(target=worker, daemon=True).start()

	def _sign_out(self):
		try:
			self._service.sign_out()
			self._status_label.configure(text="Not signed in")
			self._set_auth_button_state(is_signed_in=False)
		except Exception as exc:
			self._status_label.configure(text=f"Sign out failed: {exc}")

	def _send_chat(self):
		prompt = self._chat_prompt.get("1.0", "end").strip()
		mode = self._chat_mode.get().strip()
		use_stream = mode == "Chat over Stream"
		self._reset_chat_stream_status()
		payload = {
			"messages": [{"role": "user", "content": prompt}],
			"webSearchEnabled": bool(self._web_grounding.get()),
			"useStream": use_stream,
		}
		if use_stream:
			self._run_chat_stream_in_background(payload)
			return

		self._run_in_background(
			self._chat_formatted_output,
			self._chat_output,
			self._service.send_chat,
			payload,
		)

	def _run_chat_stream_in_background(self, payload: dict[str, object]):
		self._render_output(self._chat_formatted_output, "Connecting to stream...")
		self._render_output(self._chat_output, "Connecting to stream...")
		self._set_chat_stream_status("connecting", 0)
		self._start_request_progress()

		stream_events: list[dict[str, object]] = []

		def on_stream_event(event: dict[str, object]):
			stream_events.append(event)
			event_count = len(stream_events)
			self.after(0, lambda: self._set_chat_stream_status("receiving", event_count))
			response_snapshot = {
				"streamEvents": list(stream_events),
				"finalConversation": event,
			}
			raw_rendered = json.dumps(response_snapshot, indent=2)
			formatted_rendered = self._extract_formatted_text(response_snapshot)
			if formatted_rendered == "No formatted text found in the response." and len(stream_events) > 1:
				return
			self.after(
				0,
				lambda: self._render_dual_output(
					self._chat_formatted_output,
					self._chat_output,
					formatted_rendered,
					raw_rendered,
				),
			)

		def worker():
			try:
				response = self._service.send_chat(payload, on_stream_event=on_stream_event)
				raw_rendered = json.dumps(response, indent=2)
				formatted_rendered = self._extract_formatted_text(response)
				self.after(0, lambda: self._set_chat_stream_status("completed", len(stream_events)))
			except Exception as exc:
				raw_rendered = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
				formatted_rendered = f"{type(exc).__name__}: {exc}"
				self.after(0, lambda: self._set_chat_stream_status("failed", len(stream_events)))

			self.after(
				0,
				lambda: self._render_dual_output(
					self._chat_formatted_output,
					self._chat_output,
					formatted_rendered,
					raw_rendered,
				),
			)
			self.after(0, self._stop_request_progress)

		threading.Thread(target=worker, daemon=True).start()

	def _reset_chat_stream_status(self):
		self._chat_stream_status_label.configure(text="Stream status: idle")

	def _set_chat_stream_status(self, state: str, event_count: int):
		timestamp = datetime.now().strftime("%H:%M:%S")
		if state == "idle":
			self._chat_stream_status_label.configure(text="Stream status: idle")
			return

		self._chat_stream_status_label.configure(
			text=f"Stream status: {state} | events: {event_count} | last update: {timestamp}"
		)

	def _run_search(self):
		query = self._search_query.get().strip()
		if not query:
			self._search_validation_label.configure(
				text="Please fill in the required Natural Language Query field."
			)
			self._render_output(
				self._search_formatted_output,
				"Please fill in all required fields before running Search.",
			)
			self._render_output(
				self._search_output,
				"Validation error: required Natural Language Query is missing.",
			)
			return

		self._search_validation_label.configure(text="")
		self._search_next_link = ""
		self._search_next_page_btn.configure(state="disabled")
		self._search_next_page_label.configure(text="")
		payload = {
			"query": query,
			"pageSize": self._parse_int(self._search_page_size.get(), 10, 1, 100),
		}
		filter_expression = self._search_filter.get().strip()
		if filter_expression:
			payload["filterExpression"] = filter_expression
		self._run_in_background(
			self._search_formatted_output,
			self._search_output,
			self._service.run_search,
			payload,
			on_success=self._update_search_next_link,
		)

	def _run_search_next_page(self):
		if not self._search_next_link:
			self._search_next_page_label.configure(text="No next page available.")
			return

		self._run_in_background(
			self._search_formatted_output,
			self._search_output,
			self._service.run_search_next_page,
			self._search_next_link,
			on_success=self._update_search_next_link,
		)

	def _update_search_next_link(self, response: dict[str, object]):
		next_link = ""
		total_count = 0
		hits_count = 0
		if isinstance(response, dict):
			next_link = str(response.get("@odata.nextLink", "")).strip()
			total_count_value = response.get("totalCount", 0)
			if isinstance(total_count_value, int):
				total_count = total_count_value
			search_hits = response.get("searchHits")
			if isinstance(search_hits, list):
				hits_count = len(search_hits)

		self._search_next_link = next_link
		if next_link:
			self._search_next_page_btn.configure(state="normal")
			self._search_next_page_label.configure(text="Next page available. Click 'Run Search Next Page'.")
		else:
			self._search_next_page_btn.configure(state="disabled")
			if total_count > hits_count and hits_count > 0:
				self._search_next_page_label.configure(
					text="No continuation token returned by API for this result set."
				)
			else:
				self._search_next_page_label.configure(text="No additional pages.")

	def _run_retrieval(self):
		query = self._retrieval_query.get().strip()
		data_source = self._retrieval_source.get().strip()
		if not query or not data_source:
			self._retrieval_validation_label.configure(
				text="Please fill in all required fields: Query String and Data Source."
			)
			self._render_output(
				self._retrieval_formatted_output,
				"Please fill in all required fields before running Retrieval.",
			)
			self._render_output(
				self._retrieval_output,
				"Validation error: required fields are missing.",
			)
			return

		self._retrieval_validation_label.configure(text="")
		payload = {
			"queryString": query,
			"dataSource": data_source,
			"maximumNumberOfResults": self._parse_int(
				self._retrieval_max_results.get(),
				10,
				1,
				25,
			),
		}
		filter_expression = self._retrieval_filter.get().strip()
		if filter_expression:
			payload["filterExpression"] = filter_expression
		self._run_in_background(
			self._retrieval_formatted_output,
			self._retrieval_output,
			self._service.run_retrieval,
			payload,
		)

	def _run_batch(self):
		chat_prompt = self._batch_chat_prompt.get("1.0", "end").strip()
		search_query = self._batch_search_query.get().strip()
		retrieval_query = self._batch_retrieval_query.get().strip()
		retrieval_source = self._batch_retrieval_source.get().strip()

		if not chat_prompt and not search_query and not retrieval_query:
			self._batch_validation_label.configure(
				text="Provide at least one operation: Chat prompt, Search query, or Retrieval query."
			)
			self._render_output(
				self._batch_formatted_output,
				"Validation error: no batch operations provided.",
			)
			self._render_output(
				self._batch_output,
				"Validation error: no batch operations provided.",
			)
			return

		if retrieval_query and not retrieval_source:
			self._batch_validation_label.configure(
				text="Retrieval data source is required when Retrieval query is provided."
			)
			self._render_output(
				self._batch_formatted_output,
				"Validation error: retrieval data source is missing.",
			)
			self._render_output(
				self._batch_output,
				"Validation error: retrieval data source is missing.",
			)
			return

		self._batch_validation_label.configure(text="")
		payload: dict[str, object] = {}

		if chat_prompt:
			payload["chat"] = {
				"prompt": chat_prompt,
				"webSearchEnabled": bool(self._batch_web_grounding.get()),
			}

		if search_query:
			payload["search"] = {
				"query": search_query,
				"pageSize": self._parse_int(self._search_page_size.get(), 10, 1, 100),
			}

		if retrieval_query:
			payload["retrieval"] = {
				"queryString": retrieval_query,
				"dataSource": retrieval_source,
				"maximumNumberOfResults": self._parse_int(
					self._retrieval_max_results.get(),
					10,
					1,
					25,
				),
			}

		self._run_in_background(
			self._batch_formatted_output,
			self._batch_output,
			self._service.run_graph_batch,
			payload,
		)

	@staticmethod
	def _parse_int(value: str, default: int, minimum: int, maximum: int) -> int:
		try:
			parsed = int(value)
		except ValueError:
			return default
		if parsed < minimum:
			return minimum
		if parsed > maximum:
			return maximum
		return parsed

	@staticmethod
	def _mask_tenant_id(tenant_id: str) -> str:
		value = tenant_id.strip()
		parts = value.split("-")
		if len(parts) == 5 and all(parts):
			return f"{parts[0]}-****-****-****-{parts[4]}"

		if len(value) > 10:
			return f"{value[:4]}...{value[-4:]}"
		return value

	@staticmethod
	def _mask_username_domain(username: str) -> str:
		value = username.strip()
		if "@" not in value:
			return value

		local, domain = value.split("@", 1)
		if not domain:
			return value

		mask_count = min(6, len(domain))
		masked_domain = ("*" * mask_count) + domain[mask_count:]
		return f"{local}@{masked_domain}"


def build_service() -> CopilotService:
	settings = AppSettings.from_env()
	auth_manager = AuthManager(settings)
	http_client = HttpClient(settings)
	return CopilotService(
		auth_manager=auth_manager,
		chat_api=ChatApi(settings, http_client),
		search_api=SearchApi(settings, http_client),
		retrieval_api=RetrievalApi(settings, http_client),
		request_timeout_seconds=settings.timeout_seconds,
	)


def run_app() -> None:
	configure_logging()
	ctk.set_appearance_mode("System")
	ctk.set_default_color_theme("blue")

	try:
		service = build_service()
	except ConfigurationError as exc:
		app = ctk.CTk()
		app.title("Copilot API Client - Configuration Error")
		app.geometry("760x360")
		message = ctk.CTkTextbox(app)
		message.pack(fill="both", expand=True, padx=16, pady=16)
		message.insert(
			"1.0",
			"Configuration error. Set required environment variables and restart:\n\n"
			f"{exc}\n\n"
			"Required:\n"
			"- COPILOT_TENANT_ID\n"
			"- COPILOT_CLIENT_ID\n"
			"- COPILOT_SCOPES\n",
		)
		app.mainloop()
		return

	window = MainWindow(service)
	window.mainloop()
