from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiResult:
    endpoint: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AuthState:
    is_signed_in: bool
    username: str | None = None
    tenant_id: str | None = None
