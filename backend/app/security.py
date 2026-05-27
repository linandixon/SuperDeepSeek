from fastapi import Header, HTTPException, Request


def configured_key(config: dict) -> str:
    return config.get("security", {}).get("local_api_key", "")


def token_from_headers(headers) -> str:
    authorization = headers.get("authorization", "")
    if authorization:
        lower = authorization.lower()
        if lower.startswith("bearer ") or lower.startswith("token "):
            return authorization.split(" ", 1)[1].strip()
        return authorization.strip()
    for name in ("x-api-key", "api-key", "anthropic-api-key", "x-goog-api-key"):
        value = headers.get(name, "")
        if value:
            return value.strip()
    return ""


async def require_local_key(
    request: Request,
    authorization: str = Header(default=""),
    x_api_key: str = Header(default=""),
) -> None:
    config = request.app.state.config_store.get()
    expected = configured_key(config)
    if not expected:
        return
    token = token_from_headers(request.headers)
    if not token and (authorization or x_api_key):
        token = token_from_headers({"authorization": authorization, "x-api-key": x_api_key})
    if token != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_or_invalid_local_api_key",
                "message": "Use ANTHROPIC_API_KEY/OPENAI_API_KEY with the Super DeepSeek local key.",
            },
        )
