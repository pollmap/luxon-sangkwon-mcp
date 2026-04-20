# Security Policy

## Reporting a Vulnerability

Use **GitHub Private Vulnerability Reporting** (Security tab → Report a vulnerability).

Do not file public issues for security vulnerabilities.

## Sensitive Data Notice

This MCP server queries a database derived from Korean public commercial registry data
(공공데이터포털 / 소상공인시장진흥공단). The `name` (상호명) column may contain personal
identifiers when sole proprietors register their business under their own name
(e.g. "홍길동 미용실"). Tool responses **must not** expose raw `name` values to
downstream LLM agents without aggregation or anonymization. Reviewers should verify
that any new tool added to this server does not leak such values.

## Deployment Hardening

- Run as a dedicated non-root user (`mcpserver`); see `luxon-sangkwon-mcp.service`.
- Bind to `127.0.0.1`; expose externally only behind nginx with auth + IP allowlist + UFW deny default.
- Set `DoS` upper bounds in tool inputs (radius, cell size) — already enforced server-side.
- Rotate API keys (서울 OpenAPI, etc.) quarterly.
