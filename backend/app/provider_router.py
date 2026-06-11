from typing import Dict, List, Tuple

import httpx

from .alias_resolver import AliasResolver, ResolvedModel
from .capabilities import model_capabilities
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .upstream import DEFAULT_UPSTREAM_TIMEOUT, call_openai_chat


class ProviderRouter:
    def __init__(self, config: dict):
        self.config = config
        self.resolver = AliasResolver(config)
        self.breakers: Dict[str, CircuitBreaker] = {}

    def resolve_candidates(self, incoming_model: str, force_role: str = None) -> List[ResolvedModel]:
        primary = self.resolver.resolve(incoming_model, force_role=force_role)
        model_ids = self.resolver.model_ids_for_role(primary.profile_id, primary.role)
        direct_model = next(
            (
                m
                for m in self.config.get("models", [])
                if incoming_model and incoming_model in {m.get("id"), m.get("actual_model"), m.get("litellm_model")}
            ),
            None,
        )
        if direct_model and direct_model.get("id") not in model_ids:
            model_ids = [direct_model.get("id")] + model_ids
        candidates = []
        seen = set()
        for model_id in model_ids:
            resolved = self.resolver.resolve_model_id(
                incoming_model=incoming_model,
                profile_id=primary.profile_id,
                role=primary.role,
                model_id=model_id,
            )
            key = (resolved.provider_id, resolved.actual_model)
            if key not in seen:
                seen.add(key)
                candidates.append(resolved)
        return candidates or [primary]

    async def call_openai_chat_with_failover(self, payload: dict, incoming_model: str, force_role: str = None, timeout: float = None) -> Tuple[dict, ResolvedModel, list]:
        attempts = []
        last_exc = None
        for resolved in self.resolve_candidates(incoming_model, force_role=force_role):
            breaker = self._breaker(resolved)
            if not breaker.allow_request():
                attempts.append(
                    {
                        "providerId": resolved.provider_id,
                        "model": resolved.actual_model,
                        "status": "skipped",
                        "reason": "circuit_open",
                        "circuit": breaker.snapshot(),
                    }
                )
                continue

            routed_payload = dict(payload)
            routed_payload["model"] = resolved.actual_model
            routed_payload = self._sanitize_for_resolved(routed_payload, resolved)
            try:
                response = await call_openai_chat(routed_payload, resolved, timeout=timeout if timeout is not None else DEFAULT_UPSTREAM_TIMEOUT)
                breaker.record_success()
                attempts.append(
                    {
                        "providerId": resolved.provider_id,
                        "model": resolved.actual_model,
                        "status": "success",
                        "circuit": breaker.snapshot(),
                    }
                )
                return response, resolved, attempts
            except httpx.HTTPStatusError as exc:
                breaker.record_failure()
                last_exc = exc
                error_text = exc.response.text[:500] if exc.response is not None else str(exc)
                attempts.append(
                    {
                        "providerId": resolved.provider_id,
                        "model": resolved.actual_model,
                        "status": "failed",
                        "statusCode": exc.response.status_code,
                        "error": f"{exc.__class__.__name__}: {error_text}",
                        "circuit": breaker.snapshot(),
                    }
                )
            except Exception as exc:
                breaker.record_failure()
                last_exc = exc
                attempts.append(
                    {
                        "providerId": resolved.provider_id,
                        "model": resolved.actual_model,
                        "status": "failed",
                        "error": f"{exc.__class__.__name__}: {str(exc) or repr(exc)}",
                        "circuit": breaker.snapshot(),
                    }
                )

        if last_exc:
            raise last_exc
        raise RuntimeError("No available provider candidates")

    def prepare_openai_chat_stream(self, payload: dict, incoming_model: str, force_role: str = None) -> Tuple[dict, ResolvedModel, list]:
        attempts = []
        for resolved in self.resolve_candidates(incoming_model, force_role=force_role):
            breaker = self._breaker(resolved)
            if not breaker.allow_request():
                attempts.append(
                    {
                        "providerId": resolved.provider_id,
                        "model": resolved.actual_model,
                        "status": "skipped",
                        "reason": "circuit_open",
                        "circuit": breaker.snapshot(),
                    }
                )
                continue
            routed_payload = dict(payload)
            routed_payload["model"] = resolved.actual_model
            routed_payload = self._sanitize_for_resolved(routed_payload, resolved)
            attempts.append(
                {
                    "providerId": resolved.provider_id,
                    "model": resolved.actual_model,
                    "status": "streaming",
                    "circuit": breaker.snapshot(),
                }
            )
            return routed_payload, resolved, attempts
        raise RuntimeError("No available provider candidates")

    def status(self) -> dict:
        return {key: breaker.snapshot() for key, breaker in self.breakers.items()}

    def _sanitize_for_resolved(self, payload: dict, resolved: ResolvedModel) -> dict:
        caps = model_capabilities(self.config, resolved)
        payload = self._disable_thinking_for_fast_tool(payload, resolved)
        if resolved.role == "fast_tool":
            return self._strip_reasoning_content(payload)
        if caps.get("reasoning_state") in {"reasoning_content", "mimo_reasoning_content"}:
            return payload
        return self._strip_reasoning_content(payload)

    def _disable_thinking_for_fast_tool(self, payload: dict, resolved: ResolvedModel) -> dict:
        if resolved.role != "fast_tool":
            return payload
        out = dict(payload)
        for key in [
            "reasoning",
            "reasoning_effort",
            "thinking",
            "thinking_budget",
            "enable_thinking",
            "include_reasoning",
        ]:
            out.pop(key, None)
        return out

    def _strip_reasoning_content(self, payload: dict) -> dict:
        out = dict(payload)
        messages = []
        changed = False
        for msg in out.get("messages", []):
            if isinstance(msg, dict) and "reasoning_content" in msg:
                clone = dict(msg)
                clone.pop("reasoning_content", None)
                messages.append(clone)
                changed = True
            else:
                messages.append(msg)
        if changed:
            out["messages"] = messages
        return out

    def _breaker(self, resolved: ResolvedModel) -> CircuitBreaker:
        key = f"{resolved.provider_id}:{resolved.actual_model}"
        if key not in self.breakers:
            cfg = self.config.get("runtime", {}).get("circuit_breaker", {})
            self.breakers[key] = CircuitBreaker(
                CircuitBreakerConfig(
                    failure_threshold=int(cfg.get("failure_threshold", 3)),
                    success_threshold=int(cfg.get("success_threshold", 2)),
                    timeout_seconds=int(cfg.get("timeout_seconds", 60)),
                )
            )
        return self.breakers[key]
