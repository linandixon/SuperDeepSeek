# AGENTS.md

## Project overview

Super DeepSeek is a local AI gateway that proxies Claude Code, Codex CLI, and OpenAI-compatible clients to upstream providers (DeepSeek, Qwen, Kimi, OpenRouter, MiMo, SiliconFlow, etc.). It speaks three protocol families: Anthropic `/v1/messages`, OpenAI `/openai/v1/chat/completions`, and OpenAI Responses `/openai/v1/responses`.

## Tech stack

- Python 3.11+, FastAPI, uvicorn, httpx — no heavy frameworks
- Frontend is static JSX files served directly by FastAPI (no build step, no npm/node)
- Single config file: `config/superds.json` (live-mutated by dashboard API)
- Secrets in `.env` (gitignored), loaded by a custom `load_dotenv()` in `config_store.py`

## Commands

```bash
# Install
python3 -m pip install -r requirements.txt

# Run
python3 -m backend.app              # starts uvicorn on 127.0.0.1:8787

# Tests
python3 -m unittest discover -s tests

# Docker
docker compose up
```

There is no linter, formatter, type checker, or pre-commit hook configured. Do not assume one exists.

## Architecture

- **Entry point**: `backend/app/__main__.py` → uvicorn serves `backend.app.main:app`
- **App factory**: `backend/app/main.py:create_app()` wires ConfigStore, TraceStore, EvidenceStore, ProviderRouter
- **Config**: `backend/app/config_store.py` — loads `.env`, reads/writes `config/superds.json`, hydrates env keys into provider entries
- **Defaults**: `backend/app/defaults.py` — hardcoded config used when `superds.json` doesn't exist
- **Adapters**: `backend/app/adapters.py` — bidirectional format conversion (Anthropic ↔ OpenAI Chat ↔ Responses)
- **Alias resolver**: `backend/app/alias_resolver.py` — maps Claude-style model names (e.g. `claude-haiku-4-5`) to internal model entries via profiles and roles
- **Provider router**: `backend/app/provider_router.py` — failover routing with circuit breaker
- **Multimodal**: `backend/app/multimodal.py` — image detection, vision worker dispatch, evidence packet injection
- **Security**: `backend/app/security.py` — local API key check via `require_local_key` FastAPI dependency

## Key concepts

- **Profiles** map roles (main, fast_tool, large, verifier, vision) to model IDs. The default profile is in `config/superds.json`.
- **Model aliases** (e.g. `claude-haiku-4-5` → fast_tool role) let Claude Code clients use familiar names.
- **Vision worker**: when an image arrives for a non-vision model, a separate vision model reads the image and injects text evidence into the payload.
- **Reasoning state**: different providers return reasoning differently (`reasoning_content`, `anthropic thinking`, `mimo_reasoning_content`). The gateway preserves this across format conversions.
- **Billing header sanitizer**: strips or canonicalizes `x-anthropic-billing-header` from Claude Code system prompts before forwarding to non-Anthropic upstreams.

## Frontend

Dashboard HTML at root (`Super DeepSeek 控制台.html`) loads static JSX files from root: `api.jsx`, `app.jsx`, `components.jsx`, `data.jsx`, `pages-a.jsx`, `pages-b.jsx`, `tweaks-panel.jsx`, `styles.css`. These are registered in `STATIC_FILES` dict in `main.py`. No build tooling.

## File layout

```
backend/app/         # All server code (single flat package)
config/              # superds.json (live config), provider_presets.json
scripts/             # install_codex_provider.py (Codex CLI integration)
tests/test_core.py   # All tests in one file
*.jsx, styles.css    # Dashboard frontend (served as static files)
data/                # Runtime traces, gitignored
```

## Gotchas

- `config/superds.json` is both the default config template AND the live runtime config. The dashboard API writes to it directly. Don't treat it as read-only.
- Provider `api_key` fields in `superds.json` are empty strings in the committed version. Keys come from `.env` at runtime via `_hydrate_env_keys()`.
- The `config_store.py` has its own `load_dotenv()` — it does NOT use python-dotenv.
- Tests use `default_config()` from `defaults.py`, not the live `superds.json`. This means test assertions reference hardcoded model IDs like `deepseek_main`, `qwen_verifier`.
- No `__init__.py` exports — the package is `backend.app` with `__all__ = []`.
- The `ROOT` path in `main.py` is `Path(__file__).resolve().parents[2]` (repo root), used for serving static files.
- CORS is locked to `127.0.0.1:8787` / `localhost:8787` only.
