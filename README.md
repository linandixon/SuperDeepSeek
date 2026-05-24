# Super DeepSeek

Super DeepSeek is a local gateway for using DeepSeek and other OpenAI-compatible models with Claude Code, Codex CLI, and OpenAI-compatible clients.

It is built for one practical goal: give strong text/code models a usable agent interface, including tool calls, Responses API compatibility, and a vision-worker path for image inputs.

## Features

- Anthropic-compatible `/v1/messages` for Claude Code-style clients
- OpenAI-compatible `/openai/v1/chat/completions`
- OpenAI Responses-compatible `/openai/v1/responses`
- Responses streaming and WebSocket support for Codex CLI
- Tool-call history conversion between Responses and OpenAI Chat formats
- `reasoning_content` passthrough for models that require thinking history
- Vision worker: images are read by a configured vision model, then passed to the main model as text evidence
- Local dashboard with provider, model, profile, trace, and capability views

## Quick Start

```bash
cp .env.example .env
python3 -m pip install -r requirements.txt
python3 -m backend.app
```

Open:

```text
http://127.0.0.1:8787
```

## Configure Keys

Put upstream keys in `.env`:

```bash
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
MIMO_API_KEY=
SILICONFLOW_API_KEY=
KIMI_API_KEY=
```

The local gateway key defaults to:

```bash
SUPERDS_LOCAL_API_KEY=sk-superds-local-change-me
```

Change it before exposing the gateway outside localhost.

## Default Model Plan

The bundled `config/superds.json` keeps a ready-to-use default profile:

| Role | Default |
| --- | --- |
| Main | `deepseek-v4-pro` |
| Fast tool / vision worker | `Qwen/Qwen3.6-27B` via SiliconFlow |
| Large / long context | `deepseek-v4-pro` |
| Verifier | `kimi-k2.6` |
| Fallback | `anthropic/claude-haiku-4.5` via OpenRouter |

You can edit providers and role mappings in the dashboard.

## Claude Code

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export ANTHROPIC_API_KEY="sk-superds-local-change-me"
```

Then use Claude-like aliases such as:

- `claude-haiku-4-5`
- `claude-sonnet-4-6`
- `claude-opus-4-7`
- `super-main`
- `super-verifier`

## Codex CLI

Install the SuperDS provider into `~/.codex/config.toml`:

```bash
python3 scripts/install_codex_provider.py
export OPENAI_API_KEY="sk-superds-local-change-me"
```

Run Codex:

```bash
codex exec --model super-main "Reply with CODEX_OK"
codex review --uncommitted
```

If WebSocket mode is unstable on your machine, force HTTP/SSE:

```bash
python3 scripts/install_codex_provider.py --no-websockets
```

## OpenAI-Compatible Clients

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8787/openai/v1"
export OPENAI_API_KEY="sk-superds-local-change-me"
```

Available endpoints:

- `GET /openai/v1/models`
- `POST /openai/v1/chat/completions`
- `POST /openai/v1/responses`
- `WS /openai/v1/responses`

## Tests

```bash
python3 -m unittest discover -s tests
```

## Notes

- Runtime traces and visual evidence are stored under `data/` and are ignored by git.
- `config/superds.json` is safe to commit after replacing real provider keys with empty strings.
- If no upstream key is configured, SuperDS starts normally and returns local mock responses.
