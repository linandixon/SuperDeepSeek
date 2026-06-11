import os


def _local_key() -> str:
    return os.getenv("SUPERDS_LOCAL_API_KEY") or "sk-superds-local-change-me"


def default_config() -> dict:
    return {
        "server": {
            "host": os.getenv("SUPERDS_HOST", "127.0.0.1"),
            "port": int(os.getenv("SUPERDS_PORT", "8787")),
            "public_base_url": "http://127.0.0.1:8787",
        },
        "security": {
            "local_api_key": _local_key(),
            "bind_localhost_only": True,
            "redact_secrets_in_logs": True,
        },
        "runtime": {
            "mode": "observe",
            "default_profile": "default",
            "trace_retention_days": 7,
            "image_policy": "ocr",
            "evidence_retention_days": 14,
            "vision_worker": {
                "max_tokens": 2048,
                "timeout_seconds": 90,
            },
            "circuit_breaker": {
                "failure_threshold": 3,
                "success_threshold": 2,
                "timeout_seconds": 60,
            },
        },
        "claude_code_compat": {
            "enabled": True,
            "billing_header_policy": "strip_for_non_anthropic_upstream",
            "expose_claude_aliases": True,
            "require_haiku_alias": True,
        },
        "providers": [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "protocol": "openai",
                "base_url": "https://api.deepseek.com/v1",
                "api_key_env": "DEEPSEEK_API_KEY",
                "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
                "default_model": "deepseek-chat",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "reasoning_content", "api_format": "openai_chat"},
            },
            {
                "id": "qwen",
                "name": "Qwen",
                "protocol": "openai",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key_env": "QWEN_API_KEY",
                "api_key": os.getenv("QWEN_API_KEY", ""),
                "default_model": "qwen2.5-coder-32b-instruct",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "none", "api_format": "openai_chat"},
            },
            {
                "id": "openrouter",
                "name": "OpenRouter",
                "protocol": "openai",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "api_key": os.getenv("OPENROUTER_API_KEY", ""),
                "default_model": "anthropic/claude-3.5-sonnet",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "anthropic_thinking", "api_format": "openai_chat"},
            },
            {
                "id": "kimi",
                "name": "Kimi",
                "protocol": "openai",
                "base_url": "https://api.moonshot.cn/v1",
                "api_key_env": "KIMI_API_KEY",
                "api_key": os.getenv("KIMI_API_KEY", ""),
                "default_model": "moonshot-v1-128k",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "none", "api_format": "openai_chat"},
            },
            {
                "id": "mimo",
                "name": "Xiaomi MiMo",
                "protocol": "openai",
                "base_url": "https://api.xiaomimimo.com/v1",
                "api_key_env": "MIMO_API_KEY",
                "api_key": os.getenv("MIMO_API_KEY", ""),
                "default_model": "mimo-v2.5-pro",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "mimo_reasoning_content", "api_format": "openai_chat"},
            },
        ],
        "models": [
            {
                "id": "deepseek_main",
                "provider_id": "deepseek",
                "litellm_model": "openai/deepseek-chat",
                "actual_model": "deepseek-chat",
                "role": "main",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "reasoning_content", "api_format": "openai_chat"},
            },
            {
                "id": "deepseek_fast",
                "provider_id": "deepseek",
                "litellm_model": "openai/deepseek-chat",
                "actual_model": "deepseek-chat",
                "role": "fast_tool",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "reasoning_content", "api_format": "openai_chat"},
            },
            {
                "id": "deepseek_large",
                "provider_id": "deepseek",
                "litellm_model": "openai/deepseek-reasoner",
                "actual_model": "deepseek-reasoner",
                "role": "large",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "reasoning_content", "api_format": "openai_chat"},
            },
            {
                "id": "qwen_verifier",
                "provider_id": "qwen",
                "litellm_model": "openai/qwen2.5-coder-32b-instruct",
                "actual_model": "qwen2.5-coder-32b-instruct",
                "role": "verifier",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "none", "api_format": "openai_chat"},
            },
            {
                "id": "qwen_vision",
                "provider_id": "qwen",
                "litellm_model": "openai/qwen-vl-max",
                "actual_model": "qwen-vl-max",
                "role": "vision",
                "capabilities": {"vision": True, "tools": False, "reasoning_state": "none", "api_format": "openai_chat"},
            },
            {
                "id": "mimo_reasoning",
                "provider_id": "mimo",
                "litellm_model": "openai/mimo-v2.5-pro",
                "actual_model": "mimo-v2.5-pro",
                "role": "large",
                "capabilities": {"vision": False, "tools": True, "reasoning_state": "mimo_reasoning_content", "api_format": "openai_chat"},
            },
        ],
        "profiles": [
            {
                "id": "default",
                "name": "Default",
                "main_model": "deepseek_main",
                "fast_tool_model": "deepseek_fast",
                "large_model": "deepseek_large",
                "verifier_model": "qwen_verifier",
                "vision_model": "qwen_vision",
                "failover": {
                    "main": ["qwen_verifier"],
                    "fast_tool": ["qwen_verifier"],
                    "large": ["deepseek_main", "qwen_verifier"],
                    "verifier": ["deepseek_main"],
                    "default": [],
                },
            }
        ],
        "model_aliases": [
            {"alias": "claude-haiku-4-5", "profile_id": "default", "role": "fast_tool", "enabled": True},
            {"alias": "claude-sonnet-4-6", "profile_id": "default", "role": "main", "enabled": True},
            {"alias": "claude-opus-4-7", "profile_id": "default", "role": "large", "enabled": True},
            {
                "alias": "claude-3-5-haiku-latest",
                "profile_id": "default",
                "role": "fast_tool",
                "enabled": True,
            },
            {
                "alias": "claude-3-5-haiku-20241022",
                "profile_id": "default",
                "role": "fast_tool",
                "enabled": True,
            },
            {
                "alias": "claude-3-7-sonnet-latest",
                "profile_id": "default",
                "role": "main",
                "enabled": True,
            },
            {
                "alias": "claude-sonnet-4-5",
                "profile_id": "default",
                "role": "main",
                "enabled": True,
            },
            {
                "alias": "claude-opus-4-1",
                "profile_id": "default",
                "role": "large",
                "enabled": True,
            },
            {
                "alias": "super-main",
                "profile_id": "default",
                "role": "main",
                "enabled": True,
            },
            {
                "alias": "super-verifier",
                "profile_id": "default",
                "role": "verifier",
                "enabled": True,
            },
        ],
    }
