import json
import time
from typing import Any, AsyncIterator, Dict

import httpx


def _join(base_url: str, suffix: str) -> str:
    return base_url.rstrip("/") + "/" + suffix.lstrip("/")


def mock_openai_response(payload: Dict[str, Any], resolved, reason: str = "mock") -> Dict[str, Any]:
    prompt = ""
    for msg in payload.get("messages", []):
        if msg.get("role") == "user":
            prompt = msg.get("content", "")
    text = (
        "Super DeepSeek 本地网关已接到请求。"
        f" 当前没有配置 `{resolved.provider_name}` 的上游 API Key，所以返回本地 mock 响应。"
        " 配好 .env 后，同一个端点会转发到真实模型。"
    )
    if prompt:
        text += f"\n\n收到的用户输入预览：{prompt[:180]}"
    now = int(time.time())
    return {
        "id": f"chatcmpl-superds-{now}",
        "object": "chat.completion",
        "created": now,
        "model": resolved.actual_model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": sum(len(str(m.get("content", ""))) for m in payload.get("messages", [])) // 4,
            "completion_tokens": len(text) // 4,
            "total_tokens": (sum(len(str(m.get("content", ""))) for m in payload.get("messages", [])) + len(text)) // 4,
        },
        "_superds_mock_reason": reason,
    }


def mock_anthropic_response(payload: Dict[str, Any], resolved, reason: str = "mock") -> Dict[str, Any]:
    prompt = ""
    for msg in payload.get("messages", []):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt = content
            elif isinstance(content, list):
                prompt = "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
    text = (
        "Super DeepSeek 本地网关已接到 Anthropic 兼容请求。"
        f" 当前没有配置 `{resolved.provider_name}` 的上游 API Key，所以返回本地 mock 响应。"
    )
    if prompt:
        text += f"\n\n收到的用户输入预览：{prompt[:180]}"
    return {
        "id": f"msg_superds_{int(time.time())}",
        "type": "message",
        "role": "assistant",
        "model": payload.get("model", resolved.actual_model),
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": max(1, len(prompt) // 4), "output_tokens": max(1, len(text) // 4)},
    }


DEFAULT_UPSTREAM_TIMEOUT = httpx.Timeout(300.0, connect=30.0, read=300.0, write=60.0, pool=30.0)


def openai_chat_request(payload: Dict[str, Any], resolved, stream: bool) -> tuple[str, Dict[str, Any], Dict[str, str]]:
    body = dict(payload)
    body.pop("_superds_sanitized_headers", None)
    body["stream"] = stream
    headers = {"Authorization": f"Bearer {resolved.api_key}", "Content-Type": "application/json"}
    return _join(resolved.base_url, "chat/completions"), body, headers


async def call_openai_chat(payload: Dict[str, Any], resolved, timeout=DEFAULT_UPSTREAM_TIMEOUT) -> Dict[str, Any]:
    if not resolved.api_key or not resolved.base_url:
        return mock_openai_response(payload, resolved, "missing_upstream_api_key")

    url, body, headers = openai_chat_request(payload, resolved, stream=False)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json()


async def iter_openai_chat_stream(payload: Dict[str, Any], resolved, timeout=DEFAULT_UPSTREAM_TIMEOUT) -> AsyncIterator[str]:
    if not resolved.api_key or not resolved.base_url:
        mock = mock_openai_response(payload, resolved, "missing_upstream_api_key")
        text = ((mock.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        yield json.dumps(
            {
                "id": mock.get("id"),
                "object": "chat.completion.chunk",
                "created": mock.get("created", int(time.time())),
                "model": mock.get("model"),
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
            },
            ensure_ascii=False,
        )
        yield json.dumps(
            {
                "id": mock.get("id"),
                "object": "chat.completion.chunk",
                "created": mock.get("created", int(time.time())),
                "model": mock.get("model"),
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
            ensure_ascii=False,
        )
        yield "[DONE]"
        return

    url, body, headers = openai_chat_request(payload, resolved, stream=True)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=body, headers=headers) as response:
            if response.status_code >= 400:
                error_body = (await response.aread()).decode("utf-8", errors="replace")
                raise httpx.HTTPStatusError(error_body, request=response.request, response=response)
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line.startswith(":"):
                    continue
                yield line


async def call_anthropic_messages(payload: Dict[str, Any], resolved, timeout=DEFAULT_UPSTREAM_TIMEOUT) -> Dict[str, Any]:
    if not resolved.api_key or not resolved.base_url:
        return mock_anthropic_response(payload, resolved, "missing_upstream_api_key")

    body = dict(payload)
    body.pop("_superds_sanitized_headers", None)
    body["stream"] = False
    headers = {
        "x-api-key": resolved.api_key,
        "anthropic-version": body.pop("anthropic_version", "2023-06-01"),
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(_join(resolved.base_url, "messages"), json=body, headers=headers)
        response.raise_for_status()
        return response.json()


async def test_connection(provider: dict) -> dict:
    if not provider.get("api_key"):
        return {
            "ok": False,
            "status": "missing_api_key",
            "latency_ms": None,
            "ttfb_ms": None,
            "mode": "stream_check",
        }
    start = time.perf_counter()
    first_byte_at = None
    model = provider.get("test_model") or provider.get("default_model") or "gpt-4o-mini"
    if provider.get("protocol") == "anthropic":
        endpoint = "messages"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
        }
        headers = {
            "x-api-key": provider.get("api_key"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    else:
        endpoint = "chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {provider.get('api_key')}"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            async with client.stream(
                "POST",
                _join(provider.get("base_url", ""), endpoint),
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        first_byte_at = time.perf_counter()
                        break
        latency_ms = int((time.perf_counter() - start) * 1000)
        ttfb_ms = int(((first_byte_at or time.perf_counter()) - start) * 1000)
        return {
            "ok": True,
            "status": "healthy" if ttfb_ms < provider.get("degraded_threshold_ms", 6000) else "degraded",
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "ttfb_ms": ttfb_ms,
            "mode": "stream_check",
            "model": model,
        }
    except httpx.HTTPStatusError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status": exc.response.status_code,
            "latency_ms": latency_ms,
            "ttfb_ms": None,
            "mode": "stream_check",
            "model": model,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": exc.__class__.__name__,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "ttfb_ms": None,
            "mode": "stream_check",
            "model": model,
            "error": str(exc),
        }
