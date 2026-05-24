from dataclasses import asdict, dataclass
from typing import Optional


ROLE_TO_PROFILE_KEY = {
    "main": "main_model",
    "fast_tool": "fast_tool_model",
    "large": "large_model",
    "verifier": "verifier_model",
    "vision": "vision_model",
    "fallback": "fallback_model",
}


@dataclass
class ResolvedModel:
    incoming_model: str
    alias: Optional[str]
    profile_id: str
    role: str
    provider_id: str
    provider_name: str
    provider_protocol: str
    base_url: str
    api_key: str
    actual_model: str
    litellm_model: str

    def to_safe_dict(self) -> dict:
        data = asdict(self)
        data["api_key"] = "<configured>" if self.api_key else ""
        return data


class AliasResolver:
    def __init__(self, config: dict):
        self.config = config

    def enabled_aliases(self) -> list:
        return [a for a in self.config.get("model_aliases", []) if a.get("enabled", True)]

    def resolve(self, incoming_model: str, force_role: Optional[str] = None) -> ResolvedModel:
        alias = next((a for a in self.enabled_aliases() if a["alias"] == incoming_model), None)
        profile_id = self.config.get("runtime", {}).get("default_profile", "default")
        direct_model = next(
            (
                m
                for m in self.config.get("models", [])
                if incoming_model and incoming_model in {m.get("id"), m.get("actual_model"), m.get("litellm_model")}
            ),
            None,
        )
        if direct_model and not alias:
            return self.resolve_model_id(
                incoming_model,
                profile_id,
                force_role or direct_model.get("role", "main"),
                direct_model.get("id"),
                None,
            )
        role = force_role or self._infer_role(incoming_model)
        if alias:
            profile_id = alias.get("profile_id", profile_id)
            role = force_role or alias.get("role", role)

        profile = self._find(self.config.get("profiles", []), profile_id) or self.config.get("profiles", [{}])[0]
        model_id = profile.get(ROLE_TO_PROFILE_KEY.get(role, "main_model")) or profile.get("main_model")
        return self.resolve_model_id(incoming_model, profile.get("id", profile_id), role, model_id, alias)

    def resolve_model_id(
        self,
        incoming_model: str,
        profile_id: str,
        role: str,
        model_id: str,
        alias: Optional[dict] = None,
    ) -> ResolvedModel:
        profile = self._find(self.config.get("profiles", []), profile_id) or self.config.get("profiles", [{}])[0]
        model = self._find(self.config.get("models", []), model_id)
        if not model:
            model = self._fallback_model(incoming_model, role)
        provider = self._find(self.config.get("providers", []), model.get("provider_id")) or {}
        return ResolvedModel(
            incoming_model=incoming_model,
            alias=alias.get("alias") if alias else None,
            profile_id=profile.get("id", profile_id),
            role=role,
            provider_id=provider.get("id", model.get("provider_id", "unknown")),
            provider_name=provider.get("name", provider.get("id", "Unknown")),
            provider_protocol=provider.get("protocol", "openai"),
            base_url=provider.get("base_url", ""),
            api_key=provider.get("api_key", ""),
            actual_model=model.get("actual_model", incoming_model),
            litellm_model=model.get("litellm_model", incoming_model),
        )

    def model_ids_for_role(self, profile_id: str, role: str) -> list:
        profile = self._find(self.config.get("profiles", []), profile_id) or self.config.get("profiles", [{}])[0]
        primary = profile.get(ROLE_TO_PROFILE_KEY.get(role, "main_model")) or profile.get("main_model")
        failover = profile.get("failover", {})
        role_queue = list(failover.get(role, []))
        default_queue = list(failover.get("default", []))
        out = []
        for model_id in [primary] + role_queue + default_queue:
            if model_id and model_id not in out:
                out.append(model_id)
        return out

    def models_for_anthropic(self) -> dict:
        return {
            "data": [
                {"id": a["alias"], "type": "model", "display_name": a["alias"]}
                for a in self.enabled_aliases()
                if a["alias"].startswith("claude-") or a["alias"].startswith("super-")
            ]
        }

    def models_for_openai(self) -> dict:
        seen = set()
        data = []
        for model in self.config.get("models", []):
            actual = model.get("actual_model")
            if actual and actual not in seen:
                seen.add(actual)
                data.append({"id": actual, "object": "model", "owned_by": model.get("provider_id", "superds")})
        return {"object": "list", "data": data}

    def _fallback_model(self, incoming_model: str, role: str) -> dict:
        provider = (self.config.get("providers") or [{}])[0]
        return {
            "id": "fallback_passthrough",
            "provider_id": provider.get("id", "deepseek"),
            "actual_model": incoming_model or provider.get("default_model", "deepseek-chat"),
            "litellm_model": incoming_model or provider.get("default_model", "deepseek-chat"),
            "role": role,
        }

    def _infer_role(self, model: str) -> str:
        lower = (model or "").lower()
        if "haiku" in lower:
            return "fast_tool"
        if "opus" in lower or "reason" in lower:
            return "large"
        return "main"

    def _find(self, rows: list, row_id: str) -> Optional[dict]:
        return next((r for r in rows if r.get("id") == row_id), None)
