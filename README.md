<div align="center">

# DocuMind

**Self-hostable, multi-tenant RAG.** Upload your documents, ask questions, get answers **grounded in your sources with citations** — or a plain "that isn't in your documents." Runs on a small VPS, with automatic HTTPS and your choice of AI provider.

</div>

> ⚠️ Early development — Phase 0 (scaffolding) is in place. See [ARCHITECTURE.md](ARCHITECTURE.md) and [CHANGELOG.md](CHANGELOG.md).

## Why
- **Private & self-hosted** — your documents and questions stay on your server.
- **Grounded answers, with citations** — answers come only from the project's documents; it never makes things up, and it resists prompt-injection hidden in uploads.
- **Multi-tenant** — users, projects, and documents are strictly isolated per owner.
- **Bring your own key** — OpenAI, Anthropic (Claude), Google Gemini, or Groq. Works out-of-the-box on a single free Gemini key.
- **Multilingual** — Persian and English are first-class.
- **Light** — one Postgres (relational + vectors via pgvector), no separate vector service; targets a 2 GB VPS.

## Install (one line)
```bash
curl -fsSL https://example.com/install.sh | bash
```
You'll be asked for a domain and an admin email (and optionally a free Gemini key). The installer obtains HTTPS certificates automatically (Caddy + Let's Encrypt) and brings the stack up. *(Installer ships in Phase 6.)*

## Develop
Requires Python 3.12, Node 24, and (for the full stack) Docker.
```bash
make api-install      # backend venv + deps
make web-install      # frontend deps
make lint test        # ruff/mypy/pytest + eslint/prettier/tsc
make dev              # full stack via docker compose (published ports)
```
See [CLAUDE.md](CLAUDE.md) for the developer guide and conventions.

## Architecture
FastAPI + PostgreSQL 16/pgvector + Next.js, behind Caddy. Hybrid retrieval (vector + keyword) with a grounded, cited generation step and strict per-tenant isolation. Full design in [ARCHITECTURE.md](ARCHITECTURE.md); key decisions in [docs/decisions/](docs/decisions/).

## License
[AGPL-3.0](LICENSE) © DocuMind contributors.
