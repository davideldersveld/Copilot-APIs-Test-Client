# Privacy Policy

## Scope

This privacy policy applies to this repository and local runs of the application.

## Data Processed by the App

The app can process:

- User prompts entered in the UI
- API responses from Microsoft Graph / Copilot APIs
- Configuration values from environment variables or `.env`
- Authentication tokens cached locally by MSAL

## Data Storage

By default, the app stores tokens locally (for silent sign-in) using MSAL cache persistence. The cache location is configurable.

The app does not include built-in telemetry export, analytics pipelines, or remote logging destinations.

## Data Sharing

The app sends requests to Microsoft endpoints that you configure (for example, `graph.microsoft.com`).

No additional third-party data-sharing behavior is intentionally implemented by this project.

## Security Notes

- Keep `.env` files and credentials private.
- Do not commit secrets to source control.
- Use least-privilege permissions.
- Review and rotate credentials regularly.

## Enterprise Use

For enterprises, conduct your own legal, privacy, compliance, and security review before use.
