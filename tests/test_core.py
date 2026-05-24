import unittest
import asyncio

from backend.app.adapters import anthropic_payload, anthropic_to_openai_payload, responses_tools_to_openai
from backend.app.alias_resolver import AliasResolver
from backend.app.billing_header_sanitizer import sanitize_system_first_line
from backend.app.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from backend.app.capabilities import model_capabilities
from backend.app.defaults import default_config
from backend.app.main import ensure_provider_default_models, normalize_profile_payload, openai_to_responses_response, remove_provider_from_config, responses_body_with_cached_context
from backend.app.multimodal import detect_images, inject_evidence_into_chat_payload, make_evidence_packets, responses_input_to_messages
from backend.app.provider_presets import load_provider_presets
from backend.app.provider_router import ProviderRouter
from backend.app.reasoning_state import extract_opaque_reasoning, validate_mimo_reasoning_history
from backend.app.secret_redaction import redact_text
from backend.app.upstream import test_connection


class BillingHeaderSanitizerTests(unittest.TestCase):
    def test_strips_first_system_line_for_non_anthropic(self):
        text = "x-anthropic-billing-header: user=abc cch=random123\nYou are Claude Code."
        out, report = sanitize_system_first_line(text, "strip_for_non_anthropic_upstream", "openai")
        self.assertEqual(out, "You are Claude Code.")
        self.assertTrue(report.billingHeaderDetected)
        self.assertEqual(report.billingHeaderAction, "stripped")
        self.assertTrue(report.cchRedacted)

    def test_canonicalizes_first_system_line(self):
        text = "x-anthropic-billing-header: cch=random123\nStable prompt"
        out, report = sanitize_system_first_line(text, "canonicalize", "openai")
        self.assertEqual(out.splitlines()[0], "x-anthropic-billing-header: cch=<stable-redacted>")
        self.assertEqual(report.billingHeaderAction, "canonicalized")

    def test_ignores_non_first_line(self):
        text = "User instruction\nx-anthropic-billing-header: cch=random123"
        out, report = sanitize_system_first_line(text, "strip", "openai")
        self.assertEqual(out, text)
        self.assertFalse(report.billingHeaderDetected)

    def test_passes_through_for_anthropic_upstream_by_default(self):
        text = "x-anthropic-billing-header: cch=random123\nStable prompt"
        out, report = sanitize_system_first_line(text, "strip_for_non_anthropic_upstream", "anthropic")
        self.assertEqual(out, text)
        self.assertEqual(report.billingHeaderAction, "passed_through")


class AliasResolverTests(unittest.TestCase):
    def setUp(self):
        self.config = default_config()
        self.resolver = AliasResolver(self.config)

    def test_haiku_alias_maps_to_fast_tool(self):
        resolved = self.resolver.resolve("claude-3-5-haiku-latest")
        self.assertEqual(resolved.role, "fast_tool")
        self.assertEqual(resolved.actual_model, "deepseek-chat")

    def test_sonnet_alias_maps_to_main(self):
        resolved = self.resolver.resolve("claude-sonnet-4-5")
        self.assertEqual(resolved.role, "main")

    def test_opus_alias_maps_to_large(self):
        resolved = self.resolver.resolve("claude-opus-4-1")
        self.assertEqual(resolved.role, "large")
        self.assertEqual(resolved.actual_model, "deepseek-reasoner")

    def test_v1_models_returns_aliases_not_real_models(self):
        models = self.resolver.models_for_anthropic()["data"]
        ids = [m["id"] for m in models]
        self.assertIn("claude-3-5-haiku-latest", ids)
        self.assertNotIn("deepseek-chat", ids)

    def test_role_candidates_include_failover_queue(self):
        ids = self.resolver.model_ids_for_role("default", "fast_tool")
        self.assertEqual(ids[0], "deepseek_fast")
        self.assertIn("qwen_verifier", ids)

    def test_direct_model_name_resolves_to_model_entry(self):
        resolved = self.resolver.resolve("mimo-v2.5-pro")
        self.assertEqual(resolved.provider_id, "mimo")

    def test_profile_role_is_preserved_when_model_role_differs(self):
        resolved = self.resolver.resolve_model_id("x", "default", "main", "qwen_verifier")
        self.assertEqual(resolved.role, "main")

    def test_super_verifier_alias_maps_to_verifier(self):
        resolved = self.resolver.resolve("super-verifier")
        self.assertEqual(resolved.role, "verifier")


class AdapterTests(unittest.TestCase):
    def test_anthropic_adapter_sanitizes_before_upstream_payload(self):
        resolved = AliasResolver(default_config()).resolve("claude-3-5-haiku-latest")
        payload, report = anthropic_to_openai_payload(
            {
                "model": "claude-3-5-haiku-latest",
                "system": "x-anthropic-billing-header: cch=random\nYou are Claude Code.",
                "messages": [{"role": "user", "content": "hi"}],
            },
            {"x-anthropic-billing-header": "cch=random"},
            resolved,
            "strip_for_non_anthropic_upstream",
        )
        self.assertTrue(report.billingHeaderDetected)
        self.assertEqual(payload["messages"][0]["content"], "You are Claude Code.")
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertNotIn("max_tokens", payload)

    def test_anthropic_adapter_passes_generation_and_reasoning_options(self):
        resolved = AliasResolver(default_config()).resolve("claude-sonnet-4-6")
        payload, _ = anthropic_to_openai_payload(
            {
                "model": "claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 32000,
                "thinking": {"type": "enabled", "budget_tokens": 4096},
                "reasoning": {"effort": "high"},
                "enable_thinking": True,
                "tool_choice": {"type": "auto"},
            },
            {},
            resolved,
            "strip_for_non_anthropic_upstream",
        )
        self.assertEqual(payload["max_tokens"], 32000)
        self.assertEqual(payload["thinking"]["budget_tokens"], 4096)
        self.assertEqual(payload["reasoning"]["effort"], "high")
        self.assertTrue(payload["enable_thinking"])
        self.assertEqual(payload["tool_choice"], "auto")

    def test_anthropic_payload_preserves_anthropic_content_blocks(self):
        config = default_config()
        config["providers"].append(
            {
                "id": "anthropic",
                "name": "Anthropic",
                "protocol": "anthropic",
                "base_url": "https://api.anthropic.com/v1",
                "api_key": "",
                "default_model": "claude-3-5-sonnet-latest",
            }
        )
        config["models"].append(
            {
                "id": "claude_native",
                "provider_id": "anthropic",
                "actual_model": "claude-3-5-sonnet-latest",
                "litellm_model": "claude-3-5-sonnet-latest",
                "role": "main",
            }
        )
        resolved = AliasResolver(config).resolve_model_id("claude-x", "default", "main", "claude_native")
        body = {
            "model": "claude-x",
            "system": [{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "assistant", "content": [{"type": "thinking", "thinking": "keep", "signature": "sig"}]}],
        }
        payload, report = anthropic_payload(body, {}, resolved, "strip_for_non_anthropic_upstream")
        self.assertEqual(payload["model"], "claude-3-5-sonnet-latest")
        self.assertEqual(payload["system"], body["system"])
        self.assertEqual(payload["messages"][0]["content"][0]["type"], "thinking")
        self.assertNotIn("max_tokens", payload)
        self.assertEqual(report.billingHeaderAction, "none")

    def test_anthropic_to_openai_preserves_image_blocks(self):
        resolved = AliasResolver(default_config()).resolve("claude-3-5-haiku-latest")
        payload, _ = anthropic_to_openai_payload(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "看图"},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
                        ],
                    }
                ]
            },
            {},
            resolved,
            "strip_for_non_anthropic_upstream",
        )
        self.assertEqual(payload["messages"][0]["content"][1]["type"], "image_url")

    def test_responses_tools_convert_to_openai_chat_tools(self):
        tools = responses_tools_to_openai(
            [
                {
                    "type": "function",
                    "name": "exec_command",
                    "description": "run command",
                    "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}},
                }
            ]
        )
        self.assertEqual(tools[0]["function"]["name"], "exec_command")
        self.assertEqual(tools[0]["function"]["parameters"]["properties"]["cmd"]["type"], "string")


class RedactionTests(unittest.TestCase):
    def test_cch_value_is_not_searchable_in_trace_text(self):
        text = "x-anthropic-billing-header: cch=random-456\nbody cch=random-789"
        redacted = redact_text(text)
        self.assertNotIn("random-456", redacted)
        self.assertNotIn("random-789", redacted)


class ProviderPresetTests(unittest.TestCase):
    def test_provider_presets_load(self):
        presets = load_provider_presets()
        ids = {p["id"] for p in presets}
        self.assertIn("deepseek", ids)
        self.assertIn("ollama", ids)


class ProviderConfigTests(unittest.TestCase):
    def test_removing_provider_cleans_models_and_profile_refs(self):
        config = default_config()
        self.assertTrue(remove_provider_from_config(config, "deepseek"))
        self.assertFalse(any(p["id"] == "deepseek" for p in config["providers"]))
        self.assertFalse(any(m["provider_id"] == "deepseek" for m in config["models"]))
        model_ids = {m["id"] for m in config["models"]}
        for profile in config["profiles"]:
            for key in ["main_model", "fast_tool_model", "large_model", "verifier_model", "vision_model"]:
                if profile.get(key):
                    self.assertIn(profile[key], model_ids)

    def test_profile_payload_accepts_role_mapping(self):
        profile = normalize_profile_payload(
            {
                "id": "custom",
                "name": "Custom",
                "roles": {"main": "deepseek_main", "vision": "qwen_vision"},
            }
        )
        self.assertEqual(profile["main_model"], "deepseek_main")
        self.assertEqual(profile["vision_model"], "qwen_vision")

    def test_provider_default_model_becomes_selectable_model(self):
        config = default_config()
        config["providers"].append(
            {
                "id": "custom",
                "name": "Custom",
                "protocol": "openai",
                "base_url": "https://example.com/v1",
                "api_key": "",
                "default_model": "custom-model-1",
                "capabilities": {"vision": False, "tools": True},
            }
        )
        self.assertTrue(ensure_provider_default_models(config))
        self.assertTrue(any(m["provider_id"] == "custom" and m["actual_model"] == "custom-model-1" for m in config["models"]))


class StreamCheckTests(unittest.TestCase):
    def test_missing_key_returns_stream_check_shape(self):
        result = asyncio.run(test_connection({"id": "x", "base_url": "https://example.com/v1"}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["mode"], "stream_check")
        self.assertIn("ttfb_ms", result)

    def test_anthropic_missing_key_returns_stream_check_shape(self):
        result = asyncio.run(test_connection({"id": "x", "protocol": "anthropic", "base_url": "https://example.com/v1"}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["mode"], "stream_check")
        self.assertEqual(result["status"], "missing_api_key")


class CircuitBreakerTests(unittest.TestCase):
    def test_opens_after_failure_threshold(self):
        breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, timeout_seconds=999))
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertEqual(breaker.snapshot()["state"], "open")
        self.assertFalse(breaker.allow_request())


class ProviderRouterTests(unittest.TestCase):
    def test_fails_over_to_second_candidate(self):
        import backend.app.provider_router as router_module

        config = default_config()
        router = ProviderRouter(config)
        calls = []
        original = router_module.call_openai_chat

        async def fake_call(payload, resolved):
            calls.append(resolved.provider_id)
            if len(calls) == 1:
                raise RuntimeError("primary failed")
            return {
                "id": "chatcmpl-test",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

        router_module.call_openai_chat = fake_call
        try:
            _, resolved, attempts = asyncio.run(
                router.call_openai_chat_with_failover(
                    {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]},
                    "claude-3-5-haiku-latest",
                )
            )
        finally:
            router_module.call_openai_chat = original

        self.assertEqual(calls, ["deepseek", "qwen"])
        self.assertEqual(resolved.provider_id, "qwen")
        self.assertEqual([a["status"] for a in attempts], ["failed", "success"])

    def test_direct_model_is_first_candidate(self):
        router = ProviderRouter(default_config())
        candidates = router.resolve_candidates("mimo-v2.5-pro")
        self.assertEqual(candidates[0].provider_id, "mimo")


class CapabilityAndMultimodalTests(unittest.TestCase):
    def test_vision_model_capability_overrides_provider_default(self):
        config = default_config()
        resolved = AliasResolver(config).resolve_model_id("x", "default", "vision", "qwen_vision")
        self.assertTrue(model_capabilities(config, resolved)["vision"])

    def test_detects_anthropic_images_and_injects_evidence(self):
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "看图"},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
                    ],
                }
            ]
        }
        images = detect_images("anthropic", body)
        self.assertEqual(len(images), 1)
        packets = make_evidence_packets(images, "test")
        payload = inject_evidence_into_chat_payload({"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]}, "视觉证据")
        self.assertIn("视觉证据", payload["messages"][0]["content"])
        self.assertEqual(packets[0]["type"], "vision_observation")


class OpaqueReasoningTests(unittest.TestCase):
    def test_extracts_mimo_reasoning_content(self):
        state = extract_opaque_reasoning("openai_chat", {"messages": [{"role": "assistant", "reasoning_content": "think", "tool_calls": [{"id": "c"}]}]})
        self.assertEqual(state[0]["kind"], "reasoning_content")

    def test_mimo_requires_reasoning_content_with_tool_calls(self):
        result = validate_mimo_reasoning_history(
            {"messages": [{"role": "assistant", "tool_calls": [{"id": "c"}]}]},
            {"reasoning_state": "mimo_reasoning_content"},
        )
        self.assertFalse(result["ok"])

    def test_extracts_anthropic_thinking_block(self):
        state = extract_opaque_reasoning("anthropic", {"messages": [{"role": "assistant", "content": [{"type": "thinking", "thinking": "x", "signature": "s"}]}]})
        self.assertEqual(state[0]["kind"], "thinking")


class ResponsesAdapterTests(unittest.TestCase):
    def test_responses_input_to_messages(self):
        messages = responses_input_to_messages({"instructions": "sys", "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]})
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["content"], "hi")

    def test_responses_input_preserves_images_for_vision_route(self):
        messages = responses_input_to_messages({"input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}, {"type": "input_image", "image_url": "data:image/png;base64,abc"}]}]})
        self.assertEqual(messages[0]["content"][1]["type"], "image_url")

    def test_responses_extracts_encrypted_reasoning_request(self):
        state = extract_opaque_reasoning("openai_responses", {"include": ["reasoning.encrypted_content"], "input": []})
        self.assertEqual(state[0]["kind"], "encrypted_reasoning_requested")

    def test_responses_function_call_history_to_openai_tool_messages(self):
        messages = responses_input_to_messages(
            {
                "input": [
                    {"type": "function_call", "call_id": "call_1", "name": "exec_command", "arguments": "{\"cmd\":\"pwd\"}"},
                    {"type": "function_call_output", "call_id": "call_1", "output": "/tmp/project"},
                ]
            }
        )
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["tool_calls"][0]["function"]["name"], "exec_command")
        self.assertEqual(messages[1]["role"], "tool")
        self.assertEqual(messages[1]["tool_call_id"], "call_1")

    def test_openai_tool_calls_to_responses_function_call_items(self):
        response = openai_to_responses_response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "exec_command", "arguments": "{\"cmd\":\"pwd\"}"},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {},
            },
            "",
            "super-main",
        )
        self.assertEqual(response["output"][0]["type"], "function_call")
        self.assertEqual(response["output"][0]["call_id"], "call_1")
        self.assertEqual(response["output"][0]["name"], "exec_command")

    def test_responses_cached_previous_response_restores_tool_reasoning(self):
        class State:
            responses_cache = {
                "resp_1": {
                    "output": [{"type": "function_call", "call_id": "call_1", "name": "exec_command", "arguments": "{}"}],
                    "_superds_reasoning_content": "think",
                }
            }
            responses_call_reasoning = {}

        class App:
            state = State()

        class Request:
            app = App()

        body = responses_body_with_cached_context(Request(), {"previous_response_id": "resp_1", "input": [{"type": "function_call_output", "call_id": "call_1", "output": "ok"}]})
        messages = responses_input_to_messages(body)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["reasoning_content"], "think")
        self.assertEqual(messages[1]["role"], "tool")

    def test_responses_groups_parallel_function_calls_before_outputs(self):
        messages = responses_input_to_messages(
            {
                "input": [
                    {"type": "function_call", "call_id": "call_1", "name": "exec_command", "arguments": "{}"},
                    {"type": "function_call", "call_id": "call_2", "name": "exec_command", "arguments": "{}"},
                    {"type": "function_call_output", "call_id": "call_1", "output": "one"},
                    {"type": "function_call_output", "call_id": "call_2", "output": "two"},
                ]
            }
        )
        self.assertEqual(len(messages[0]["tool_calls"]), 2)
        self.assertEqual(messages[1]["tool_call_id"], "call_1")
        self.assertEqual(messages[2]["tool_call_id"], "call_2")


if __name__ == "__main__":
    unittest.main()
