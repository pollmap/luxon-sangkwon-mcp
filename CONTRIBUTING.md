# Contributing

Thanks for considering a contribution.

## Development Setup

1. `cp .env.template .env` and fill in API keys (서울 OpenAPI etc.).
2. `python -m pip install -r requirements.txt`
3. Build the local DB: `python scripts/build_db.py --test` (synthetic) or `--real` if you have the upstream parquet.
4. Run: `python server.py --transport stdio`

## Code Style

- Python: black + ruff. Type hints on public functions.
- Web: TypeScript strict, Next.js 16 App Router.
- Keep tool input bounds tight (radius_m, cell_size_m, limit) — DoS protection.

## Pull Requests

- Small, focused commits.
- Conventional commits (`fix(scope): ...`).
- New MCP tool? Add input validation, document it in `README.md`, and verify it never returns `name` (상호명) field — see `SECURITY.md`.

## Reporting Vulnerabilities

See `SECURITY.md`. Use GitHub Private Vulnerability Reporting.
