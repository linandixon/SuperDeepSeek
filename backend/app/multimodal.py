import hashlib
import json
import time
import uuid
from copy import deepcopy
from typing import Any, Dict, List


IMAGE_REF_WORDS = ["刚才那张图", "上一张图", "这张图", "图里", "截图", "图片", "右下角", "左下角", "右上角", "左上角"]


def detect_images(protocol: str, body: Dict[str, Any]) -> List[dict]:
    if protocol == "anthropic":
        return _detect_anthropic_images(body)
    if protocol == "openai_responses":
        return _detect_responses_images(body)
    return _detect_openai_images(body)


def latest_user_text(protocol: str, body: Dict[str, Any]) -> str:
    if protocol == "openai_responses":
        inp = body.get("input")
        if isinstance(inp, str):
            return inp
        items = inp if isinstance(inp, list) else []
        texts = []
        for item in items:
            if isinstance(item, dict):
                texts.extend(_text_from_content(item.get("content")))
        return "\n".join(texts)
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return "\n".join(_text_from_content(msg.get("content")))
    return ""


def references_previous_image(text: str) -> bool:
    return any(word in text for word in IMAGE_REF_WORDS)


def make_evidence_packets(images: List[dict], session_key: str, note: str = "vision_worker_placeholder", observation_text: str = "") -> List[dict]:
    packets = []
    for image in images:
        source_hash = image.get("hash") or _hash_text(str(image.get("source", "")))
        summary = observation_text.strip() or "检测到图片输入；当前 MVP 使用视觉副手占位证据。接入 Qwen-VL/OCR 后这里会包含 OCR、布局、对象和区域坐标。"
        packets.append(
            {
                "id": "ev_" + uuid.uuid4().hex[:10],
                "session_key": session_key,
                "type": "vision_observation",
                "source": image.get("source_ref", source_hash),
                "source_hash": source_hash,
                "content": {
                    "summary": summary,
                    "ocr_text": observation_text.strip(),
                    "regions": [],
                    "note": note,
                },
                "confidence": 0.78 if observation_text.strip() else 0.2,
                "uncertainties": [] if observation_text.strip() else ["尚未接入真实视觉/OCR worker，不能保证图片细节。"],
                "created_at": int(time.time()),
            }
        )
    return packets


def evidence_system_message(evidence_packets: List[dict], historical: List[dict] = None) -> str:
    parts = []
    for ev in historical or []:
        content = ev.get("content", {})
        parts.append(f"- 历史图片证据 {ev.get('id')}: {content.get('summary', '')} OCR: {content.get('ocr_text', '')}")
    for ev in evidence_packets:
        content = ev.get("content", {})
        parts.append(f"- 当前图片证据 {ev.get('id')}: {content.get('summary', '')} OCR: {content.get('ocr_text', '')}")
    if not parts:
        return ""
    return "视觉证据包（由 Super DeepSeek 视觉副手提供，回答必须只基于这些可追溯观察，不要假装直接看图）：\n" + "\n".join(parts)


def inject_evidence_into_chat_payload(payload: Dict[str, Any], evidence_text: str) -> Dict[str, Any]:
    if not evidence_text:
        return payload
    out = deepcopy(payload)
    messages = out.setdefault("messages", [])
    insert_at = 1 if messages and messages[0].get("role") == "system" else 0
    messages.insert(insert_at, {"role": "system", "content": evidence_text})
    out["messages"] = _strip_images_from_messages(messages)
    return out


def responses_input_to_messages(body: Dict[str, Any]) -> List[dict]:
    messages = []
    if body.get("instructions"):
        messages.append({"role": "system", "content": body.get("instructions")})
    inp = body.get("input")
    if isinstance(inp, str):
        messages.append({"role": "user", "content": inp})
        return messages
    pending_tool_calls = []
    pending_reasoning_content = ""

    def flush_pending_tool_calls() -> None:
        nonlocal pending_tool_calls, pending_reasoning_content
        if not pending_tool_calls:
            return
        message = {"role": "assistant", "content": "", "tool_calls": pending_tool_calls}
        if pending_reasoning_content:
            message["reasoning_content"] = pending_reasoning_content
        messages.append(message)
        pending_tool_calls = []
        pending_reasoning_content = ""

    for item in inp if isinstance(inp, list) else []:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        if item.get("type") == "function_call":
            arguments = item.get("arguments", "")
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)
            call_id = item.get("call_id") or item.get("id") or ("call_" + _hash_text(item.get("name", "") + arguments))
            pending_tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": arguments,
                    },
                }
            )
            if item.get("_superds_reasoning_content"):
                pending_reasoning_content = item["_superds_reasoning_content"]
        elif item.get("type") == "function_call_output":
            flush_pending_tool_calls()
            messages.append({"role": "tool", "tool_call_id": item.get("call_id"), "content": item.get("output", "")})
        elif item.get("type") == "message" or role in {"user", "assistant", "system", "developer"}:
            flush_pending_tool_calls()
            if role == "developer":
                role = "system"
            content = item.get("content")
            if _content_has_image(content):
                messages.append({"role": role, "content": _openai_content_from_responses(content)})
            else:
                messages.append({"role": role, "content": "\n".join(_text_from_content(content))})
    flush_pending_tool_calls()
    return messages


def _content_has_image(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    return any(isinstance(block, dict) and block.get("type") in {"input_image", "image_url"} for block in content if isinstance(content, list))


def _openai_content_from_responses(content: Any) -> List[dict]:
    out = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "input_text":
            out.append({"type": "text", "text": block.get("text", "")})
        elif block.get("type") == "image_url":
            out.append(block)
        elif block.get("type") == "input_image":
            url = block.get("image_url") or block.get("url")
            if url:
                out.append({"type": "image_url", "image_url": {"url": url}})
    return out


def _strip_images_from_messages(messages: List[dict]) -> List[dict]:
    out = []
    for msg in messages:
        clone = dict(msg)
        content = clone.get("content")
        if isinstance(content, list):
            clone["content"] = "\n".join(_text_from_content(content))
        out.append(clone)
    return out


def _detect_anthropic_images(body: Dict[str, Any]) -> List[dict]:
    images = []
    for mi, msg in enumerate(body.get("messages", [])):
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for bi, block in enumerate(content):
            if isinstance(block, dict) and block.get("type") == "image":
                source = block.get("source", {})
                images.append({"message_index": mi, "block_index": bi, "source": source, "hash": _hash_text(str(source)), "source_ref": f"messages[{mi}].content[{bi}]"})
    return images


def _detect_openai_images(body: Dict[str, Any]) -> List[dict]:
    images = []
    for mi, msg in enumerate(body.get("messages", [])):
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for bi, block in enumerate(content):
            if isinstance(block, dict) and block.get("type") in {"image_url", "input_image"}:
                images.append({"message_index": mi, "block_index": bi, "source": block, "hash": _hash_text(str(block)), "source_ref": f"messages[{mi}].content[{bi}]"})
    return images


def _detect_responses_images(body: Dict[str, Any]) -> List[dict]:
    images = []
    inp = body.get("input")
    for ii, item in enumerate(inp if isinstance(inp, list) else []):
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        for bi, block in enumerate(content if isinstance(content, list) else []):
            if isinstance(block, dict) and block.get("type") in {"input_image", "image_url"}:
                images.append({"item_index": ii, "block_index": bi, "source": block, "hash": _hash_text(str(block)), "source_ref": f"input[{ii}].content[{bi}]"})
    return images


def _text_from_content(content: Any) -> List[str]:
    if isinstance(content, str):
        return [content]
    out = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, str):
            out.append(block)
        elif isinstance(block, dict) and block.get("type") in {"text", "input_text", "output_text"}:
            out.append(block.get("text", ""))
        elif isinstance(block, dict) and block.get("type") in {"image", "image_url", "input_image"}:
            out.append("[image omitted; see vision evidence packet]")
    return [x for x in out if x]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
