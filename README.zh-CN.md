# Super DeepSeek

[English](README.md)

Super DeepSeek 是一个本地 AI 网关，用来把 DeepSeek 和其他 OpenAI-compatible 模型接到 Claude Code、Codex CLI、OpenAI-compatible 客户端里。

它的目标很直接：让强文本/代码模型拥有更好用的 Agent 接口，包括工具调用、Responses API 兼容、思考历史透传，以及用视觉副手给纯文本模型“加眼睛”。

## 功能

- Claude Code 可用的 Anthropic-compatible `/v1/messages`
- OpenAI-compatible `/openai/v1/chat/completions`
- OpenAI Responses-compatible `/openai/v1/responses`
- Codex CLI 可用的 Responses 流式和 WebSocket
- Responses 与 OpenAI Chat 之间的工具调用历史转换
- `reasoning_content` 透传，兼容需要回传思考历史的模型
- 视觉副手：图片先交给视觉模型读取，再把文字证据交给主模型
- 本地控制台：配置 provider、模型、角色方案、trace、能力展示

## 快速开始

```bash
cp .env.example .env
python3 -m pip install -r requirements.txt
python3 -m backend.app
```

打开：

```text
http://127.0.0.1:8787
```

## 配置 Key

把上游 provider 的 key 写进 `.env`：

```bash
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
MIMO_API_KEY=
SILICONFLOW_API_KEY=
KIMI_API_KEY=
```

本地网关 key 默认是：

```bash
SUPERDS_LOCAL_API_KEY=sk-superds-local-change-me
```

如果要把服务暴露到 localhost 之外，请先改掉这个本地 key。

## 默认模型方案

内置的 `config/superds.json` 保留了一套可直接使用的默认方案：

| 角色 | 默认模型 |
| --- | --- |
| 主模型 | `deepseek-v4-pro` |
| 快速工具 / 视觉副手 | SiliconFlow 的 `Qwen/Qwen3.6-27B` |
| 大模型 / 长上下文 | `deepseek-v4-pro` |
| 审查 / 校验 | `kimi-k2.6` |
| 兜底 | OpenRouter 的 `anthropic/claude-haiku-4.5` |

你可以在控制台里继续修改 provider 和角色映射。

## Claude Code

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export ANTHROPIC_API_KEY="sk-superds-local-change-me"
```

可用别名示例：

- `claude-haiku-4-5`
- `claude-sonnet-4-6`
- `claude-opus-4-7`
- `super-main`
- `super-verifier`

这些是本地兼容别名，会被 Super DeepSeek 映射到你配置的真实上游模型。

## Codex CLI

把 SuperDS provider 写入 `~/.codex/config.toml`：

```bash
python3 scripts/install_codex_provider.py
export OPENAI_API_KEY="sk-superds-local-change-me"
```

然后运行：

```bash
codex exec --model super-main "Reply with CODEX_OK"
codex review --uncommitted
```

如果你的本机 WebSocket 环境不稳定，可以强制使用 HTTP/SSE：

```bash
python3 scripts/install_codex_provider.py --no-websockets
```

## OpenAI-Compatible 客户端

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8787/openai/v1"
export OPENAI_API_KEY="sk-superds-local-change-me"
```

可用入口：

- `GET /openai/v1/models`
- `POST /openai/v1/chat/completions`
- `POST /openai/v1/responses`
- `WS /openai/v1/responses`

## 测试

```bash
python3 -m unittest discover -s tests
```

## 说明

- 运行 trace 和视觉证据会写入 `data/`，该目录默认被 git 忽略。
- `config/superds.json` 可以提交到仓库，但真实上游 key 必须保持为空。
- 没有配置上游 key 时，服务仍然可以启动，并返回本地 mock 响应，方便先验证客户端连接。
