import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .adapters import (
    anthropic_payload,
    anthropic_to_openai_payload,
    openai_payload,
    openai_to_anthropic_response,
    responses_tools_to_openai,
    rough_count_tokens,
)
from .alias_resolver import AliasResolver
from .capabilities import all_model_capabilities, model_capabilities
from .config_store import ConfigStore
from .evidence_store import EvidenceStore
from .multimodal import (
    detect_images,
    evidence_system_message,
    inject_evidence_into_chat_payload,
    latest_user_text,
    make_evidence_packets,
    references_previous_image,
    responses_input_to_messages,
    vision_request_content,
)
from .provider_presets import load_provider_presets
from .provider_router import ProviderRouter
from .reasoning_state import extract_opaque_reasoning, validate_mimo_reasoning_history
from .secret_redaction import redact
from .security import configured_key, require_local_key, token_from_headers
from .trace_store import TraceStore
from .upstream import call_anthropic_messages, call_openai_chat, iter_openai_chat_stream, test_connection


ROOT = Path(__file__).resolve().parents[2]
VISION_CHECK_IMAGE_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
RESPONSES_TO_CHAT_PASSTHROUGH = {
    "max_tokens",
    "max_completion_tokens",
    "temperature",
    "top_p",
    "reasoning",
    "reasoning_effort",
    "thinking",
    "thinking_budget",
    "enable_thinking",
    "include_reasoning",
    "response_format",
    "seed",
    "presence_penalty",
    "frequency_penalty",
    "logprobs",
    "top_logprobs",
    "parallel_tool_calls",
    "tool_choice",
    "service_tier",
    "metadata",
    "extra_body",
}
STATIC_FILES = {
    "/styles.css": "styles.css",
    "/api.jsx": "api.jsx",
    "/tweaks-panel.jsx": "tweaks-panel.jsx",
    "/data.jsx": "data.jsx",
    "/components.jsx": "components.jsx",
    "/pages-a.jsx": "pages-a.jsx",
    "/pages-b.jsx": "pages-b.jsx",
    "/app.jsx": "app.jsx",
}


def create_app() -> FastAPI:
    app = FastAPI(title="Super DeepSeek", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8787", "http://localhost:8787"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.config_store = ConfigStore()
    initial_config = app.state.config_store.get()
    if ensure_provider_default_models(initial_config):
        initial_config = app.state.config_store.save(initial_config)
    app.state.trace_store = TraceStore()
    app.state.evidence_store = EvidenceStore(retention_days=int(initial_config.get("runtime", {}).get("evidence_retention_days", 14)))
    app.state.responses_cache = {}
    app.state.responses_call_reasoning = {}
    app.state.provider_router = ProviderRouter(initial_config)
    install_routes(app)
    return app


def cfg(request: Request) -> dict:
    return request.app.state.config_store.get()


def normalize_provider_payload(body: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    existing = existing or {}
    api_key = body.get("api_key") or body.get("apiKey")
    if isinstance(api_key, str) and (api_key.startswith("sk-****") or api_key == "<redacted>"):
        api_key = existing.get("api_key", "")
    default_model = body.get("default_model") or body.get("defaultModel") or existing.get("default_model", "")
    provider_id = body.get("id") or existing.get("id") or body.get("name", "custom").lower().replace(" ", "-")
    base_url = body.get("base_url") or body.get("baseUrl") or existing.get("base_url", "")
    default_model = canonical_provider_model(provider_id, base_url, default_model)
    models = normalize_provider_models(body.get("models", body.get("model_list", body.get("modelList"))), default_model, existing)
    models = [canonical_provider_model(provider_id, base_url, model) for model in models]
    models = list(dict.fromkeys([model for model in models if model]))
    if not default_model and models:
        default_model = models[0]
    return {
        **existing,
        "id": provider_id,
        "name": body.get("name") or existing.get("name") or "Custom Provider",
        "protocol": body.get("protocol") or existing.get("protocol") or "openai",
        "base_url": base_url,
        "api_key_env": body.get("api_key_env") or body.get("apiKeyEnv") or existing.get("api_key_env", ""),
        "api_key": api_key if api_key is not None else existing.get("api_key", ""),
        "default_model": default_model,
        "models": models,
    }


def canonical_provider_model(provider_id: str, base_url: str, model: str) -> str:
    model = str(model or "").strip()
    if not model:
        return ""
    is_deepinfra = provider_id == "deepinfra" or "api.deepinfra.com" in (base_url or "")
    if is_deepinfra and model.startswith("gpt-oss-"):
        return f"openai/{model}"
    return model


def normalize_provider_models(raw: Any, default_model: str = "", existing: Optional[Dict[str, Any]] = None) -> list:
    existing = existing or {}
    if raw is None:
        raw = existing.get("models")
    if raw is None:
        raw = [default_model] if default_model else []
    if isinstance(raw, str):
        raw = re.split(r"[\n,]+", raw)
    out = []
    seen = set()
    for item in raw or []:
        model = item.get("id") if isinstance(item, dict) else item
        model = str(model or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        out.append(model)
    if default_model and default_model not in seen:
        out.insert(0, default_model)
    return out


def provider_model_names(provider: Dict[str, Any]) -> list:
    return normalize_provider_models(provider.get("models"), provider.get("default_model", ""))


def model_id_for_provider_model(provider: Dict[str, Any], model_name: str) -> str:
    raw = f"{provider.get('id', 'provider')}_{model_name or 'model'}"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
    return slug or "provider_model"


def litellm_model_for_provider(provider: Dict[str, Any], model: str = "") -> str:
    model = model or provider.get("default_model", "")
    if provider.get("protocol") == "openai":
        return f"openai/{model}" if model and "/" not in model.split(":", 1)[0] else model
    return model


def ensure_provider_default_models(config: Dict[str, Any]) -> bool:
    changed = False
    for provider in config.get("providers", []):
        provider_id = provider.get("id")
        provider_models = provider_model_names(provider)
        if provider_models != provider.get("models", []):
            provider["models"] = provider_models
            changed = True
        if not provider_id or not provider_models:
            continue
        changed = sync_provider_models(config, provider) or changed
    return changed


def sync_provider_models(config: Dict[str, Any], provider: Dict[str, Any]) -> bool:
    changed = False
    models = config.setdefault("models", [])
    provider_id = provider.get("id")
    managed_sources = {"provider_default", "provider_model"}
    desired = provider_model_names(provider)
    desired_set = set(desired)
    existing_by_actual = {
        m.get("actual_model"): m
        for m in models
        if m.get("provider_id") == provider_id and m.get("source") in managed_sources
    }

    before = len(models)
    models[:] = [
        m
        for m in models
        if not (
            m.get("provider_id") == provider_id
            and m.get("source") in managed_sources
            and m.get("actual_model") not in desired_set
        )
    ]
    changed = changed or len(models) != before

    existing_pairs = {(m.get("provider_id"), m.get("actual_model")) for m in models}
    existing_ids = {m.get("id") for m in models}
    for model_name in desired:
        if (provider_id, model_name) in existing_pairs:
            existing = existing_by_actual.get(model_name)
            if existing:
                litellm_model = litellm_model_for_provider(provider, model_name)
                if existing.get("litellm_model") != litellm_model:
                    existing["litellm_model"] = litellm_model
                    changed = True
            continue
        model_id = model_id_for_provider_model(provider, model_name)
        suffix = 2
        while model_id in existing_ids:
            model_id = f"{model_id}_{suffix}"
            suffix += 1
        caps = dict(provider.get("capabilities", {}))
        caps.setdefault("api_format", "anthropic_messages" if provider.get("protocol") == "anthropic" else "openai_chat")
        models.append(
            {
                "id": model_id,
                "provider_id": provider_id,
                "litellm_model": litellm_model_for_provider(provider, model_name),
                "actual_model": model_name,
                "role": "main",
                "capabilities": caps,
                "source": "provider_model",
            }
        )
        existing_pairs.add((provider_id, model_name))
        existing_ids.add(model_id)
        changed = True
    return changed


def remove_provider_from_config(config: Dict[str, Any], provider_id: str) -> bool:
    providers = config.get("providers", [])
    if not any(p.get("id") == provider_id for p in providers):
        return False

    removed_model_ids = {
        m.get("id")
        for m in config.get("models", [])
        if m.get("provider_id") == provider_id and m.get("id")
    }
    config["providers"] = [p for p in providers if p.get("id") != provider_id]
    config["models"] = [m for m in config.get("models", []) if m.get("provider_id") != provider_id]

    remaining_model_ids = [m.get("id") for m in config.get("models", []) if m.get("id")]
    fallback_model_id = remaining_model_ids[0] if remaining_model_ids else ""
    profile_model_keys = [
        "main_model",
        "fast_tool_model",
        "large_model",
        "verifier_model",
        "vision_model",
        "fallback_model",
    ]
    for profile in config.get("profiles", []):
        for key in profile_model_keys:
            if profile.get(key) in removed_model_ids:
                profile[key] = fallback_model_id
        failover = profile.get("failover")
        if isinstance(failover, dict):
            for key, model_ids in list(failover.items()):
                if isinstance(model_ids, list):
                    failover[key] = [mid for mid in model_ids if mid not in removed_model_ids]
    return True


PROFILE_MODEL_KEYS = {
    "main": "main_model",
    "fast_tool": "fast_tool_model",
    "large": "large_model",
    "verifier": "verifier_model",
    "vision": "vision_model",
    "fallback": "fallback_model",
}


def normalize_alias_payload(body: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    existing = existing or {}
    alias = body.get("alias") or existing.get("alias", "")
    profile_id = body.get("profile_id") or body.get("profileId") or body.get("targetProfile") or existing.get("profile_id", "default")
    role = body.get("role") or existing.get("role", "main")
    return {
        **existing,
        "alias": alias,
        "profile_id": profile_id,
        "role": role,
        "enabled": body.get("enabled") if isinstance(body.get("enabled"), bool) else existing.get("enabled", True),
        "notes": body.get("notes") or existing.get("notes", ""),
    }


def alias_response(alias: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    profile_id = alias.get("profile_id", "default")
    role = alias.get("role", "main")
    profile = profile_for_id(config, profile_id)
    model_id = profile.get(PROFILE_MODEL_KEYS.get(role, "main_model")) or profile.get("main_model")
    model = next((m for m in config.get("models", []) if m.get("id") == model_id), {})
    return {
        "id": alias.get("alias"),
        "alias": alias.get("alias", ""),
        "role": role,
        "profile_id": profile_id,
        "targetProfile": profile_id,
        "target_model_id": model_id or "",
        "targetModel": model.get("actual_model", model_id or ""),
        "enabled": alias.get("enabled", True),
        "notes": alias.get("notes", ""),
    }


def normalize_profile_payload(body: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    existing = existing or {}
    profile_id = body.get("id") or body.get("name", "profile").lower().replace(" ", "-")
    profile = {
        **existing,
        "id": profile_id,
        "name": body.get("name") or existing.get("name") or profile_id,
        "failover": body.get("failover") if isinstance(body.get("failover"), dict) else existing.get("failover", {}),
    }
    for role, key in PROFILE_MODEL_KEYS.items():
        value = body.get(key)
        if value is None and isinstance(body.get("roles"), dict):
            value = body["roles"].get(role)
        if value is not None:
            profile[key] = value
        elif key in existing:
            profile[key] = existing[key]
    return profile


def profile_for_id(config: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
    return next((p for p in config.get("profiles", []) if p.get("id") == profile_id), config.get("profiles", [{}])[0])


def vision_model_id(config: Dict[str, Any], profile_id: str) -> str:
    profile = profile_for_id(config, profile_id)
    return profile.get("vision_model") or ""


def resolve_for_request(request: Request, incoming_model: str, protocol: str, body: Dict[str, Any]):
    return resolver(request).resolve(incoming_model)


def update_model_vision_status(config: Dict[str, Any], model_id: str, status: str) -> None:
    for model in config.get("models", []):
        if model.get("id") == model_id:
            caps = model.setdefault("capabilities", {})
            caps["vision_status"] = status
            if status == "verified_supported":
                caps["vision"] = True
            elif status == "verified_unsupported":
                caps["vision"] = False
            caps["vision_checked_at"] = int(time.time())
            return


def resolver(request: Request) -> AliasResolver:
    return AliasResolver(cfg(request))


def provider_router(request: Request) -> ProviderRouter:
    return request.app.state.provider_router


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def step(name: str, type_: str, status: str = "success", summary: str = "") -> dict:
    return {"id": "st_" + uuid.uuid4().hex[:8], "name": name, "type": type_, "startedAt": now_iso(), "endedAt": now_iso(), "status": status, "summary": summary}


def save_trace(request: Request, record: Dict[str, Any]) -> None:
    request.app.state.trace_store.put(redact(record))


def text_from_openai(resp: dict) -> str:
    choice = (resp.get("choices") or [{}])[0]
    return ((choice.get("message") or {}).get("content")) or ""


def tool_calls_from_openai(resp: dict) -> list:
    choice = (resp.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return message.get("tool_calls") or []


def openai_stream_delta(data: str) -> tuple[str, Optional[str]]:
    if data == "[DONE]":
        return "", "stop"
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return "", None
    choice = (chunk.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    return delta.get("content") or "", choice.get("finish_reason")


def openai_stream_parts(data: str) -> tuple[str, list, str, Optional[str]]:
    if data == "[DONE]":
        return "", [], "", "stop"
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return "", [], "", None
    choice = (chunk.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    return delta.get("content") or "", delta.get("tool_calls") or [], delta.get("reasoning_content") or "", choice.get("finish_reason")


def response_from_stream_text(text: str, request_model: str) -> dict:
    return {
        "id": "msg_" + uuid.uuid4().hex[:12],
        "type": "message",
        "role": "assistant",
        "model": request_model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "stop",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def response_output_from_openai(openai_response: dict, text: str) -> list:
    output = []
    if text:
        output.append(
            {
                "id": "msg_" + uuid.uuid4().hex[:12],
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        )
    for call in tool_calls_from_openai(openai_response):
        function = call.get("function") or {}
        output.append(
            {
                "id": call.get("id") or "fc_" + uuid.uuid4().hex[:12],
                "type": "function_call",
                "status": "completed",
                "call_id": call.get("id") or "call_" + uuid.uuid4().hex[:12],
                "name": function.get("name", ""),
                "arguments": function.get("arguments", ""),
            }
        )
    if not output:
        output.append(
            {
                "id": "msg_" + uuid.uuid4().hex[:12],
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "", "annotations": []}],
            }
        )
    return output


def reasoning_from_openai(openai_response: dict) -> str:
    choice = (openai_response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return message.get("reasoning_content") or ""


def cache_responses_state(request: Request, response: dict) -> None:
    cache = getattr(request.app.state, "responses_cache", None)
    call_cache = getattr(request.app.state, "responses_call_reasoning", None)
    if cache is None or call_cache is None or not response.get("id"):
        return
    cache[response["id"]] = response
    while len(cache) > 100:
        cache.pop(next(iter(cache)))
    reasoning = response.get("_superds_reasoning_content") or ""
    for item in response.get("output", []):
        if item.get("type") == "function_call" and item.get("call_id") and reasoning:
            call_cache[item["call_id"]] = reasoning
    while len(call_cache) > 500:
        call_cache.pop(next(iter(call_cache)))


def responses_body_with_cached_context(request: Request, body: dict) -> dict:
    cache = getattr(request.app.state, "responses_cache", {})
    call_cache = getattr(request.app.state, "responses_call_reasoning", {})
    previous = cache.get(body.get("previous_response_id"))
    original_input = body.get("input")
    merged_input = []
    if previous:
        for item in previous.get("output", []):
            clone = dict(item)
            reasoning = previous.get("_superds_reasoning_content")
            if reasoning and clone.get("type") == "function_call":
                clone["_superds_reasoning_content"] = reasoning
            merged_input.append(clone)
    if isinstance(original_input, list):
        merged_input.extend(original_input)
    elif original_input is not None:
        merged_input.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": str(original_input)}]})
    for item in merged_input:
        if isinstance(item, dict) and item.get("type") == "function_call" and not item.get("_superds_reasoning_content"):
            reasoning = call_cache.get(item.get("call_id"))
            if reasoning:
                item["_superds_reasoning_content"] = reasoning
    return {**body, "input": merged_input}


def usage_from_openai(resp: dict) -> dict:
    usage = resp.get("usage") or {}
    return {
        "inputTokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
        "outputTokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
        "totalTokens": usage.get("total_tokens", 0),
        "estimatedCostUsd": 0,
    }


def usage_from_anthropic(resp: dict) -> dict:
    usage = resp.get("usage") or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": usage.get("total_tokens", input_tokens + output_tokens),
        "estimatedCostUsd": 0,
    }


async def check_vision_model(config: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    model = next((m for m in config.get("models", []) if m.get("id") == model_id), None)
    if not model:
        raise HTTPException(status_code=404, detail="model_not_found")
    resolved = AliasResolver(config).resolve_model_id(
        incoming_model=model.get("actual_model", model_id),
        profile_id=config.get("runtime", {}).get("default_profile", "default"),
        role="vision",
        model_id=model_id,
    )
    if not resolved.api_key:
        return {"ok": False, "vision_status": "unknown", "status": "missing_api_key", "model_id": model_id, "model": resolved.actual_model}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if resolved.provider_protocol == "anthropic":
                payload = {
                    "model": resolved.actual_model,
                    "max_tokens": 8,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "请只回复 VISION_OK。"},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": VISION_CHECK_IMAGE_B64}},
                            ],
                        }
                    ],
                }
                response = await client.post(
                    resolved.base_url.rstrip("/") + "/messages",
                    json=payload,
                    headers={"x-api-key": resolved.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                )
            else:
                payload = {
                    "model": resolved.actual_model,
                    "max_tokens": 8,
                    "stream": False,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "请只回复 VISION_OK。"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{VISION_CHECK_IMAGE_B64}"}},
                            ],
                        }
                    ],
                }
                response = await client.post(
                    resolved.base_url.rstrip("/") + "/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {resolved.api_key}", "Content-Type": "application/json"},
                )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if 200 <= response.status_code < 300:
            return {"ok": True, "vision_status": "verified_supported", "status": response.status_code, "latency_ms": latency_ms, "model_id": model_id, "model": resolved.actual_model}
        if response.status_code in {400, 415, 422}:
            return {"ok": False, "vision_status": "verified_unsupported", "status": response.status_code, "latency_ms": latency_ms, "model_id": model_id, "model": resolved.actual_model, "error": response.text[:500]}
        return {"ok": False, "vision_status": "unknown", "status": response.status_code, "latency_ms": latency_ms, "model_id": model_id, "model": resolved.actual_model, "error": response.text[:500]}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "vision_status": "unknown", "status": exc.response.status_code, "model_id": model_id, "model": resolved.actual_model, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "vision_status": "unknown", "status": exc.__class__.__name__, "model_id": model_id, "model": resolved.actual_model, "error": str(exc)}


def session_key(request: Request, body: dict) -> str:
    metadata = body.get("metadata") if isinstance(body, dict) else None
    if isinstance(metadata, dict):
        # Claude Code 的 user_id 内嵌 session uuid，可避免同机多会话共享证据缓存
        for key in ("session_id", "user_id"):
            if metadata.get(key):
                return str(metadata[key])[:200]
    return request.headers.get("x-superds-session-id") or request.headers.get("user-agent", "default")[:120] or "default"


async def run_vision_worker(request: Request, images: list, user_text: str, incoming_model: str):
    worker_cfg = cfg(request).get("runtime", {}).get("vision_worker", {})
    vision_payload = {
        "model": "vision",
        "messages": [{"role": "user", "content": vision_request_content(images, user_text, worker_cfg.get("prompt", ""))}],
        "stream": False,
        "max_tokens": int(worker_cfg.get("max_tokens", 2048)),
        "temperature": 0,
        "enable_thinking": False,
    }
    timeout = float(worker_cfg.get("timeout_seconds", 90))
    upstream, resolved, route_attempts = await provider_router(request).call_openai_chat_with_failover(vision_payload, incoming_model, force_role="vision", timeout=timeout)
    return text_from_openai(upstream), resolved, route_attempts


async def prepare_multimodal_context(request: Request, protocol: str, body: dict, payload: dict, resolved, steps: list):
    config = cfg(request)
    caps = model_capabilities(config, resolved)
    images = detect_images(protocol, body)
    evidence_packets = []
    historical_evidence = []
    forced_role = None
    key = session_key(request, body)
    cached_packets = []
    new_images = []
    worker_info = {"provider_id": None, "model": None, "route_attempts": [], "observation_chars": 0, "failed_images": 0}

    if images and caps.get("vision"):
        steps.append(step("Image Capability", "route", summary=f"{resolved.actual_model} accepts image input"))
    elif images:
        image_policy = config.get("runtime", {}).get("image_policy", "ocr")
        if image_policy == "reject":
            raise HTTPException(status_code=422, detail={"error": "model_does_not_support_images", "model": resolved.actual_model})
        if image_policy == "route":
            forced_role = "vision"
            steps.append(step("Image Router", "route", summary="Image detected; routing to vision role"))
        else:
            # ---- 按图片内容 hash 查缓存，避免重复调用视觉模型 ----
            image_hashes = [img.get("hash") for img in images]
            cached_map = request.app.state.evidence_store.get_by_hashes(key, image_hashes)
            new_images = [img for img in images if img.get("hash") not in cached_map]
            # 按原始顺序收集缓存命中的 evidence packets，保证注入文本稳定
            cached_packets = [cached_map[h] for h in image_hashes if h in cached_map]
            new_packets = []

            if new_images and vision_model_id(config, resolved.profile_id):
                user_text = latest_user_text(protocol, body)
                results = await asyncio.gather(
                    *[run_vision_worker(request, [img], user_text, resolved.incoming_model) for img in new_images],
                    return_exceptions=True,
                )
                cacheable = []
                for img, result in zip(new_images, results):
                    if isinstance(result, BaseException):
                        worker_info["failed_images"] += 1
                        packet = make_evidence_packets([img], key, note=f"vision_worker_error:{result.__class__.__name__}")[0]
                        packet["content"]["summary"] = "视觉副手暂时不可用，本次未能读取该图片。"
                        packet["uncertainties"] = ["视觉副手调用失败，不要猜测图片细节，可建议用户稍后重试。"]
                        new_packets.append(packet)
                        continue
                    observation_text, vision_resolved, vision_attempts = result
                    worker_info["provider_id"] = vision_resolved.provider_id
                    worker_info["model"] = vision_resolved.actual_model
                    worker_info["route_attempts"].extend(vision_attempts)
                    worker_info["observation_chars"] += len(observation_text)
                    packet = make_evidence_packets([img], key, note=f"vision_worker:{vision_resolved.provider_id}/{vision_resolved.actual_model}", observation_text=observation_text)[0]
                    if observation_text.strip():
                        # 只缓存真实观察结果，失败/空结果下次重试，避免污染缓存
                        cacheable.append(packet)
                    else:
                        worker_info["failed_images"] += 1
                    new_packets.append(packet)
                if cacheable:
                    request.app.state.evidence_store.put_many(cacheable)
                ok_count = len(new_images) - worker_info["failed_images"]
                status = "success" if ok_count else "error"
                steps.append(step("Vision Worker", "worker", status=status, summary=f"{worker_info['provider_id'] or 'vision'} / {worker_info['model'] or '?'} produced evidence for {ok_count}/{len(new_images)} new image(s), {len(cached_packets)} cached"))
            elif new_images:
                new_packets = make_evidence_packets(new_images, key)
                steps.append(step("Vision Evidence", "worker", summary=f"{len(new_packets)} image(s) converted to placeholder evidence (no vision model configured)"))
            else:
                steps.append(step("Vision Cache Hit", "worker", summary=f"All {len(cached_packets)} image(s) resolved from evidence cache, vision worker skipped"))

            evidence_packets = cached_packets + new_packets
            payload = inject_evidence_into_chat_payload(payload, evidence_system_message(evidence_packets))

    if not images and references_previous_image(latest_user_text(protocol, body)):
        historical_evidence = request.app.state.evidence_store.recent(key, limit=3)
        if historical_evidence:
            evidence_text = evidence_system_message([], historical_evidence)
            payload = inject_evidence_into_chat_payload(payload, evidence_text)
            steps.append(step("Historical Vision Context", "worker", summary=f"Injected {len(historical_evidence)} previous evidence packet(s)"))

    return payload, forced_role, {
        "images": [{"hash": img.get("hash"), "source_ref": img.get("source_ref")} for img in images],
        "evidence_packets": evidence_packets,
        "historical_evidence": historical_evidence,
        "capabilities": caps,
        "vision_worker": worker_info,
        "vision_cache": {
            "cached_count": len(cached_packets),
            "new_count": len(new_images),
            "skipped_worker": bool(images) and not new_images and bool(cached_packets),
        },
    }



class ConnectionRequest:
    def __init__(self, app, headers: dict):
        self.app = app
        self.headers = headers


def websocket_is_authorized(websocket: WebSocket) -> bool:
    expected = configured_key(websocket.app.state.config_store.get())
    if not expected:
        return True
    token = token_from_headers(websocket.headers)
    if not token and websocket.query_params.get("api_key"):
        token = websocket.query_params.get("api_key", "").strip()
    return token == expected


def sse_frame_data(frame: str) -> Optional[dict]:
    data_lines = [line[5:].strip() for line in frame.splitlines() if line.startswith("data:")]
    if not data_lines:
        return None
    raw = "\n".join(data_lines)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def install_routes(app: FastAPI) -> None:
    @app.get("/")
    async def index():
        return FileResponse(ROOT / "Super DeepSeek 控制台.html")

    @app.get("/{asset_name}")
    async def static_asset(asset_name: str):
        path = "/" + asset_name
        if path not in STATIC_FILES:
            raise HTTPException(status_code=404, detail="not_found")
        return FileResponse(ROOT / STATIC_FILES[path])

    @app.get("/api/health")
    async def health(request: Request):
        config = cfg(request)
        aliases = AliasResolver(config).enabled_aliases()
        return {
            "ok": True,
            "service": "super-deepseek",
            "version": "0.1.0",
            "time": now_iso(),
            "mode": config.get("runtime", {}).get("mode", "observe"),
            "local_base_url": config.get("server", {}).get("public_base_url", "http://127.0.0.1:8787"),
            "aliases": len(aliases),
            "haiku_alias_enabled": any("haiku" in a["alias"] for a in aliases),
        }

    @app.get("/api/config")
    async def get_config(request: Request):
        return redact(cfg(request))

    @app.post("/api/config")
    async def post_config(request: Request):
        body = await request.json()
        saved = request.app.state.config_store.save(body)
        request.app.state.provider_router = ProviderRouter(saved)
        return redact(saved)

    @app.get("/api/providers")
    async def providers(request: Request):
        return {"data": redact(cfg(request).get("providers", []))}

    @app.post("/api/providers")
    async def add_provider(request: Request):
        body = await request.json()
        config = cfg(request)
        existing = next((p for p in config.get("providers", []) if p.get("id") == body.get("id")), None)
        provider = normalize_provider_payload(body, existing)
        providers = [p for p in config.get("providers", []) if p.get("id") != provider["id"]]
        providers.append(provider)
        config["providers"] = providers
        ensure_provider_default_models(config)
        saved = request.app.state.config_store.save(config)
        request.app.state.provider_router = ProviderRouter(saved)
        return {"ok": True, "provider": redact(provider)}

    @app.delete("/api/providers/{provider_id}")
    async def delete_provider(request: Request, provider_id: str):
        config = cfg(request)
        removed = remove_provider_from_config(config, provider_id)
        if not removed:
            raise HTTPException(status_code=404, detail="provider_not_found")
        saved = request.app.state.config_store.save(config)
        request.app.state.provider_router = ProviderRouter(saved)
        return {"ok": True, "provider_id": provider_id}

    @app.get("/api/provider-presets")
    async def provider_presets():
        return {"data": load_provider_presets()}

    @app.post("/api/claude-code/smoke", dependencies=[Depends(require_local_key)])
    async def claude_code_smoke(request: Request):
        body = {
            "model": "claude-3-5-haiku-latest",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Super DeepSeek smoke test."}],
        }
        req = type("SmokeRequest", (), {})()
        req.json = lambda: body
        return {
            "ok": True,
            "base_url": cfg(request).get("server", {}).get("public_base_url", "http://127.0.0.1:8787"),
            "model": body["model"],
            "env": {
                "ANTHROPIC_BASE_URL": cfg(request).get("server", {}).get("public_base_url", "http://127.0.0.1:8787"),
                "ANTHROPIC_API_KEY": cfg(request).get("security", {}).get("local_api_key", ""),
            },
        }

    @app.get("/api/profiles")
    async def profiles(request: Request):
        config = cfg(request)
        if ensure_provider_default_models(config):
            config = request.app.state.config_store.save(config)
            request.app.state.provider_router = ProviderRouter(config)
        return {
            "data": config.get("profiles", []),
            "models": config.get("models", []),
            "providers": redact(config.get("providers", [])),
            "default_profile": config.get("runtime", {}).get("default_profile", "default"),
        }

    @app.post("/api/profiles")
    async def save_profile(request: Request):
        body = await request.json()
        config = cfg(request)
        if ensure_provider_default_models(config):
            config = request.app.state.config_store.save(config)
        existing = next((p for p in config.get("profiles", []) if p.get("id") == body.get("id")), None)
        profile = normalize_profile_payload(body, existing)
        valid_model_ids = {m.get("id") for m in config.get("models", [])}
        for key in PROFILE_MODEL_KEYS.values():
            if profile.get(key) and profile.get(key) not in valid_model_ids:
                raise HTTPException(status_code=400, detail={"error": "unknown_model_id", "field": key, "model_id": profile.get(key)})
        profiles = [p for p in config.get("profiles", []) if p.get("id") != profile["id"]]
        profiles.append(profile)
        config["profiles"] = profiles
        if body.get("set_default"):
            config.setdefault("runtime", {})["default_profile"] = profile["id"]
        saved = request.app.state.config_store.save(config)
        request.app.state.provider_router = ProviderRouter(saved)
        return {
            "ok": True,
            "profile": profile,
            "default_profile": saved.get("runtime", {}).get("default_profile", "default"),
        }

    @app.post("/api/vision-check")
    async def vision_check(request: Request):
        body = await request.json()
        config = cfg(request)
        if ensure_provider_default_models(config):
            config = request.app.state.config_store.save(config)
        model_id = body.get("model_id") or body.get("modelId")
        if not model_id:
            profile_id = body.get("profile_id") or body.get("profileId") or config.get("runtime", {}).get("default_profile", "default")
            model_id = vision_model_id(config, profile_id)
        if not model_id:
            raise HTTPException(status_code=400, detail="vision_model_not_configured")
        result = await check_vision_model(config, model_id)
        if result.get("vision_status") in {"verified_supported", "verified_unsupported"}:
            update_model_vision_status(config, model_id, result["vision_status"])
            saved = request.app.state.config_store.save(config)
            request.app.state.provider_router = ProviderRouter(saved)
        return result

    @app.get("/api/model-capabilities")
    async def model_caps(request: Request):
        return {"data": all_model_capabilities(cfg(request))}

    @app.get("/api/aliases")
    async def aliases(request: Request):
        config = cfg(request)
        return {"data": [alias_response(a, config) for a in config.get("model_aliases", [])]}

    @app.post("/api/aliases")
    async def save_alias(request: Request):
        body = await request.json()
        config = cfg(request)
        existing = next((a for a in config.get("model_aliases", []) if a.get("alias") == body.get("alias")), None)
        alias = normalize_alias_payload(body, existing)
        if not alias.get("alias"):
            raise HTTPException(status_code=400, detail="alias_required")
        if alias.get("role") not in PROFILE_MODEL_KEYS:
            raise HTTPException(status_code=400, detail="unknown_role")
        if not any(p.get("id") == alias.get("profile_id") for p in config.get("profiles", [])):
            raise HTTPException(status_code=400, detail="unknown_profile")
        aliases = [a for a in config.get("model_aliases", []) if a.get("alias") != alias["alias"]]
        aliases.append(alias)
        config["model_aliases"] = aliases
        saved = request.app.state.config_store.save(config)
        request.app.state.provider_router = ProviderRouter(saved)
        return {"ok": True, "alias": alias_response(alias, saved), "data": [alias_response(a, saved) for a in saved.get("model_aliases", [])]}

    @app.delete("/api/aliases/{alias_name}")
    async def delete_alias(request: Request, alias_name: str):
        config = cfg(request)
        before = len(config.get("model_aliases", []))
        config["model_aliases"] = [a for a in config.get("model_aliases", []) if a.get("alias") != alias_name]
        if len(config["model_aliases"]) == before:
            raise HTTPException(status_code=404, detail="alias_not_found")
        saved = request.app.state.config_store.save(config)
        request.app.state.provider_router = ProviderRouter(saved)
        return {"ok": True, "alias": alias_name, "data": [alias_response(a, saved) for a in saved.get("model_aliases", [])]}

    @app.post("/api/test-connection")
    async def test_provider(request: Request):
        body = await request.json()
        config = cfg(request)
        provider_id = body.get("provider_id")
        provider = next((p for p in config.get("providers", []) if p.get("id") == provider_id), None)
        if not provider:
            provider = normalize_provider_payload(body)
        else:
            provider = normalize_provider_payload(body, provider)
        if body.get("model"):
            provider = {**provider, "test_model": body.get("model")}
        return await test_connection(provider)

    @app.get("/api/router/status")
    async def router_status(request: Request):
        return {"circuit_breakers": provider_router(request).status()}

    @app.get("/api/traces")
    async def traces(request: Request, limit: int = 100):
        return {"data": request.app.state.trace_store.list(limit)}

    @app.get("/api/traces/{trace_id}")
    async def trace_detail(request: Request, trace_id: str):
        record = request.app.state.trace_store.get(trace_id)
        if not record:
            raise HTTPException(status_code=404, detail="trace_not_found")
        return record

    @app.post("/api/logs/clear")
    async def clear_logs(request: Request):
        request.app.state.trace_store.clear()
        return {"ok": True}

    @app.get("/v1/models", dependencies=[Depends(require_local_key)])
    async def anthropic_models(request: Request):
        return resolver(request).models_for_anthropic()

    @app.get("/openai/v1/models", dependencies=[Depends(require_local_key)])
    async def openai_models(request: Request):
        return resolver(request).models_for_openai()

    @app.post("/v1/messages/count_tokens", dependencies=[Depends(require_local_key)])
    async def count_tokens(request: Request):
        return rough_count_tokens(await request.json())

    @app.post("/v1/messages", dependencies=[Depends(require_local_key)])
    async def anthropic_messages(request: Request):
        body = await request.json()
        incoming_model = body.get("model", "claude-3-5-haiku-latest")
        primary_resolved = resolve_for_request(request, incoming_model, "anthropic", body)
        opaque_reasoning = extract_opaque_reasoning("anthropic", body)
        policy = cfg(request).get("claude_code_compat", {}).get("billing_header_policy", "strip_for_non_anthropic_upstream")
        headers = {k: v for k, v in request.headers.items()}
        if primary_resolved.provider_protocol == "anthropic":
            payload, san_report = anthropic_payload(body, headers, primary_resolved, policy)
            upstream_format = "anthropic"
        else:
            payload, san_report = anthropic_to_openai_payload(body, headers, primary_resolved, policy)
            upstream_format = "openai_chat"
        want_stream = bool(body.get("stream"))
        start = time.perf_counter()
        trace_id = "tr_" + uuid.uuid4().hex[:10]
        steps = [
            step("Ingress", "ingress", summary="Captured Anthropic-compatible request"),
            step("Alias Resolver", "compat", summary=f"{incoming_model} -> {primary_resolved.actual_model}"),
            step("Billing Header Sanitizer", "sanitize", summary=san_report.billingHeaderAction),
        ]
        try:
            if upstream_format == "anthropic":
                mm = {
                    "images_detected": len(detect_images("anthropic", body)),
                    "policy": "passthrough",
                    "target": "anthropic_upstream",
                    "evidence_packets": [],
                    "historical_evidence": [],
                }
                upstream = await call_anthropic_messages(payload, primary_resolved)
                resolved = primary_resolved
                route_attempts = [
                    {
                        "providerId": resolved.provider_id,
                        "model": resolved.actual_model,
                        "status": "success",
                        "protocol": "anthropic",
                    }
                ]
                response = upstream
                usage = usage_from_anthropic(upstream)
                steps.append(step("Provider Router", "route", summary=f"1 attempt, final={resolved.provider_id}"))
                steps.append(step("Upstream Call", "anthropic_call", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
                steps.append(step("Response Adapter", "response_adapter", summary="Anthropic response passthrough"))
            else:
                payload, forced_role, mm = await prepare_multimodal_context(request, "anthropic", body, payload, primary_resolved, steps)
                if want_stream:
                    payload["stream"] = True
                    routed_payload, resolved, route_attempts = provider_router(request).prepare_openai_chat_stream(payload, incoming_model, force_role=forced_role)
                    steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
                    steps.append(step("Upstream Stream", "openai_chat_stream", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
                    base = {
                        "trace_id": trace_id,
                        "started_at": time.time(),
                        "client_protocol": "anthropic",
                        "client_name": "claude-code",
                        "incoming_model": incoming_model,
                        "resolved_profile_id": resolved.profile_id,
                        "resolved_role": resolved.role,
                        "upstream_provider_id": resolved.provider_id,
                        "upstream_model": resolved.actual_model,
                        "upstream_protocol": resolved.provider_protocol,
                        "sanitizer": san_report.to_dict(),
                        "request": {
                            "headers": redact(headers),
                            "body": redact(body),
                            "upstream_payload": redact({**routed_payload, "model": resolved.actual_model}),
                            "upstream_format": upstream_format,
                            "route_attempts": route_attempts,
                            "multimodal": mm,
                            "opaque_reasoning_state": opaque_reasoning,
                        },
                    }
                    return StreamingResponse(
                        stream_openai_as_anthropic(request, routed_payload, resolved, incoming_model, trace_id, {"start": start, "steps": steps, "base": base}),
                        media_type="text/event-stream",
                        headers={"x-superds-trace-id": trace_id},
                    )
                upstream, resolved, route_attempts = await provider_router(request).call_openai_chat_with_failover(payload, incoming_model, force_role=forced_role)
                response = openai_to_anthropic_response(upstream, incoming_model)
                usage = usage_from_openai(upstream)
                steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
                steps.append(step("Upstream Call", "openai_chat_call", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
                steps.append(step("Response Adapter", "response_adapter", summary="OpenAI response -> Anthropic message"))
            latency_ms = int((time.perf_counter() - start) * 1000)
            save_trace(
                request,
                {
                    "trace_id": trace_id,
                    "started_at": time.time() - latency_ms / 1000,
                    "ended_at": time.time(),
                    "client_protocol": "anthropic",
                    "client_name": "claude-code",
                    "incoming_model": incoming_model,
                    "resolved_profile_id": resolved.profile_id,
                    "resolved_role": resolved.role,
                    "upstream_provider_id": resolved.provider_id,
                    "upstream_model": resolved.actual_model,
                    "upstream_protocol": resolved.provider_protocol,
                    "status": "success",
                    "latency_ms": latency_ms,
                    "usage": usage,
                    "sanitizer": san_report.to_dict(),
                    "steps": steps,
                    "request": {
                        "headers": redact(headers),
                        "body": redact(body),
                        "upstream_payload": redact({**payload, "model": resolved.actual_model}),
                        "upstream_format": upstream_format,
                        "route_attempts": route_attempts,
                        "multimodal": mm,
                        "opaque_reasoning_state": opaque_reasoning,
                    },
                    "response": response,
                },
            )
            if want_stream:
                return StreamingResponse(anthropic_sse(response, trace_id), media_type="text/event-stream")
            return JSONResponse(response, headers={"x-superds-trace-id": trace_id})
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:1000] if exc.response is not None else str(exc)
            return gateway_error(request, trace_id, start, incoming_model, primary_resolved, san_report.to_dict(), steps, exc.response.status_code, detail)
        except Exception as exc:
            return gateway_error(request, trace_id, start, incoming_model, primary_resolved, san_report.to_dict(), steps, 502, str(exc))

    @app.post("/openai/v1/chat/completions", dependencies=[Depends(require_local_key)])
    @app.post("/v1/chat/completions", dependencies=[Depends(require_local_key)])
    async def openai_chat(request: Request):
        body = await request.json()
        incoming_model = body.get("model", "")
        primary_resolved = resolve_for_request(request, incoming_model, "openai_chat", body)
        opaque_reasoning = extract_opaque_reasoning("openai_chat", body)
        caps = model_capabilities(cfg(request), primary_resolved)
        mimo_check = validate_mimo_reasoning_history(body, caps)
        if not mimo_check["ok"]:
            raise HTTPException(status_code=400, detail={"error": "missing_reasoning_content_for_tool_history", "assistant_message_indexes": mimo_check["missing"]})
        payload = openai_payload(body, primary_resolved)
        want_stream = bool(body.get("stream"))
        start = time.perf_counter()
        trace_id = "tr_" + uuid.uuid4().hex[:10]
        steps = [
            step("Ingress", "ingress", summary="Captured OpenAI-compatible request"),
            step("Alias Resolver", "compat", summary=f"{incoming_model} -> {primary_resolved.actual_model}"),
        ]
        try:
            payload, forced_role, mm = await prepare_multimodal_context(request, "openai_chat", body, payload, primary_resolved, steps)
            if want_stream:
                payload["stream"] = True
                routed_payload, resolved, route_attempts = provider_router(request).prepare_openai_chat_stream(payload, incoming_model, force_role=forced_role)
                latency_ms = int((time.perf_counter() - start) * 1000)
                steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
                steps.append(step("Upstream Stream", "openai_chat_stream", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
                base = {
                    "trace_id": trace_id,
                    "started_at": time.time() - latency_ms / 1000,
                    "client_protocol": "openai",
                    "client_name": request.headers.get("user-agent", "unknown")[:80],
                    "incoming_model": incoming_model,
                    "resolved_profile_id": resolved.profile_id,
                    "resolved_role": resolved.role,
                    "upstream_provider_id": resolved.provider_id,
                    "upstream_model": resolved.actual_model,
                    "sanitizer": {"billingHeaderDetected": False, "billingHeaderAction": "none"},
                    "request": {
                        "headers": redact(dict(request.headers)),
                        "body": redact(body),
                        "upstream_payload": redact({**routed_payload, "model": resolved.actual_model}),
                        "route_attempts": route_attempts,
                        "multimodal": mm,
                        "opaque_reasoning_state": opaque_reasoning,
                    },
                }
                return StreamingResponse(
                    stream_openai_passthrough(request, routed_payload, resolved, {"start": start, "steps": steps, "base": base}),
                    media_type="text/event-stream",
                    headers={"x-superds-trace-id": trace_id},
                )
            upstream, resolved, route_attempts = await provider_router(request).call_openai_chat_with_failover(payload, incoming_model, force_role=forced_role)
            latency_ms = int((time.perf_counter() - start) * 1000)
            steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
            steps.append(step("Upstream Call", "litellm_call", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
            save_trace(
                request,
                {
                    "trace_id": trace_id,
                    "started_at": time.time() - latency_ms / 1000,
                    "ended_at": time.time(),
                    "client_protocol": "openai",
                    "client_name": request.headers.get("user-agent", "unknown")[:80],
                    "incoming_model": incoming_model,
                    "resolved_profile_id": resolved.profile_id,
                    "resolved_role": resolved.role,
                    "upstream_provider_id": resolved.provider_id,
                    "upstream_model": resolved.actual_model,
                    "status": "success",
                    "latency_ms": latency_ms,
                    "usage": usage_from_openai(upstream),
                    "sanitizer": {"billingHeaderDetected": False, "billingHeaderAction": "none"},
                    "steps": steps,
                    "request": {
                        "headers": redact(dict(request.headers)),
                        "body": redact(body),
                        "upstream_payload": redact({**payload, "model": resolved.actual_model}),
                        "route_attempts": route_attempts,
                        "multimodal": mm,
                        "opaque_reasoning_state": opaque_reasoning,
                    },
                    "response": upstream,
                },
            )
            if want_stream:
                return StreamingResponse(openai_sse(upstream), media_type="text/event-stream")
            return JSONResponse(upstream, headers={"x-superds-trace-id": trace_id})
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:1000] if exc.response is not None else str(exc)
            return gateway_error(request, trace_id, start, incoming_model, primary_resolved, {}, steps, exc.response.status_code, detail)
        except Exception as exc:
            return gateway_error(request, trace_id, start, incoming_model, primary_resolved, {}, steps, 502, str(exc))

    @app.post("/openai/v1/responses", dependencies=[Depends(require_local_key)])
    async def openai_responses(request: Request):
        body = await request.json()
        incoming_model = body.get("model", "gpt-4.1")
        primary_resolved = resolve_for_request(request, incoming_model, "openai_responses", body)
        opaque_reasoning = extract_opaque_reasoning("openai_responses", body)
        effective_body = responses_body_with_cached_context(request, body)
        messages = responses_input_to_messages(effective_body)
        payload = {
            "model": primary_resolved.actual_model,
            "messages": messages,
            "stream": bool(body.get("stream", False)),
        }
        if "max_output_tokens" in body:
            payload["max_tokens"] = body["max_output_tokens"]
        for key in RESPONSES_TO_CHAT_PASSTHROUGH:
            if key in body and body[key] is not None:
                payload[key] = body[key]
        if body.get("tools"):
            payload["tools"] = responses_tools_to_openai(body.get("tools", []))
        want_stream = bool(body.get("stream"))
        start = time.perf_counter()
        trace_id = "tr_" + uuid.uuid4().hex[:10]
        steps = [
            step("Ingress", "ingress", summary="Captured OpenAI Responses-compatible request"),
            step("Responses Adapter", "normalize", summary="Responses input -> chat payload MVP"),
        ]
        try:
            payload, forced_role, mm = await prepare_multimodal_context(request, "openai_responses", effective_body, payload, primary_resolved, steps)
            if want_stream:
                payload["stream"] = True
                routed_payload, resolved, route_attempts = provider_router(request).prepare_openai_chat_stream(payload, incoming_model, force_role=forced_role)
                latency_ms = int((time.perf_counter() - start) * 1000)
                steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
                steps.append(step("Upstream Stream", "openai_chat_stream", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
                base = {
                    "trace_id": trace_id,
                    "started_at": time.time() - latency_ms / 1000,
                    "client_protocol": "openai_responses",
                    "client_name": request.headers.get("user-agent", "unknown")[:80],
                    "incoming_model": incoming_model,
                    "resolved_profile_id": resolved.profile_id,
                    "resolved_role": resolved.role,
                    "upstream_provider_id": resolved.provider_id,
                    "upstream_model": resolved.actual_model,
                    "sanitizer": {"billingHeaderDetected": False, "billingHeaderAction": "none"},
                    "request": {
                        "headers": redact(dict(request.headers)),
                        "body": redact(body),
                        "upstream_payload": redact({**routed_payload, "model": resolved.actual_model}),
                        "route_attempts": route_attempts,
                        "multimodal": mm,
                        "opaque_reasoning_state": opaque_reasoning,
                    },
                }
                return StreamingResponse(
                    stream_openai_as_responses(request, routed_payload, resolved, incoming_model, {"start": start, "steps": steps, "base": base}),
                    media_type="text/event-stream",
                    headers={"x-superds-trace-id": trace_id},
                )
            upstream, resolved, route_attempts = await provider_router(request).call_openai_chat_with_failover(payload, incoming_model, force_role=forced_role)
            latency_ms = int((time.perf_counter() - start) * 1000)
            text = text_from_openai(upstream)
            response = openai_to_responses_response(upstream, text, incoming_model)
            if reasoning_from_openai(upstream):
                response["_superds_reasoning_content"] = reasoning_from_openai(upstream)
            cache_responses_state(request, response)
            steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
            steps.append(step("Response Adapter", "response_adapter", summary="Chat response -> Responses object"))
            save_trace(
                request,
                {
                    "trace_id": trace_id,
                    "started_at": time.time() - latency_ms / 1000,
                    "ended_at": time.time(),
                    "client_protocol": "openai_responses",
                    "client_name": request.headers.get("user-agent", "unknown")[:80],
                    "incoming_model": incoming_model,
                    "resolved_profile_id": resolved.profile_id,
                    "resolved_role": resolved.role,
                    "upstream_provider_id": resolved.provider_id,
                    "upstream_model": resolved.actual_model,
                    "status": "success",
                    "latency_ms": latency_ms,
                    "usage": usage_from_openai(upstream),
                    "sanitizer": {"billingHeaderDetected": False, "billingHeaderAction": "none"},
                    "steps": steps,
                    "request": {
                        "headers": redact(dict(request.headers)),
                        "body": redact(body),
                        "upstream_payload": redact({**payload, "model": resolved.actual_model}),
                        "route_attempts": route_attempts,
                        "multimodal": mm,
                        "opaque_reasoning_state": opaque_reasoning,
                    },
                    "response": response,
                },
            )
            if want_stream:
                return StreamingResponse(responses_sse(response), media_type="text/event-stream")
            return JSONResponse(response, headers={"x-superds-trace-id": trace_id})
        except Exception as exc:
            return gateway_error(request, trace_id, start, incoming_model, primary_resolved, {}, steps, 502, str(exc))

    @app.websocket("/openai/v1/responses")
    async def openai_responses_websocket(websocket: WebSocket):
        if not websocket_is_authorized(websocket):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        request = ConnectionRequest(websocket.app, dict(websocket.headers))
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({"type": "error", "status": 400, "error": {"type": "invalid_request_error", "message": "Expected JSON websocket event."}}, ensure_ascii=False))
                    continue
                if event.get("type") != "response.create":
                    await websocket.send_text(json.dumps({"type": "error", "status": 400, "error": {"type": "invalid_request_error", "message": "Expected response.create event."}}, ensure_ascii=False))
                    continue
                body = {k: v for k, v in event.items() if k != "type"}
                incoming_model = body.get("model", "gpt-4.1")
                response_id = "resp_" + uuid.uuid4().hex[:16]
                if body.get("generate") is False:
                    response = {"id": response_id, "object": "response", "created_at": int(time.time()), "status": "completed", "model": incoming_model, "output": [], "output_text": "", "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
                    cache_responses_state(request, response)
                    await websocket.send_text(json.dumps({"type": "response.created", "sequence_number": 1, "response": {**response, "status": "in_progress"}}, ensure_ascii=False))
                    await websocket.send_text(json.dumps({"type": "response.completed", "sequence_number": 2, "response": response}, ensure_ascii=False))
                    continue

                primary_resolved = resolve_for_request(request, incoming_model, "openai_responses", body)
                opaque_reasoning = extract_opaque_reasoning("openai_responses", body)
                effective_body = responses_body_with_cached_context(request, body)
                messages = responses_input_to_messages(effective_body)
                payload = {
                    "model": primary_resolved.actual_model,
                    "messages": messages,
                    "stream": True,
                }
                if "max_output_tokens" in body:
                    payload["max_tokens"] = body["max_output_tokens"]
                for key in RESPONSES_TO_CHAT_PASSTHROUGH:
                    if key in body and body[key] is not None:
                        payload[key] = body[key]
                if body.get("tools"):
                    payload["tools"] = responses_tools_to_openai(body.get("tools", []))

                start = time.perf_counter()
                trace_id = "tr_" + uuid.uuid4().hex[:10]
                steps = [
                    step("Ingress", "ingress", summary="Captured OpenAI Responses websocket request"),
                    step("Responses Adapter", "normalize", summary="Responses websocket input -> chat payload"),
                ]
                try:
                    payload, forced_role, mm = await prepare_multimodal_context(request, "openai_responses", effective_body, payload, primary_resolved, steps)
                    routed_payload, resolved, route_attempts = provider_router(request).prepare_openai_chat_stream(payload, incoming_model, force_role=forced_role)
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    steps.append(step("Provider Router", "route", summary=f"{len(route_attempts)} attempt(s), final={resolved.provider_id}"))
                    steps.append(step("Upstream Stream", "openai_chat_stream", summary=f"{resolved.provider_name} / {resolved.actual_model}"))
                    base = {
                        "trace_id": trace_id,
                        "started_at": time.time() - latency_ms / 1000,
                        "client_protocol": "openai_responses_ws",
                        "client_name": request.headers.get("user-agent", "unknown")[:80],
                        "incoming_model": incoming_model,
                        "resolved_profile_id": resolved.profile_id,
                        "resolved_role": resolved.role,
                        "upstream_provider_id": resolved.provider_id,
                        "upstream_model": resolved.actual_model,
                        "sanitizer": {"billingHeaderDetected": False, "billingHeaderAction": "none"},
                        "request": {
                            "headers": redact(dict(request.headers)),
                            "body": redact(body),
                            "upstream_payload": redact({**routed_payload, "model": resolved.actual_model}),
                            "route_attempts": route_attempts,
                            "multimodal": mm,
                            "opaque_reasoning_state": opaque_reasoning,
                        },
                    }
                    async for frame in stream_openai_as_responses(request, routed_payload, resolved, incoming_model, {"start": start, "steps": steps, "base": base}):
                        data = sse_frame_data(frame)
                        if data:
                            await websocket.send_text(json.dumps(data, ensure_ascii=False))
                except Exception as exc:
                    await websocket.send_text(json.dumps({"type": "response.failed", "sequence_number": 1, "response": {"id": trace_id, "status": "failed", "error": {"type": exc.__class__.__name__, "message": str(exc) or repr(exc)}}}, ensure_ascii=False))
        except WebSocketDisconnect:
            return


async def anthropic_sse(message: dict, trace_id: str):
    text = (message.get("content") or [{}])[0].get("text", "")
    base = {k: v for k, v in message.items() if k != "content"}
    yield "event: message_start\ndata: " + json.dumps({"message": {**base, "content": []}}, ensure_ascii=False) + "\n\n"
    yield 'event: content_block_start\ndata: {"index":0,"content_block":{"type":"text","text":""}}\n\n'
    for i in range(0, len(text), 96):
        chunk = text[i : i + 96]
        yield "event: content_block_delta\ndata: " + json.dumps({"index": 0, "delta": {"type": "text_delta", "text": chunk}}, ensure_ascii=False) + "\n\n"
    yield 'event: content_block_stop\ndata: {"index":0}\n\n'
    yield "event: message_delta\ndata: " + json.dumps({"delta": {"stop_reason": message.get("stop_reason", "end_turn"), "stop_sequence": None}, "usage": message.get("usage", {})}, ensure_ascii=False) + "\n\n"
    yield 'event: message_stop\ndata: {}\n\n'


async def openai_sse(response: dict):
    text = text_from_openai(response)
    chunk_id = response.get("id", "chatcmpl-superds")
    created = response.get("created", int(time.time()))
    model = response.get("model", "superds")
    for i in range(0, len(text), 96):
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": text[i : i + 96]}, "finish_reason": None}],
        }
        yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


def openai_to_responses_response(openai_response: dict, text: str, request_model: str) -> dict:
    usage = openai_response.get("usage") or {}
    now = int(time.time())
    output = response_output_from_openai(openai_response, text)
    return {
        "id": "resp_" + uuid.uuid4().hex[:16],
        "object": "response",
        "created_at": now,
        "status": "completed",
        "background": False,
        "error": None,
        "model": request_model,
        "output": output,
        "output_text": text,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
            "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


async def responses_sse(response: dict):
    seq = 1
    yield "event: response.created\ndata: " + json.dumps({"type": "response.created", "sequence_number": seq, "response": {**response, "status": "in_progress", "output": []}}, ensure_ascii=False) + "\n\n"
    for output_index, item in enumerate(response.get("output", [])):
        seq += 1
        if item.get("type") == "function_call":
            in_progress = {**item, "status": "in_progress", "arguments": ""}
            yield "event: response.output_item.added\ndata: " + json.dumps({"type": "response.output_item.added", "sequence_number": seq, "output_index": output_index, "item": in_progress}, ensure_ascii=False) + "\n\n"
            arguments = item.get("arguments", "")
            if arguments:
                seq += 1
                yield "event: response.function_call_arguments.delta\ndata: " + json.dumps({"type": "response.function_call_arguments.delta", "sequence_number": seq, "item_id": item["id"], "output_index": output_index, "delta": arguments}, ensure_ascii=False) + "\n\n"
            seq += 1
            yield "event: response.function_call_arguments.done\ndata: " + json.dumps({"type": "response.function_call_arguments.done", "sequence_number": seq, "item_id": item["id"], "output_index": output_index, "arguments": arguments}, ensure_ascii=False) + "\n\n"
            seq += 1
            yield "event: response.output_item.done\ndata: " + json.dumps({"type": "response.output_item.done", "sequence_number": seq, "output_index": output_index, "item": item}, ensure_ascii=False) + "\n\n"
            continue
        text = ((item.get("content") or [{}])[0].get("text")) or ""
        item_id = item["id"]
        yield "event: response.output_item.added\ndata: " + json.dumps({"type": "response.output_item.added", "sequence_number": seq, "output_index": output_index, "item": {**item, "content": []}}, ensure_ascii=False) + "\n\n"
        seq += 1
        yield "event: response.content_part.added\ndata: " + json.dumps({"type": "response.content_part.added", "sequence_number": seq, "item_id": item_id, "output_index": output_index, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}, ensure_ascii=False) + "\n\n"
        for i in range(0, len(text), 96):
            seq += 1
            yield "event: response.output_text.delta\ndata: " + json.dumps({"type": "response.output_text.delta", "sequence_number": seq, "item_id": item_id, "output_index": output_index, "content_index": 0, "delta": text[i : i + 96]}, ensure_ascii=False) + "\n\n"
        seq += 1
        yield "event: response.output_text.done\ndata: " + json.dumps({"type": "response.output_text.done", "sequence_number": seq, "item_id": item_id, "output_index": output_index, "content_index": 0, "text": text}, ensure_ascii=False) + "\n\n"
        seq += 1
        yield "event: response.content_part.done\ndata: " + json.dumps({"type": "response.content_part.done", "sequence_number": seq, "item_id": item_id, "output_index": output_index, "content_index": 0, "part": {"type": "output_text", "text": text, "annotations": []}}, ensure_ascii=False) + "\n\n"
        seq += 1
        yield "event: response.output_item.done\ndata: " + json.dumps({"type": "response.output_item.done", "sequence_number": seq, "output_index": output_index, "item": item}, ensure_ascii=False) + "\n\n"
    seq += 1
    yield "event: response.completed\ndata: " + json.dumps({"type": "response.completed", "sequence_number": seq, "response": response}, ensure_ascii=False) + "\n\n"


async def stream_openai_passthrough(request: Request, payload: dict, resolved, trace_record: dict):
    text_parts = []
    error = None
    try:
        async for data in iter_openai_chat_stream(payload, resolved):
            text, _ = openai_stream_delta(data)
            if text:
                text_parts.append(text)
            yield "data: " + data + "\n\n"
    except Exception as exc:
        error = exc
        yield "data: " + json.dumps({"error": {"type": exc.__class__.__name__, "message": str(exc) or repr(exc)}}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"
    finally:
        latency_ms = int((time.perf_counter() - trace_record["start"]) * 1000)
        status = "error" if error else "success"
        if error:
            trace_record["steps"].append(step("Gateway Error", "error", "error", f"{error.__class__.__name__}: {str(error) or repr(error)}"[:300]))
        save_trace(
            request,
            {
                **trace_record["base"],
                "ended_at": time.time(),
                "status": status,
                "latency_ms": latency_ms,
                "usage": {},
                "steps": trace_record["steps"],
                "response": {"streamed_text": "".join(text_parts), "error": str(error) if error else None},
            },
        )


async def stream_openai_as_anthropic(request: Request, payload: dict, resolved, incoming_model: str, trace_id: str, trace_record: dict):
    text_parts = []
    tool_calls = {}
    error = None
    message_id = "msg_" + uuid.uuid4().hex[:16]
    text_block_started = False
    text_block_index = None
    next_block_index = 0
    yield "event: message_start\ndata: " + json.dumps({"message": {"id": message_id, "type": "message", "role": "assistant", "model": incoming_model, "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}}, ensure_ascii=False) + "\n\n"
    try:
        async for data in iter_openai_chat_stream(payload, resolved):
            text, tool_deltas, _reasoning_text, finish = openai_stream_parts(data)
            if text:
                if not text_block_started:
                    text_block_started = True
                    text_block_index = next_block_index
                    yield "event: content_block_start\ndata: " + json.dumps({"index": text_block_index, "content_block": {"type": "text", "text": ""}}, ensure_ascii=False) + "\n\n"
                    next_block_index += 1
                text_parts.append(text)
                yield "event: content_block_delta\ndata: " + json.dumps({"index": text_block_index, "delta": {"type": "text_delta", "text": text}}, ensure_ascii=False) + "\n\n"
            for delta_call in tool_deltas:
                index = int(delta_call.get("index", len(tool_calls)))
                state = tool_calls.setdefault(
                    index,
                    {
                        "id": delta_call.get("id") or "call_" + uuid.uuid4().hex[:12],
                        "name": "",
                        "arguments": "",
                        "block_index": None,
                    },
                )
                if delta_call.get("id"):
                    state["id"] = delta_call["id"]
                function = delta_call.get("function") or {}
                if function.get("name"):
                    state["name"] = function["name"]
                if state["block_index"] is None and state["name"]:
                    state["block_index"] = next_block_index
                    next_block_index += 1
                    yield "event: content_block_start\ndata: " + json.dumps(
                        {
                            "index": state["block_index"],
                            "content_block": {"type": "tool_use", "id": state["id"], "name": state["name"], "input": {}},
                        },
                        ensure_ascii=False,
                    ) + "\n\n"
                if function.get("arguments"):
                    state["arguments"] += function["arguments"]
                    if state["block_index"] is not None:
                        yield "event: content_block_delta\ndata: " + json.dumps(
                            {
                                "index": state["block_index"],
                                "delta": {"type": "input_json_delta", "partial_json": function["arguments"]},
                            },
                            ensure_ascii=False,
                        ) + "\n\n"
            if data == "[DONE]" or finish:
                break
    except Exception as exc:
        error = exc
        yield "event: error\ndata: " + json.dumps({"type": "error", "error": {"type": exc.__class__.__name__, "message": str(exc) or repr(exc)}}, ensure_ascii=False) + "\n\n"
    if text_block_started:
        yield "event: content_block_stop\ndata: " + json.dumps({"index": text_block_index}, ensure_ascii=False) + "\n\n"
    for index in sorted(tool_calls):
        block_index = tool_calls[index].get("block_index")
        if block_index is not None:
            yield "event: content_block_stop\ndata: " + json.dumps({"index": block_index}, ensure_ascii=False) + "\n\n"
    stop_reason = "error" if error else ("tool_use" if tool_calls else "stop")
    yield "event: message_delta\ndata: " + json.dumps({"delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 0}}, ensure_ascii=False) + "\n\n"
    yield 'event: message_stop\ndata: {}\n\n'
    latency_ms = int((time.perf_counter() - trace_record["start"]) * 1000)
    if error:
        trace_record["steps"].append(step("Gateway Error", "error", "error", f"{error.__class__.__name__}: {str(error) or repr(error)}"[:300]))
    save_trace(
        request,
        {
            **trace_record["base"],
            "ended_at": time.time(),
            "status": "error" if error else "success",
            "latency_ms": latency_ms,
            "usage": {},
            "steps": trace_record["steps"],
            "response": response_from_stream_text("".join(text_parts), incoming_model),
        },
    )


async def stream_openai_as_responses(request: Request, payload: dict, resolved, incoming_model: str, trace_record: dict):
    text_parts = []
    reasoning_parts = []
    tool_calls = {}
    error = None
    seq = 1
    response_id = "resp_" + uuid.uuid4().hex[:16]
    message_item_id = None
    started = {"id": response_id, "object": "response", "created_at": int(time.time()), "status": "in_progress", "model": incoming_model, "output": []}
    yield "event: response.created\ndata: " + json.dumps({"type": "response.created", "sequence_number": seq, "response": started}, ensure_ascii=False) + "\n\n"
    try:
        async for data in iter_openai_chat_stream(payload, resolved):
            text, tool_deltas, reasoning_text, finish = openai_stream_parts(data)
            if reasoning_text:
                reasoning_parts.append(reasoning_text)
            if text:
                if message_item_id is None:
                    message_item_id = "msg_" + uuid.uuid4().hex[:12]
                    seq += 1
                    yield "event: response.output_item.added\ndata: " + json.dumps({"type": "response.output_item.added", "sequence_number": seq, "output_index": 0, "item": {"id": message_item_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []}}, ensure_ascii=False) + "\n\n"
                    seq += 1
                    yield "event: response.content_part.added\ndata: " + json.dumps({"type": "response.content_part.added", "sequence_number": seq, "item_id": message_item_id, "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}, ensure_ascii=False) + "\n\n"
                text_parts.append(text)
                seq += 1
                yield "event: response.output_text.delta\ndata: " + json.dumps({"type": "response.output_text.delta", "sequence_number": seq, "item_id": message_item_id, "output_index": 0, "content_index": 0, "delta": text}, ensure_ascii=False) + "\n\n"
            for delta_call in tool_deltas:
                index = int(delta_call.get("index", len(tool_calls)))
                state = tool_calls.setdefault(
                    index,
                    {
                        "id": delta_call.get("id") or "fc_" + uuid.uuid4().hex[:12],
                        "call_id": delta_call.get("id") or "call_" + uuid.uuid4().hex[:12],
                        "name": "",
                        "arguments": "",
                        "added": False,
                    },
                )
                if delta_call.get("id") and state["id"].startswith("fc_"):
                    state["id"] = delta_call["id"]
                    state["call_id"] = delta_call["id"]
                function = delta_call.get("function") or {}
                if function.get("name"):
                    state["name"] = function["name"]
                if not state["added"]:
                    state["added"] = True
                    seq += 1
                    yield "event: response.output_item.added\ndata: " + json.dumps({"type": "response.output_item.added", "sequence_number": seq, "output_index": index + (1 if message_item_id else 0), "item": {"id": state["id"], "type": "function_call", "status": "in_progress", "call_id": state["call_id"], "name": state["name"], "arguments": ""}}, ensure_ascii=False) + "\n\n"
                if function.get("arguments"):
                    state["arguments"] += function["arguments"]
                    seq += 1
                    yield "event: response.function_call_arguments.delta\ndata: " + json.dumps({"type": "response.function_call_arguments.delta", "sequence_number": seq, "item_id": state["id"], "output_index": index + (1 if message_item_id else 0), "delta": function["arguments"]}, ensure_ascii=False) + "\n\n"
            if data == "[DONE]" or finish:
                break
    except Exception as exc:
        error = exc
        seq += 1
        yield "event: response.failed\ndata: " + json.dumps({"type": "response.failed", "sequence_number": seq, "response": {"id": response_id, "status": "failed", "error": {"type": exc.__class__.__name__, "message": str(exc) or repr(exc)}}}, ensure_ascii=False) + "\n\n"
    output = []
    text = "".join(text_parts)
    added_empty_message = False
    if message_item_id is not None:
        output.append({"id": message_item_id, "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": text, "annotations": []}]})
    for index in sorted(tool_calls):
        state = tool_calls[index]
        output.append({"id": state["id"], "type": "function_call", "status": "completed", "call_id": state["call_id"], "name": state["name"], "arguments": state["arguments"]})
    if not output:
        message_item_id = "msg_" + uuid.uuid4().hex[:12]
        added_empty_message = True
        output.append({"id": message_item_id, "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": text, "annotations": []}]})
    response = {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "failed" if error else "completed",
        "model": incoming_model,
        "output": output,
        "output_text": text,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    if reasoning_parts:
        response["_superds_reasoning_content"] = "".join(reasoning_parts)
    cache_responses_state(request, response)
    if not error:
        output_index = 0
        if message_item_id is not None:
            if added_empty_message:
                seq += 1
                yield "event: response.output_item.added\ndata: " + json.dumps({"type": "response.output_item.added", "sequence_number": seq, "output_index": 0, "item": {"id": message_item_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []}}, ensure_ascii=False) + "\n\n"
                seq += 1
                yield "event: response.content_part.added\ndata: " + json.dumps({"type": "response.content_part.added", "sequence_number": seq, "item_id": message_item_id, "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}, ensure_ascii=False) + "\n\n"
            seq += 1
            yield "event: response.output_text.done\ndata: " + json.dumps({"type": "response.output_text.done", "sequence_number": seq, "item_id": message_item_id, "output_index": output_index, "content_index": 0, "text": text}, ensure_ascii=False) + "\n\n"
            seq += 1
            yield "event: response.content_part.done\ndata: " + json.dumps({"type": "response.content_part.done", "sequence_number": seq, "item_id": message_item_id, "output_index": output_index, "content_index": 0, "part": {"type": "output_text", "text": text, "annotations": []}}, ensure_ascii=False) + "\n\n"
            seq += 1
            yield "event: response.output_item.done\ndata: " + json.dumps({"type": "response.output_item.done", "sequence_number": seq, "output_index": output_index, "item": output[0]}, ensure_ascii=False) + "\n\n"
            output_index += 1
        for item in output[output_index:]:
            if item.get("type") != "function_call":
                continue
            seq += 1
            yield "event: response.function_call_arguments.done\ndata: " + json.dumps({"type": "response.function_call_arguments.done", "sequence_number": seq, "item_id": item["id"], "output_index": output_index, "arguments": item.get("arguments", "")}, ensure_ascii=False) + "\n\n"
            seq += 1
            yield "event: response.output_item.done\ndata: " + json.dumps({"type": "response.output_item.done", "sequence_number": seq, "output_index": output_index, "item": item}, ensure_ascii=False) + "\n\n"
            output_index += 1
        seq += 1
        yield "event: response.completed\ndata: " + json.dumps({"type": "response.completed", "sequence_number": seq, "response": response}, ensure_ascii=False) + "\n\n"
    latency_ms = int((time.perf_counter() - trace_record["start"]) * 1000)
    if error:
        trace_record["steps"].append(step("Gateway Error", "error", "error", f"{error.__class__.__name__}: {str(error) or repr(error)}"[:300]))
    save_trace(
        request,
        {
            **trace_record["base"],
            "ended_at": time.time(),
            "status": "error" if error else "success",
            "latency_ms": latency_ms,
            "usage": {},
            "steps": trace_record["steps"],
            "response": response,
        },
    )


def gateway_error(request: Request, trace_id: str, start: float, incoming_model: str, resolved, sanitizer: dict, steps: list, status_code: int, message: str):
    latency_ms = int((time.perf_counter() - start) * 1000)
    message = message or "empty upstream error"
    steps.append(step("Gateway Error", "error", "error", message[:300]))
    save_trace(
        request,
        {
            "trace_id": trace_id,
            "started_at": time.time() - latency_ms / 1000,
            "ended_at": time.time(),
            "client_protocol": "gateway",
            "incoming_model": incoming_model,
            "resolved_profile_id": resolved.profile_id,
            "resolved_role": resolved.role,
            "upstream_provider_id": resolved.provider_id,
            "upstream_model": resolved.actual_model,
            "status": "error",
            "latency_ms": latency_ms,
            "usage": {},
            "sanitizer": sanitizer,
            "steps": steps,
            "request": {},
            "response": {"error": message},
        },
    )
    return JSONResponse(
        status_code=502,
        content={"error": {"type": "upstream_error", "upstream_status": status_code, "message": message, "trace_id": trace_id}},
    )


app = create_app()
