# Copilot APIs Test Client

Modular Python desktop client for Microsoft 365 Copilot APIs.

## About

This repository provides a non-official test client for evaluating Microsoft 365 Copilot APIs in development and lab scenarios.

- Distribution status: provided **as-is**
- Intended use: testing, prototyping, and learning
- Not intended for: enterprise production workloads
- Endorsement: this project is **not endorsed by Microsoft**

API behavior, permissions, and endpoint references were sourced from Microsoft Learn documentation:

- Chat API overview: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/chat/overview
- Search API overview: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/search/overview
- Retrieval API overview: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/retrieval/overview
- AI interaction history resource: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/interaction-export/resources/aiinteractionhistory?pivots=graph-v1
- AI interaction export method: https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/interaction-export/aiinteractionhistory-getallenterpriseinteractions?pivots=graph-v1

![Copilot API Test Client](https://raw.githubusercontent.com/davideldersveld/Copilot-APIs-Test-Client/refs/heads/main/Copilot%20Chat%20API%20Test%20Client.png)

## Scope (initial)

- Chat API
- Search API
- Retrieval API

The app uses:

- `CustomTkinter` for desktop UI
- `MSAL` + `msal-extensions` for sign-in and token cache
- `requests` for HTTP calls

## Important API notes

- The Microsoft 365 Copilot Chat/Search/Retrieval APIs are preview/beta and subject to change.
- Search and Chat require Microsoft 365 Copilot licensing.
- Retrieval can have additional licensing/pay-as-you-go options depending on tenant setup.
- Endpoint paths in this project are configurable and should be verified against the latest API references.

## New capabilities

- Search pagination support via `@odata.nextLink` in the Search tab.
- Graph batch support (`POST /$batch`) in the Batch tab for Chat, Search, and Retrieval operations.

## Project layout

- `app.py` desktop entrypoint
- `copilot_client/config.py` environment-based settings + validation
- `copilot_client/auth.py` interactive Microsoft Entra auth manager
- `copilot_client/http.py` shared HTTP client with retries/timeouts
- `copilot_client/apis/` Chat/Search/Retrieval wrappers
- `copilot_client/services.py` orchestrates auth + API calls
- `copilot_client/ui/main_window.py` CustomTkinter UI
- `.env.example` environment template

## Prerequisites

1. Python 3.10+
2. Microsoft Entra app registration (single-tenant)
3. Public client enabled for interactive sign-in
4. Delegated permissions required by API:
  - **Chat API**: `Sites.Read.All`, `Mail.Read`, `People.Read.All`, `OnlineMeetingTranscript.Read.All`, `Chat.Read`, `ChannelMessage.Read.All`, `ExternalItem.Read.All`
  - **Search API**: `Files.Read.All`, `Sites.Read.All` (or higher privilege `Files.ReadWrite.All`, `Sites.ReadWrite.All`)
  - **Retrieval API**:
    - SharePoint/OneDrive: `Files.Read.All` and `Sites.Read.All`
    - Copilot connectors: `ExternalItem.Read.All`
  - **AI Interactions Export API** (`getAllEnterpriseInteractions`) does **not** support delegated permissions.
    - Required model: **Application** permission `AiEnterpriseInteraction.Read.All` with admin consent.
    - Result: no additional delegated permission can fix `Requested API is not supported in delegated context`.
5. Admin/user consent per your tenant policy

## Configure

1. Copy `.env.example` to `.env`.
2. Fill in tenant/app values and scopes.
3. Confirm API paths against latest docs and adjust if needed.
4. Optional auth settings:
  - `COPILOT_AUTH_FLOW=interactive_then_device` (default)
  - `COPILOT_AUTH_FLOW=interactive`
  - `COPILOT_AUTH_FLOW=device_code`
  - `COPILOT_REDIRECT_URI=http://localhost`
  - `COPILOT_TIMEZONE=Etc/UTC` (IANA timezone; example: `America/New_York`)
  - `COPILOT_BATCH_PATH=/$batch`

PowerShell example:

```powershell
Copy-Item .env.example .env
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $name, $value = $_ -split '=', 2
  [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
}
```

## Run locally

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Batch usage

- Open the **Batch** tab.
- Provide one or more operations:
  - Chat prompt (optional)
  - Search query (optional)
  - Retrieval query + data source (both required if retrieval is used)
- Select **Run Graph Batch**.

## Packaging to Windows executable

### One-file

```powershell
pyinstaller --clean --noconfirm --onefile --windowed --name CopilotApiClient app.py
```

### One-dir

```powershell
pyinstaller --clean --noconfirm --onedir --windowed --name CopilotApiClient app.py
```

### Runtime config for EXE

- Put a `.env` file in the same folder as `CopilotApiClient.exe`.
- The app now auto-loads `.env` from:
  1. `COPILOT_ENV_FILE` (if set, absolute or relative path)
  2. Current working directory
  3. Executable directory (when running as packaged EXE)
- You can explicitly set a config path before launching:

```powershell
$env:COPILOT_ENV_FILE = "C:\path\to\.env"
.\CopilotApiClient.exe
```

## Security guidance

- Do not hardcode secrets, tenant IDs, or tokens in source files.
- Keep `.env` out of source control.
- Tokens are cached locally for silent re-auth; protect user profile and endpoint devices.
- Validate user-facing outputs from AI responses before operational use.

## Legal and Policy

- Disclaimer and non-endorsement terms: `DISCLAIMER.md`
- Privacy policy: `PRIVACY.md`
- Security reporting policy: `SECURITY.md`

## Troubleshooting: AADSTS9002327

If you see:

`AADSTS9002327: Tokens issued for the 'Single-Page Application' client-type may only be redeemed via cross-origin requests`

your Entra app registration is configured as SPA for a desktop auth flow.

Fix in Microsoft Entra app registration:

1. Go to **Authentication** for your app.
2. Add platform: **Mobile and desktop applications**.
3. Add redirect URI: `http://localhost`.
4. Keep delegated API permissions and grant consent per tenant policy.

Workaround in this app:

- Set `COPILOT_AUTH_FLOW=device_code` in `.env`.
- The client now supports automatic fallback from interactive login to device code when possible.

## Troubleshooting: HTTP 412 `Requested API is not supported in delegated context`

If this occurs in the **AI Interactions** tab:

- This is expected when using delegated user sign-in (MSAL public client).
- The `getAllEnterpriseInteractions` endpoint only supports application context (`AiEnterpriseInteraction.Read.All`).
- There are **no additional delegated API permissions** to add for this endpoint.
