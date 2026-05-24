DEFAULT_CAPABILITIES = {
    "api_format": "openai_chat",
    "vision": None,
    "vision_status": "unknown",
    "tools": True,
    "reasoning_state": "none",
    "preserve_opaque_reasoning": False,
}


def normalize_caps(caps: dict) -> dict:
    caps = dict(caps)
    status = caps.get("vision_status")
    if status == "verified_supported" or caps.get("vision") is True:
        caps["vision"] = True
        caps["vision_status"] = "verified_supported"
    elif status == "verified_unsupported":
        caps["vision"] = False
        caps["vision_status"] = "verified_unsupported"
    else:
        caps["vision"] = None
        caps["vision_status"] = "unknown"
    return caps


def model_capabilities(config: dict, resolved) -> dict:
    caps = dict(DEFAULT_CAPABILITIES)
    provider = next((p for p in config.get("providers", []) if p.get("id") == resolved.provider_id), None)
    if provider:
        caps.update(provider.get("capabilities", {}))
    model = next(
        (
            m
            for m in config.get("models", [])
            if m.get("provider_id") == resolved.provider_id
            and m.get("actual_model") == resolved.actual_model
            and m.get("role") == resolved.role
        ),
        None,
    )
    if not model:
        model = next(
            (
                m
                for m in config.get("models", [])
                if m.get("provider_id") == resolved.provider_id
                and m.get("actual_model") == resolved.actual_model
            ),
            None,
        )
    if model:
        caps.update(model.get("capabilities", {}))
    caps.setdefault("api_format", resolved.provider_protocol or "openai_chat")
    return normalize_caps(caps)


def all_model_capabilities(config: dict) -> list:
    out = []
    for model in config.get("models", []):
        caps = dict(DEFAULT_CAPABILITIES)
        caps.update(model.get("capabilities", {}))
        caps = normalize_caps(caps)
        out.append(
            {
                "id": model.get("id"),
                "provider_id": model.get("provider_id"),
                "actual_model": model.get("actual_model"),
                "role": model.get("role"),
                "capabilities": caps,
            }
        )
    return out
