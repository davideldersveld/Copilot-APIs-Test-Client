from __future__ import annotations

import os
from typing import Any

import msal
from msal_extensions import (
    FilePersistence,
    FilePersistenceWithDataProtection,
    PersistedTokenCache,
)

from copilot_client.config import AppSettings
from copilot_client.models import AuthState


class AuthenticationError(RuntimeError):
    pass


class AuthManager:
    def __init__(self, settings: AppSettings):
        self._settings = settings
        self._cache = PersistedTokenCache(self._build_persistence(settings.token_cache_path))
        self._app = msal.PublicClientApplication(
            client_id=settings.client_id,
            authority=settings.authority,
            token_cache=self._cache,
        )

    @staticmethod
    def _build_persistence(path: str):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            return FilePersistenceWithDataProtection(path)
        except Exception:
            return FilePersistence(path)

    def acquire_access_token(self) -> str:
        account = self._get_first_account()
        if account:
            silent_result = self._app.acquire_token_silent(
                scopes=list(self._settings.scopes),
                account=account,
            )
            if silent_result and "access_token" in silent_result:
                return str(silent_result["access_token"])

        if self._settings.auth_flow == "device_code":
            return self._acquire_token_device_code()

        interactive_result = self._acquire_token_interactive_compatible()
        if "access_token" in interactive_result:
            return str(interactive_result["access_token"])

        message = self._get_error_message(interactive_result)
        if self._settings.auth_flow == "interactive_then_device" or "AADSTS9002327" in message:
            try:
                return self._acquire_token_device_code()
            except AuthenticationError as device_error:
                raise AuthenticationError(
                    f"Interactive login failed: {message}\n\nDevice code fallback failed: {device_error}"
                ) from device_error

        if "AADSTS9002327" in message:
            raise AuthenticationError(self._build_spa_mismatch_error(message))

        raise AuthenticationError(f"Interactive login failed: {message}")

    def _acquire_token_device_code(self) -> str:
        flow = self._app.initiate_device_flow(scopes=list(self._settings.scopes))
        if "user_code" not in flow:
            message = self._get_error_message(flow)
            raise AuthenticationError(f"Device code initialization failed: {message}")

        print(flow.get("message", "Complete device-code sign in in your browser."))
        device_result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" in device_result:
            return str(device_result["access_token"])

        message = self._get_error_message(device_result)
        raise AuthenticationError(f"Device code login failed: {message}")

    def _acquire_token_interactive_compatible(self) -> dict[str, Any]:
        interactive_kwargs: dict[str, Any] = {
            "scopes": list(self._settings.scopes),
            "prompt": "select_account",
        }
        if self._settings.redirect_uri:
            interactive_kwargs["redirect_uri"] = self._settings.redirect_uri

        try:
            return self._app.acquire_token_interactive(**interactive_kwargs)
        except TypeError as error:
            message = str(error)
            if "redirect_uri" in message and "multiple values" in message:
                interactive_kwargs.pop("redirect_uri", None)
                return self._app.acquire_token_interactive(**interactive_kwargs)
            raise

    @staticmethod
    def _get_error_message(result: dict[str, Any] | None) -> str:
        if not result:
            return "Unknown authentication error"
        return str(result.get("error_description") or result.get("error") or "Unknown authentication error")

    def _build_spa_mismatch_error(self, original_message: str) -> str:
        return (
            "Interactive login failed due to app registration platform mismatch (AADSTS9002327). "
            "This desktop app must use a Public client (native) registration, not SPA token redemption. "
            "In Microsoft Entra app registration, add platform 'Mobile and desktop applications' with redirect URI "
            "'http://localhost' and keep using delegated scopes. Optionally set COPILOT_AUTH_FLOW=device_code "
            "as a temporary fallback.\n\n"
            f"Original error: {original_message}"
        )

    def sign_in(self) -> AuthState:
        self.acquire_access_token()
        return self.get_auth_state()

    def get_auth_state(self) -> AuthState:
        account = self._get_first_account()
        if not account:
            return AuthState(is_signed_in=False)

        tenant_id = str(account.get("tenantId") or account.get("realm") or "").strip()
        if not tenant_id:
            tenant_id = self._settings.tenant_id

        return AuthState(
            is_signed_in=True,
            username=account.get("username"),
            tenant_id=tenant_id,
        )

    def sign_out(self) -> None:
        accounts = self._app.get_accounts()
        for account in accounts:
            self._app.remove_account(account)
        self._cache._persistence.save("")

    def get_user_id(self) -> str | None:
        account = self._get_first_account()
        if not account:
            return None

        local_account_id = str(account.get("local_account_id") or "").strip()
        if local_account_id:
            return local_account_id

        home_account_id = str(account.get("home_account_id") or "").strip()
        if home_account_id and "." in home_account_id:
            return home_account_id.split(".", 1)[0].strip() or None

        return None

    def _get_first_account(self) -> dict[str, Any] | None:
        accounts = self._app.get_accounts()
        if not accounts:
            return None
        return accounts[0]
