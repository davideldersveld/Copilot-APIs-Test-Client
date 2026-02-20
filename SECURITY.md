# Security Policy

## Supported Use

This project is intended for non-production testing and evaluation.

## Reporting a Vulnerability

If you discover a security issue in this repository:

1. Do not publish sensitive exploit details publicly.
2. Share a private report with maintainers through your preferred private channel.
3. Include reproduction steps, impacted files, and severity assessment.

## Secrets and Credentials

- Never commit secrets, client secrets, or tokens.
- Keep `.env` excluded from version control.
- Rotate credentials if compromise is suspected.

## Secure Configuration Baseline

- Use least-privilege API permissions.
- Restrict app registration access.
- Apply admin consent policies carefully.
- Keep dependencies up to date.
