import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRESETS_PATH = ROOT / "config" / "provider_presets.json"


def load_provider_presets() -> list:
    if not PRESETS_PATH.exists():
        return []
    with PRESETS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
