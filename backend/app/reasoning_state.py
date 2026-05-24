from copy import deepcopy
from typing import Any, Dict, List


def extract_opaque_reasoning(protocol: str, body: Dict[str, Any]) -> List[dict]:
    if protocol == "anthropic":
        return _extract_anthropic(body)
    if protocol == "openai_responses":
        return _extract_responses(body)
    return _extract_openai_chat(body)


def _extract_openai_chat(body: Dict[str, Any]) -> List[dict]:
    out = []
    for index, msg in enumerate(body.get("messages", [])):
        if msg.get("role") != "assistant":
            continue
        if "reasoning_content" in msg:
            out.append(
                {
                    "provider": "mimo",
                    "kind": "reasoning_content",
                    "message_index": index,
                    "value": msg.get("reasoning_content"),
                    "mustReplayUnmodified": True,
                }
            )
    return out


def _extract_anthropic(body: Dict[str, Any]) -> List[dict]:
    out = []
    for msg_index, msg in enumerate(body.get("messages", [])):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block_index, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") in {"thinking", "redacted_thinking"}:
                out.append(
                    {
                        "provider": "anthropic",
                        "kind": block.get("type"),
                        "message_index": msg_index,
                        "block_index": block_index,
                        "value": deepcopy(block),
                        "mustReplayUnmodified": True,
                    }
                )
    return out


def _extract_responses(body: Dict[str, Any]) -> List[dict]:
    out = []
    include = body.get("include") or []
    if "reasoning.encrypted_content" in include:
        out.append(
            {
                "provider": "openai_responses",
                "kind": "encrypted_reasoning_requested",
                "value": "reasoning.encrypted_content",
                "mustReplayUnmodified": True,
            }
        )
    for index, item in enumerate(body.get("input", []) if isinstance(body.get("input"), list) else []):
        if isinstance(item, dict) and item.get("type") == "reasoning":
            out.append(
                {
                    "provider": "openai_responses",
                    "kind": "reasoning_item",
                    "item_index": index,
                    "value": deepcopy(item),
                    "mustReplayUnmodified": True,
                }
            )
    return out


def validate_mimo_reasoning_history(body: Dict[str, Any], caps: dict) -> dict:
    if caps.get("reasoning_state") != "mimo_reasoning_content":
        return {"ok": True, "missing": []}
    missing = []
    for index, msg in enumerate(body.get("messages", [])):
        if msg.get("role") == "assistant" and msg.get("tool_calls") and "reasoning_content" not in msg:
            missing.append(index)
    return {"ok": not missing, "missing": missing}
