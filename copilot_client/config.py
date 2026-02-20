from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class AppSettings:
    tenant_id: str
    client_id: str
    authority: str
    scopes: tuple[str, ...]
    base_url: str
    chat_path: str
    search_path: str
    retrieval_path: str
    batch_path: str
    timeout_seconds: int
    retry_attempts: int
    token_cache_path: str
    auth_flow: str
    redirect_uri: str

    @staticmethod
    def from_env() -> "AppSettings":
        _load_dotenv_if_present()

        tenant_id = os.getenv("COPILOT_TENANT_ID", "").strip()
        client_id = os.getenv("COPILOT_CLIENT_ID", "").strip()
        authority = os.getenv("COPILOT_AUTHORITY", "").strip()
        if not authority and tenant_id:
            authority = f"https://login.microsoftonline.com/{tenant_id}"

        raw_scopes = os.getenv("COPILOT_SCOPES", "").strip()
        scopes = tuple(s.strip() for s in raw_scopes.split(",") if s.strip())

        base_url = os.getenv("COPILOT_BASE_URL", "https://graph.microsoft.com/beta").rstrip("/")
        chat_path = os.getenv("COPILOT_CHAT_PATH", "/copilot/conversations").strip()
        search_path = os.getenv("COPILOT_SEARCH_PATH", "/copilot/search").strip()
        retrieval_path = os.getenv("COPILOT_RETRIEVAL_PATH", "/copilot/retrieval").strip()
        batch_path = os.getenv("COPILOT_BATCH_PATH", "/$batch").strip()

        timeout_seconds = int(os.getenv("COPILOT_TIMEOUT_SECONDS", "45"))
        retry_attempts = int(os.getenv("COPILOT_RETRY_ATTEMPTS", "3"))

        default_cache_path = os.path.join(
            os.getenv("LOCALAPPDATA", os.getcwd()),
            "CopilotApiClient",
            "msal_cache.bin",
        )
        token_cache_path = os.getenv("COPILOT_TOKEN_CACHE_PATH", default_cache_path)
        auth_flow = os.getenv("COPILOT_AUTH_FLOW", "interactive_then_device").strip().lower()
        redirect_uri = os.getenv("COPILOT_REDIRECT_URI", "http://localhost").strip()

        settings = AppSettings(
            tenant_id=tenant_id,
            client_id=client_id,
            authority=authority,
            scopes=scopes,
            base_url=base_url,
            chat_path=chat_path,
            search_path=search_path,
            retrieval_path=retrieval_path,
            batch_path=batch_path,
            timeout_seconds=timeout_seconds,
            retry_attempts=retry_attempts,
            token_cache_path=token_cache_path,
            auth_flow=auth_flow,
            redirect_uri=redirect_uri,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        missing = []
        if not self.tenant_id:
            missing.append("COPILOT_TENANT_ID")
        if not self.client_id:
            missing.append("COPILOT_CLIENT_ID")
        if not self.authority:
            missing.append("COPILOT_AUTHORITY")
        if not self.scopes:
            missing.append("COPILOT_SCOPES")

        if missing:
            raise ConfigurationError(
                "Missing required settings: " + ", ".join(missing)
            )

        path_fields = {
            "COPILOT_CHAT_PATH": self.chat_path,
            "COPILOT_SEARCH_PATH": self.search_path,
            "COPILOT_RETRIEVAL_PATH": self.retrieval_path,
            "COPILOT_BATCH_PATH": self.batch_path,
        }
        invalid_paths = [name for name, value in path_fields.items() if not value.startswith("/")]
        if invalid_paths:
            raise ConfigurationError(
                "Endpoint paths must start with '/': " + ", ".join(invalid_paths)
            )

        if self.timeout_seconds <= 0:
            raise ConfigurationError("COPILOT_TIMEOUT_SECONDS must be greater than 0")

        if self.retry_attempts < 0:
            raise ConfigurationError("COPILOT_RETRY_ATTEMPTS must be 0 or greater")

        valid_auth_flows = {"interactive", "device_code", "interactive_then_device"}
        if self.auth_flow not in valid_auth_flows:
            raise ConfigurationError(
                "COPILOT_AUTH_FLOW must be one of: interactive, device_code, interactive_then_device"
            )


def _load_dotenv_if_present(file_name: str = ".env") -> None:
    for candidate in _candidate_env_files(file_name):
        _load_env_file(candidate)


def _candidate_env_files(file_name: str) -> list[Path]:
    candidates: list[Path] = []

    explicit = os.getenv("COPILOT_ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    cwd_env = Path.cwd() / file_name
    candidates.append(cwd_env)

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / file_name)
    else:
        project_root = Path(__file__).resolve().parent.parent
        candidates.append(project_root / file_name)

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        normalized = str(path.resolve()) if path.exists() else str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(path)
    return unique_candidates


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    try:
        with path.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return
