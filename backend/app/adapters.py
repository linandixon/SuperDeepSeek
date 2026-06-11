import json
from typing import Any, Dict, List, Tuple

from .billing_header_sanitizer import (
    SanitizationReport,
    merge_reports,
    sanitize_headers,
    sanitize_system_first_line,
)


ANTHROPIC_TO_OPENAI_PASSTHROUGH = {
    "max_tokens",
    "max_completion_tokens",
    "temperature",
    "top_p",
    "top_k",
    "metadata",
    "service_tier",
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
    "extra_body",
}


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "image":
                parts.append("[image omitted; see vision evidence packet]")
            elif block.get("type") == "tool_result":
                parts.append(str(block.get("content", "")))
        return "\n".join([p for p in parts if p])
    return "" if content is None else str(content)


def anthropic_content_to_openai(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return "" if content is None else str(content)
    out = []
    has_image = False
    for block in content:
        if isinstance(block, str):
            out.append({"type": "text", "text": block})
        elif isinstance(block, dict) and block.get("type") == "text":
            out.append({"type": "text", "text": block.get("text", "")})
        elif isinstance(block, dict) and block.get("type") == "image":
            source = block.get("source", {})
            media_type = source.get("media_type", "image/png")
            if source.get("type") == "base64" and source.get("data"):
                url = f"data:{media_type};base64,{source.get('data')}"
            else:
                url = source.get("url", "")
            out.append({"type": "image_url", "image_url": {"url": url}})
            has_image = True
        elif isinstance(block, dict) and block.get("type") == "tool_result":
            out.append({"type": "text", "text": str(block.get("content", ""))})
    out = [b for b in out if b.get("type") != "text" or b.get("text")]
    if has_image:
        return out
    return "\n".join(b.get("text", "") for b in out if b.get("type") == "text")


def _json_dumps(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _openai_messages_from_anthropic_message(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    if role == "assistant" and isinstance(content, list):
        text_parts = []
        tool_calls = []
        for block in content:
            if not isinstance(block, dict):
                text_parts.append(str(block))
                continue
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id") or f"call_{len(tool_calls)}",
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": _json_dumps(block.get("input", {})),
                        },
                    }
                )
        out = {"role": "assistant", "content": "\n".join(p for p in text_parts if p)}
        if tool_calls:
            out["tool_calls"] = tool_calls
        return [out]
    if role == "user" and isinstance(content, list):
        messages = []
        text_blocks = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                if text_blocks:
                    messages.append({"role": "user", "content": anthropic_content_to_openai(text_blocks)})
                    text_blocks = []
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id") or block.get("id") or "",
                        "content": content_to_text(block.get("content", "")),
                    }
                )
            else:
                text_blocks.append(block)
        if text_blocks:
            messages.append({"role": "user", "content": anthropic_content_to_openai(text_blocks)})
        return messages or [{"role": "user", "content": ""}]
    if role not in {"user", "assistant", "system", "tool"}:
        role = "user"
    return [{"role": role, "content": anthropic_content_to_openai(content)}]


def anthropic_system_to_text(system: Any) -> str:
    if isinstance(system, str):
        return system
    return content_to_text(system)


def anthropic_tools_to_openai(tools: List[dict]) -> List[dict]:
    out = []
    for tool in tools or []:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
        )
    return out


def responses_tools_to_openai(tools: List[dict]) -> List[dict]:
    out = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            out.append(tool)
        elif tool.get("type") == "function" and tool.get("name"):
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
                    },
                }
            )
    return out


def anthropic_to_openai_payload(
    body: Dict[str, Any],
    headers: Dict[str, str],
    resolved,
    policy: str,
) -> Tuple[Dict[str, Any], SanitizationReport]:
    clean_headers, header_report = sanitize_headers(headers, policy, resolved.provider_protocol)
    system = anthropic_system_to_text(body.get("system", ""))
    system, system_report = sanitize_system_first_line(system, policy, resolved.provider_protocol)
    report = merge_reports(header_report, system_report)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    for msg in body.get("messages", []):
        messages.extend(_openai_messages_from_anthropic_message(msg))

    payload = {"model": resolved.actual_model, "messages": messages, "stream": bool(body.get("stream", False))}
    for key in ANTHROPIC_TO_OPENAI_PASSTHROUGH:
        if key in body:
            payload[key] = body[key]
    if "stop_sequences" in body:
        payload["stop"] = body["stop_sequences"]
    elif "stop" in body:
        payload["stop"] = body["stop"]
    if body.get("tools"):
        payload["tools"] = anthropic_tools_to_openai(body.get("tools", []))
    if body.get("tool_choice"):
        choice = body["tool_choice"]
        if isinstance(choice, str):
            payload["tool_choice"] = choice
        elif isinstance(choice, dict) and choice.get("type") == "tool" and choice.get("name"):
            payload["tool_choice"] = {"type": "function", "function": {"name": choice["name"]}}
        elif isinstance(choice, dict) and choice.get("type") == "any":
            payload["tool_choice"] = "required"
        elif isinstance(choice, dict) and choice.get("type") in {"auto", "none"}:
            payload["tool_choice"] = choice["type"]
        else:
            payload["tool_choice"] = "auto"
    payload["_superds_sanitized_headers"] = clean_headers
    return payload, report


def anthropic_payload(
    body: Dict[str, Any],
    headers: Dict[str, str],
    resolved,
    policy: str,
) -> Tuple[Dict[str, Any], SanitizationReport]:
    clean_headers, header_report = sanitize_headers(headers, policy, resolved.provider_protocol)
    payload = dict(body)
    payload["model"] = resolved.actual_model
    if isinstance(body.get("system"), str):
        system, system_report = sanitize_system_first_line(body.get("system", ""), policy, resolved.provider_protocol)
        payload["system"] = system
        report = merge_reports(header_report, system_report)
    else:
        report = header_report
    payload["_superds_sanitized_headers"] = clean_headers
    return payload, report


def openai_payload(body: Dict[str, Any], resolved) -> Dict[str, Any]:
    payload = dict(body)
    payload["model"] = resolved.actual_model
    return payload


def openai_to_anthropic_response(openai_response: Dict[str, Any], request_model: str) -> Dict[str, Any]:
    choice = (openai_response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = message.get("content") or ""
    reasoning_text = message.get("reasoning_content") or ""
    content = []
    if text:
        content.append({"type": "text", "text": text})
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        content.append(
            {
                "type": "tool_use",
                "id": call.get("id") or f"call_{len(content)}",
                "name": function.get("name", ""),
                "input": arguments,
            }
        )
    if not content:
        content = [{"type": "text", "text": reasoning_text}]
    usage = openai_response.get("usage") or {}
    return {
        "id": openai_response.get("id", "msg_superds"),
        "type": "message",
        "role": "assistant",
        "model": request_model,
        "content": content,
        "stop_reason": "tool_use" if message.get("tool_calls") else (choice.get("finish_reason") or "end_turn"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
            "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
        },
    }


def rough_count_tokens(body: Dict[str, Any]) -> Dict[str, Any]:
    text = anthropic_system_to_text(body.get("system", ""))
    for msg in body.get("messages", []):
        text += "\n" + content_to_text(msg.get("content", ""))
    return {"input_tokens": max(1, len(text) // 4)}
