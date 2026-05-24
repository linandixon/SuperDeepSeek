from fastapi import Header, HTTPException, Request


def configured_key(config: dict) -> str:
    return config.get("security", {}).get("local_api_key", "")


async def require_local_key(
    request: Request,
    authorization: str = Header(default=""),
    x_api_key: str = Header(default=""),
) -> None:
    config = request.app.state.config_store.get()
    expected = configured_key(config)
    if not expected:
        return
    token = ""
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_api_key:
        token = x_api_key.strip()
    if token != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_or_invalid_local_api_key",
                "message": "Use ANTHROPIC_API_KEY/OPENAI_API_KEY with the Super DeepSeek local key.",
            },
        )
