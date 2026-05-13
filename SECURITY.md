# Security Policy

## Reporting a Vulnerability

Please do not open public issues for sensitive security reports.

Email the maintainer or open a private GitHub security advisory for the
repository. Include:

- affected version or commit
- reproduction steps
- expected impact
- any relevant logs or sample files

Do not include real API keys, signing certificates, private documents, or
customer files in reports.

## Secrets

DeckLens release signing and update publishing use local or CI secrets. Never
commit:

- `.env` files
- Apple notarization credentials
- Windows signing certificates or API tokens
- Cloudflare API tokens
- fal.ai API keys
