import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from .defaults import default_config


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "superds.json"


def load_dotenv(path: Optional[Path] = None) -> None:
    env_path = path or ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class ConfigStore:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        load_dotenv()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = default_config()
            self.save(config)
        self._hydrate_env_keys(config)
        return config

    def _hydrate_env_keys(self, config: dict) -> None:
        for provider in config.get("providers", []):
            env_name = provider.get("api_key_env")
            if env_name and os.getenv(env_name):
                provider["api_key"] = os.getenv(env_name, "")

    def get(self) -> dict:
        return deepcopy(self._config)

    def save(self, config: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        safe = deepcopy(config)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(safe, f, ensure_ascii=False, indent=2)
        self._config = safe
        return self.get()

    def update(self, patch: dict) -> dict:
        config = self.get()
        for key, value in patch.items():
            config[key] = value
        return self.save(config)
