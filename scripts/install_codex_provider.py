#!/usr/bin/env python3
import argparse
import os
from pathlib import Path


BEGIN = "# >>> superds codex provider >>>"
END = "# <<< superds codex provider <<<"


def block(args) -> str:
    websocket_line = "supports_websockets = true" if args.websockets else "supports_websockets = false"
    return f"""{BEGIN}
model = "{args.model}"
model_provider = "superds"
model_reasoning_effort = "{args.reasoning_effort}"

[model_providers.superds]
name = "SuperDS"
base_url = "{args.base_url.rstrip('/')}/openai/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
{websocket_line}
{END}
"""


def replace_block(text: str, new_block: str) -> str:
    start = text.find(BEGIN)
    end = text.find(END)
    if start != -1 and end != -1 and end > start:
        end += len(END)
        prefix = text[:start].rstrip()
        suffix = text[end:].lstrip()
        return "\n\n".join(part for part in [prefix, new_block.strip(), suffix] if part) + "\n"
    return text.rstrip() + "\n\n" + new_block


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the SuperDS Codex provider into ~/.codex/config.toml.")
    parser.add_argument("--base-url", default=os.environ.get("SUPERDS_BASE_URL", "http://127.0.0.1:8787"))
    parser.add_argument("--model", default=os.environ.get("SUPERDS_CODEX_MODEL", "super-main"))
    parser.add_argument("--reasoning-effort", default=os.environ.get("SUPERDS_CODEX_REASONING_EFFORT", "minimal"))
    parser.add_argument("--no-websockets", action="store_true", help="Force Codex to use HTTP/SSE instead of Responses WebSocket.")
    parser.add_argument("--config", default=os.environ.get("CODEX_CONFIG", str(Path.home() / ".codex" / "config.toml")))
    args = parser.parse_args()
    args.websockets = not args.no_websockets

    config_path = Path(args.config).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    config_path.write_text(replace_block(original, block(args)), encoding="utf-8")

    print(f"Installed SuperDS Codex provider in {config_path}")
    print(f"Set OPENAI_API_KEY to the SuperDS local key before running Codex.")


if __name__ == "__main__":
    main()
