# Super DeepSeek 本地增强网关：整体架构 Plan

## 0. 项目定位

**Super DeepSeek** 不是聊天壳，也不是“多 agent 圆桌会议”。它是一个本地 AI harness gateway：

> 把任意 OpenAI-compatible / Anthropic-compatible 模型，包装成一个可观测、可路由、可扩展、能接 Claude Code 的本地增强端点。

第一阶段重点不是让它显得很玄，而是让它**稳定、透明、好配置、好 debug**。

用户理想路径：

```bash
git clone <repo>
cd super-deepseek
docker compose up
# 或 pnpm/python 一键启动
```

然后打开：

```text
http://127.0.0.1:8787
```

在面板里填：

```text
Base URL
API Key
Model
```

点击测试连接，复制 Claude Code / OpenAI SDK 的环境变量，把本地端口接进现有客户端。

---

## 1. 核心目标

### 1.1 必须做到

1. **同一个本地端口**
   - `/` 是 Dashboard
   - `/api/*` 是 Dashboard 后端 API
   - `/v1/messages` 是 Anthropic-compatible endpoint，给 Claude Code 用
   - `/openai/v1/*` 是 OpenAI-compatible endpoint，给 Cursor / OpenAI SDK / Open WebUI 用
   - 也可以兼容 `/v1/chat/completions`，但内部推荐 OpenAI 客户端用 `/openai/v1`

2. **不限定 DeepSeek**
   - DeepSeek 只是默认主脑之一
   - 用户可以填 Qwen、Kimi、OpenRouter、LiteLLM 支持的模型、本地 vLLM / Ollama 等
   - 项目内部使用 `profile` 和 `role`，不要把架构写死成 DeepSeek-only

3. **借用 LiteLLM**
   - 不自己写 provider 兼容地狱
   - LiteLLM 负责上游模型调用、provider adapter、fallback、cost tracking 的一部分能力
   - Super DeepSeek 自己负责：Claude Code 兼容层、model alias、trace、sanitizer、harness pipeline、evidence packet

4. **Claude Code 兼容**
   - 接受并暴露 Claude 风格模型名：`opus` / `sonnet` / `haiku`
   - 尤其必须保留 `haiku` alias，因为 Claude Code 里 fast/tool/small model 逻辑经常依赖它
   - 外部看到的是 Claude-like alias，内部映射到用户配置的真实上游模型

5. **处理 `x-anthropic-billing-header` / `cch` 随机值**
   - Claude Code 可能在 system prompt 第一行塞入类似 `x-anthropic-billing-header` 的内容
   - 其中 `cch=XXXXX` 每次随机，会让第三方上游的 prefix cache 全废
   - 必须在转发给非 Anthropic 上游前 strip 或 canonicalize
   - 必须在计算 cache key 之前处理
   - 必须在日志里标记已处理，但不要把随机 `cch` 原样展示成可搜索文本

6. **可观测**
   - 每个请求都要有 trace
   - 能看 incoming request、normalized request、sanitized request、upstream payload、streaming response、token、cost、latency、错误
   - 能 Replay
   - 能 Export JSON / Markdown / HAR-like data

---

## 2. 非目标

第一版不要做这些：

- 不做一个完整聊天产品
- 不做云端 SaaS
- 不做十几个 agent 自由聊天
- 不做复杂记忆系统
- 不做一开始就全 MCP 化
- 不承诺“完美模拟 Anthropic”
- 不把 Claude-like model name 当成身份伪装；它只是本地兼容 alias

第一版真正要做的是：

> 一个稳定的本地透明代理，加上 Claude Code 兼容层和可扩展 harness 骨架。

---

## 3. 推荐技术栈

### 3.1 后端

推荐：

```text
Python + FastAPI + Uvicorn
```

理由：

- LiteLLM 是 Python 生态，用 Python 后端更自然
- SSE / streaming 比较好处理
- 后续接 OCR、PDF parser、code runner、docling、PaddleOCR、Qwen-VL worker 都方便
- 可以一个进程同时 serve API 和前端静态文件

### 3.2 模型调用层

推荐：

```text
LiteLLM as internal model gateway
```

两种接法：

1. **Library 模式**
   - 后端直接调用 LiteLLM Python API
   - 好处：部署简单，一个进程
   - 坏处：和 LiteLLM 内部变更耦合更高

2. **Sidecar Proxy 模式**
   - Super DeepSeek 跑在 `:8787`
   - LiteLLM proxy 跑在内部端口，例如 `:4000`
   - Super DeepSeek 负责兼容层、trace、sanitizer，再转给 LiteLLM
   - 好处：边界清楚
   - 坏处：部署稍复杂

MVP 建议先用 **Library 模式**，后面保留抽象接口，允许切换成 sidecar。

### 3.3 前端

推荐：

```text
React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react + Recharts
```

前端定位是本地开发者工具，不是营销官网。界面要像“本地控制台 + 网络抓包工具 + 模型网关配置台”。

### 3.4 存储

MVP：

```text
SQLite + JSON blob
```

- `config.db`：profiles、providers、aliases、settings
- `traces.db` 或同库单表：请求索引、trace metadata
- 大 payload 可以落 JSONL 文件，DB 存路径和索引

后续：

- 支持 log retention policy
- 支持一键清空 trace
- 支持导入导出配置

### 3.5 Secrets

默认：

- API key 存本地
- UI 中只显示尾号
- trace 中永远 redaction

可选增强：

- `.env` 引用
- OS keychain
- 本地加密 SQLite

---

## 4. 高层架构

```text
Claude Code / Cursor / SDK / Open WebUI
        │
        ▼
Local Gateway :8787
        │
        ├── Dashboard UI             GET /
        ├── Dashboard API            /api/*
        ├── Anthropic Adapter        /v1/messages
        └── OpenAI Adapter           /openai/v1/*
        │
        ▼
Ingress Layer
        │
        ├── Local API key auth
        ├── Request capture
        ├── Secret redaction
        └── Trace ID creation
        │
        ▼
Protocol Normalizer
        │
        ├── Anthropic Messages → InternalRequest
        └── OpenAI Chat/Responses → InternalRequest
        │
        ▼
Claude Code Compatibility Layer
        │
        ├── Model alias resolver
        ├── Haiku/Sonnet/Opus alias preservation
        ├── x-anthropic-billing-header sanitizer
        ├── Prompt cache canonicalizer
        └── Tool schema pass-through / normalization
        │
        ▼
Harness Runtime
        │
        ├── Mode: passthrough / observe / augment / strict
        ├── Router
        ├── Specialist workers
        ├── Evidence Packet Store
        └── Verifier
        │
        ▼
LiteLLM Client
        │
        ├── DeepSeek
        ├── Qwen
        ├── Kimi
        ├── OpenRouter
        ├── local vLLM
        └── other providers
        │
        ▼
Response Adapter
        │
        ├── Stream transform
        ├── Protocol-specific output
        ├── Error normalization
        └── Final trace write
        │
        ▼
Client
```

---

## 5. Route Design

### 5.1 Dashboard

```text
GET  /
GET  /assets/*
```

### 5.2 Dashboard API

```text
GET    /api/health
GET    /api/config
POST   /api/config
POST   /api/test-connection

GET    /api/providers
POST   /api/providers
PATCH  /api/providers/:id
DELETE /api/providers/:id

GET    /api/profiles
POST   /api/profiles
PATCH  /api/profiles/:id
DELETE /api/profiles/:id

GET    /api/aliases
POST   /api/aliases
PATCH  /api/aliases/:id
DELETE /api/aliases/:id

GET    /api/traces
GET    /api/traces/:trace_id
POST   /api/traces/:trace_id/replay
GET    /api/traces/:trace_id/export

GET    /api/logs/stream
POST   /api/logs/clear
```

### 5.3 Anthropic-compatible API

Claude Code 推荐配置：

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export ANTHROPIC_API_KEY="sk-superds-local-xxxxx"
```

需要支持：

```text
POST /v1/messages
POST /v1/messages/count_tokens
GET  /v1/models
```

`/v1/models` 返回本地 Claude-like aliases，例如：

```json
{
  "data": [
    { "id": "claude-3-5-haiku-latest", "type": "model" },
    { "id": "claude-3-7-sonnet-latest", "type": "model" },
    { "id": "claude-sonnet-4-5", "type": "model" },
    { "id": "claude-opus-4-1", "type": "model" }
  ]
}
```

注意：这些只是**本地兼容 alias**，实际映射由 profile 决定。

### 5.4 OpenAI-compatible API

推荐配置：

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8787/openai/v1"
export OPENAI_API_KEY="sk-superds-local-xxxxx"
```

需要支持：

```text
POST /openai/v1/chat/completions
POST /openai/v1/responses
GET  /openai/v1/models
```

可以额外兼容：

```text
POST /v1/chat/completions
```

但为了避免和 Anthropic `/v1/*` 语义混乱，文档中推荐 OpenAI 客户端使用 `/openai/v1`。

---

## 6. Internal Request Schema

所有协议进入后都转成统一内部结构，不要让 OpenAI / Anthropic 格式在系统里到处乱跑。

```ts
type InternalRequest = {
  traceId: string
  clientProtocol: "anthropic" | "openai"
  clientName?: "claude-code" | "cursor" | "openai-sdk" | "unknown"

  incomingModel: string
  resolvedProfileId?: string
  resolvedRole?: "main" | "fast_tool" | "large" | "vision" | "verifier"

  system: ContentBlock[]
  messages: InternalMessage[]
  tools?: InternalTool[]

  stream: boolean

  generation: {
    maxTokens?: number
    temperature?: number
    topP?: number
    stop?: string[]
  }

  metadata: {
    originalHeaders?: Record<string, string>
    sanitized?: SanitizationReport
    cache?: CacheReport
    rawRequestRef?: string
  }
}

type ContentBlock =
  | { type: "text"; text: string }
  | { type: "image"; mediaType: string; dataRef: string }
  | { type: "tool_result"; toolUseId: string; content: unknown }

type InternalMessage = {
  role: "user" | "assistant" | "tool" | "system"
  content: ContentBlock[]
}

type SanitizationReport = {
  billingHeaderDetected: boolean
  billingHeaderAction: "none" | "stripped" | "canonicalized" | "passed_through"
  cchRedacted: boolean
}
```

---

## 7. Runtime Pipeline

### Step 1 — Ingress

输入：

- HTTP request
- headers
- body

动作：

- 验证本地 API key
- 创建 `trace_id`
- 写入 raw request ref
- redaction：API keys、authorization header、cookies 等永远不进可搜索日志

输出：

- `RawRequestEnvelope`

---

### Step 2 — Protocol Normalization

把不同协议转成 `InternalRequest`。

必须支持：

- Anthropic Messages API
- OpenAI Chat Completions
- OpenAI Responses API 可后置，但接口预留

---

### Step 3 — Claude Code Compatibility Layer

这是项目第一版最重要的“恶心问题处理层”。

#### 3.1 Model Alias Resolver

问题：

Claude Code 对非自家模型可能会出 bug，它可能用 model name 判断某些行为。尤其 `haiku` 常被当作 fast/tool/small model，如果没有对应名字，可能会卡住或退化。

策略：

- 本地端点必须接受 Claude-like model names
- UI 必须允许用户编辑 alias
- 默认必须包含 haiku / sonnet / opus 几类 alias
- `/v1/models` 必须暴露这些 alias
- incoming model name 不直接传给上游，而是映射到 profile role

示例：

```yaml
model_aliases:
  - alias: claude-3-5-haiku-latest
    role: fast_tool
    target_profile: default
    target_model_ref: deepseek_fast

  - alias: claude-3-7-sonnet-latest
    role: main
    target_profile: default
    target_model_ref: deepseek_main

  - alias: claude-sonnet-4-5
    role: main
    target_profile: default
    target_model_ref: deepseek_main

  - alias: claude-opus-4-1
    role: large
    target_profile: default
    target_model_ref: qwen_max_or_deepseek_reasoner
```

注意：

- alias 是兼容名，不是身份声明
- UI 里要清楚显示：`Incoming model → Actual upstream model`
- 如果没有 haiku alias，Dashboard 要显示红色 warning：`Claude Code may break or stall without a Haiku-compatible alias.`

#### 3.2 Billing Header Sanitizer

问题：

Claude Code 可能把类似下面的随机内容塞进 system prompt 第一行：

```text
x-anthropic-billing-header: ... cch=RANDOM_VALUE ...
```

`cch` 每次随机。对 Anthropic 自家服务器可能是用户隔离 / billing / cache 相关机制，但转到第三方上游时，它会让 prompt prefix 每次不同，导致 prefix cache 全废。

策略：

- 只检查**第一条 system text 的第一行**
- 也顺手检查真实 HTTP header 中是否存在 `x-anthropic-billing-header`
- 默认策略：`strip_for_non_anthropic_upstream`
- 可选策略：
  - `pass_through`
  - `strip`
  - `canonicalize`

推荐默认：

```yaml
claude_code_compat:
  billing_header_policy: strip_for_non_anthropic_upstream
```

处理规则：

```text
if upstream_provider != "anthropic":
  remove first system line if it matches x-anthropic-billing-header
  remove x-anthropic-billing-header HTTP header if present
else:
  pass through by default, unless user explicitly enables strip
```

也可以支持 canonicalize：

```text
x-anthropic-billing-header: cch=<stable-redacted>
```

但对第三方 cache 来说，**strip 通常更干净**。

伪代码：

```python
BILLING_HEADER_RE = re.compile(
    r"(?i)^x-anthropic-billing-header\s*:\s*.*\bcch\s*=\s*[^;\s,]+.*$"
)

def sanitize_system_first_line(system_text: str, policy: str) -> tuple[str, SanitizationReport]:
    lines = system_text.splitlines()
    if not lines:
        return system_text, report_none()

    first = lines[0].strip()
    if not BILLING_HEADER_RE.match(first):
        return system_text, report_none()

    if policy == "pass_through":
        return system_text, report_passed_through()

    if policy == "canonicalize":
        lines[0] = "x-anthropic-billing-header: cch=<stable-redacted>"
        return "\n".join(lines), report_canonicalized()

    # default strip
    return "\n".join(lines[1:]).lstrip("\n"), report_stripped()
```

要求：

- 必须在 cache key 计算前运行
- 必须在转发给上游前运行
- trace 中显示：
  - detected: yes/no
  - action: stripped/canonicalized/pass_through
  - cch: redacted
- 不要在普通用户内容里全局搜索删除，避免误伤

---

### Step 4 — Harness Mode

运行模式分四档：

```text
Pass-through
  只转发，只做兼容和日志。

Observe
  转发 + trace + token/cost/latency + sanitizer report。

Augment
  调用副手，生成 evidence packet，然后注入主模型上下文。

Strict
  Augment + verifier + policy checks + 更严格的工具权限。
```

MVP 默认：

```text
Observe
```

原因：一开始先把代理和可观测做稳，不急着缝器官。

---

### Step 5 — Router

Router 不应该一开始就做成 LLM 自由判断。先用规则：

```text
if request contains image:
  call vision_ocr worker

if request contains file:
  call doc_parser worker

if user asks for web/current info:
  call search worker

if tools/code execution requested:
  call code_runner worker

if mode == strict:
  call verifier before final
```

后续再加 LLM router。

---

### Step 6 — Specialist Workers

副手只返回 `EvidencePacket`，不写最终回答。

```ts
type EvidencePacket = {
  id: string
  type:
    | "vision_observation"
    | "ocr_result"
    | "document_parse"
    | "web_search"
    | "code_execution"
    | "verification"
    | "memory"

  source: string
  content: unknown
  confidence?: number
  uncertainties?: string[]
  citations?: SourceRef[]
  createdAt: string
}
```

示例：

```json
{
  "id": "ev_01",
  "type": "ocr_result",
  "source": "uploaded_image_001",
  "content": {
    "text": "input $0.435 / output $0.87",
    "layout": "pricing table"
  },
  "confidence": 0.88,
  "uncertainties": [
    "small footer text may be truncated"
  ]
}
```

主模型只吃 evidence packet，不吃副手散文。

---

### Step 7 — LiteLLM Call

内部统一用 LiteLLM 调用上游：

```text
InternalRequest
  ↓
ResolvedModelCall
  ↓
LiteLLM
  ↓
Provider response
```

`ResolvedModelCall` 里包括：

```ts
type ResolvedModelCall = {
  providerId: string
  litellmModel: string
  apiBase: string
  apiKeyRef: string
  actualModelName: string
  stream: boolean
  payload: unknown
}
```

不要让客户端传进来的 `claude-...haiku...` 直接污染上游 payload。它只是 alias。

---

### Step 8 — Response Adapter

负责：

- 把 LiteLLM / 上游 response 转回客户端协议
- 支持 SSE streaming
- 错误归一化
- 写 final trace
- 不泄露真实 upstream API key
- 尽量保留 Claude Code 需要的 tool_use / tool_result 结构

---

## 8. Config Schema

示例：

```yaml
server:
  host: 127.0.0.1
  port: 8787
  public_base_url: http://127.0.0.1:8787

security:
  local_api_key: sk-superds-local-change-me
  bind_localhost_only: true
  redact_secrets_in_logs: true

runtime:
  mode: observe
  default_profile: default
  trace_retention_days: 7

claude_code_compat:
  enabled: true
  billing_header_policy: strip_for_non_anthropic_upstream
  expose_claude_aliases: true
  require_haiku_alias: true

providers:
  - id: deepseek
    name: DeepSeek
    protocol: openai
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY

  - id: qwen
    name: Qwen
    protocol: openai
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: QWEN_API_KEY

models:
  - id: deepseek_main
    provider_id: deepseek
    litellm_model: openai/deepseek-chat
    actual_model: deepseek-chat
    role: main

  - id: deepseek_fast
    provider_id: deepseek
    litellm_model: openai/deepseek-chat
    actual_model: deepseek-chat
    role: fast_tool

  - id: qwen_large
    provider_id: qwen
    litellm_model: openai/qwen-max
    actual_model: qwen-max
    role: large

profiles:
  - id: default
    name: Default
    main_model: deepseek_main
    fast_tool_model: deepseek_fast
    large_model: qwen_large
    verifier_model: deepseek_main

model_aliases:
  - alias: claude-3-5-haiku-latest
    profile_id: default
    role: fast_tool

  - alias: claude-3-7-sonnet-latest
    profile_id: default
    role: main

  - alias: claude-sonnet-4-5
    profile_id: default
    role: main

  - alias: claude-opus-4-1
    profile_id: default
    role: large

  - alias: super-main
    profile_id: default
    role: main
```

---

## 9. Trace Schema

```ts
type TraceRecord = {
  traceId: string
  startedAt: string
  endedAt?: string

  clientProtocol: "anthropic" | "openai"
  clientName?: string

  incomingModel: string
  resolvedProfileId: string
  resolvedRole: string
  upstreamProviderId: string
  upstreamModel: string

  status: "streaming" | "success" | "error" | "cancelled"

  usage?: {
    inputTokens?: number
    outputTokens?: number
    cacheReadTokens?: number
    cacheWriteTokens?: number
    estimatedCostUsd?: number
  }

  latencyMs?: number

  sanitizer: {
    billingHeaderDetected: boolean
    billingHeaderAction: string
  }

  steps: TraceStep[]
}

type TraceStep = {
  id: string
  name: string
  type:
    | "ingress"
    | "normalize"
    | "compat"
    | "sanitize"
    | "route"
    | "worker"
    | "litellm_call"
    | "response_adapter"
    | "error"

  startedAt: string
  endedAt?: string
  status: "success" | "error" | "skipped"

  inputRef?: string
  outputRef?: string
  summary?: string
  error?: string
}
```

Dashboard trace timeline 按 `steps` 展示。

---

## 10. Cache Strategy

目标不是自己实现复杂 KV cache，而是**不要破坏上游 prefix cache**。

必须做：

1. 移除 / 规范化随机 billing header
2. 避免把 volatile metadata 放进 system prompt 前缀
3. 工具 schema 顺序稳定化
4. system prompt canonicalization
5. profile 里显示 cache stability warnings

建议 UI 展示：

```text
Cache Stability
- Billing header stripped: yes
- System prefix stable: yes
- Tool schema order stable: yes
- Volatile timestamp detected: no
```

---

## 11. Frontend Pages

### 11.1 Setup Wizard

用户第一次打开：

1. 选择目标：
   - Claude Code
   - OpenAI SDK
   - Both
2. 填 upstream：
   - Provider name
   - Base URL
   - API key
   - Model
3. Test connection
4. 生成本地配置：
   - Claude Code env
   - OpenAI env
5. Go to Dashboard

### 11.2 Dashboard Overview

显示：

- Server status
- Local port
- Current runtime mode
- Requests today
- Success/error rate
- Token usage
- Estimated cost
- Cache sanitizer hits
- Active profile

### 11.3 Providers & Profiles

显示：

- Providers list
- Profiles
- Role mapping：
  - main
  - fast_tool
  - large
  - verifier
  - vision
- Test buttons

### 11.4 Claude Code Compatibility

重点页面：

- Claude aliases table
- Haiku alias status
- `/v1/models` preview
- Copy env vars
- Compatibility checklist
- Billing header sanitizer settings

### 11.5 Trace Logs

左侧列表：

- time
- client
- incoming model
- resolved upstream
- status
- tokens
- cost
- latency
- sanitizer badge

右侧 detail：

- Timeline
- Raw request
- Normalized request
- Sanitized prompt
- Upstream payload
- Response
- Replay
- Export

### 11.6 Settings / Security

- local API key
- bind localhost only
- log retention
- redact secrets
- clear traces
- export/import config

---

## 12. Project Structure

```text
super-deepseek/
  README.md
  docker-compose.yml
  .env.example

  backend/
    pyproject.toml
    app/
      main.py

      api/
        dashboard.py
        health.py

      adapters/
        anthropic_in.py
        anthropic_out.py
        openai_in.py
        openai_out.py

      compat/
        claude_code.py
        model_alias.py
        billing_header_sanitizer.py
        cache_canonicalizer.py

      runtime/
        pipeline.py
        router.py
        modes.py
        evidence.py
        workers.py

      model_gateway/
        litellm_client.py
        resolved_call.py

      store/
        sqlite.py
        trace_store.py
        config_store.py
        secret_redaction.py

      schemas/
        internal_request.py
        trace.py
        config.py

      tests/
        test_billing_header_sanitizer.py
        test_alias_resolver.py
        test_anthropic_adapter.py
        test_openai_adapter.py
        test_streaming.py

  frontend/
    package.json
    src/
      App.tsx
      main.tsx
      api/
      components/
      pages/
      styles/

  docs/
    architecture.md
    claude-code-compat.md
    config.md
```

---

## 13. MVP Roadmap

### Phase 0 — Skeleton

目标：项目能启动，面板能打开。

- FastAPI server
- React static serve
- SQLite init
- `/api/health`
- config read/write
- local API key generation

完成标准：

```text
git clone → run → open http://127.0.0.1:8787
```

---

### Phase 1 — LiteLLM Pass-through

目标：能转发 OpenAI-compatible 请求。

- Provider config
- Test connection
- LiteLLM call
- `/openai/v1/chat/completions`
- streaming support
- basic trace

完成标准：

```text
OPENAI_BASE_URL=http://127.0.0.1:8787/openai/v1
```

能正常请求上游模型。

---

### Phase 2 — Claude Code Compatibility

目标：Claude Code 能接入本地端点。

- `/v1/messages`
- Anthropic → InternalRequest
- InternalRequest → LiteLLM/OpenAI-compatible upstream
- Claude-like model aliases
- `/v1/models`
- haiku alias warning
- billing header sanitizer
- trace detail

完成标准：

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-superds-local-xxxxx
```

Claude Code 可以通过本地端点跑，且 trace 能看到 alias 和 sanitizer 行为。

---

### Phase 3 — Trace & Replay

目标：这个工具本身先变成解剖镜。

- Timeline UI
- request/response payload viewer
- sanitizer diff
- stream reconstruction
- replay
- export JSON / Markdown

完成标准：

用户能复现一次 Claude Code 请求，并看到随机 `cch` 已经被处理。

---

### Phase 4 — Harness Augment

目标：开始有 Super DeepSeek 的味道。

- Worker interface
- Evidence packet schema
- Router
- Vision/OCR worker MVP
- Doc parser MVP

完成标准：

图片/PDF 输入能先被副手转换成 evidence packet，再交给主模型回答。

---

### Phase 5 — Verifier & Strict Mode

目标：让系统能自查。

- verifier worker
- final answer check
- evidence support check
- code/log error check

完成标准：

Strict mode 下，主模型回答前必须经过 verifier step。

---

## 14. Test Plan

### 14.1 Billing Header Sanitizer Tests

必须覆盖：

1. 第一行是 billing header，能 strip
2. 第一行是 billing header，能 canonicalize
3. 第一行不是 billing header，不处理
4. billing header 出现在用户消息里，不处理
5. system prompt 第一行被 strip 后，剩余内容保持不变
6. `cch` 随机值不进入 cache key
7. non-Anthropic upstream 默认 strip
8. Anthropic upstream 默认 pass-through，除非用户强制 strip

### 14.2 Alias Resolver Tests

必须覆盖：

1. haiku alias → fast_tool role
2. sonnet alias → main role
3. opus alias → large role
4. unknown Claude-like name → fallback policy
5. no haiku alias → Dashboard warning
6. `/v1/models` 返回 alias 而不是真实上游模型名

### 14.3 Streaming Tests

必须覆盖：

1. Anthropic streaming output
2. OpenAI streaming output
3. 上游报错时正确转成客户端协议错误
4. client disconnect 时取消上游请求
5. trace 标记 cancelled

---

## 15. 安全与隐私

默认策略：

- 只监听 `127.0.0.1`
- 本地 API key 必须启用
- Dashboard 不显示完整 upstream API key
- Trace 默认 redaction
- Raw payload export 前弹窗提醒
- 不做遥测
- 不自动上传日志

危险操作：

- 开启 `0.0.0.0` 监听
- 关闭 API key
- 导出 raw trace

UI 必须显眼提示。

---

## 16. 最小可用文档

README 第一屏只放最短路径：

```bash
git clone <repo>
cd super-deepseek
cp .env.example .env
docker compose up
open http://127.0.0.1:8787
```

然后：

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export ANTHROPIC_API_KEY="sk-superds-local-xxxxx"
claude
```

不要让用户先读完架构论文再启动。

---

## 17. 一句话原则

> Super DeepSeek 的核心不是“多模型堆料”，而是：本地兼容端点 + 可观测 trace + 稳定 alias + cache-safe sanitizer + 可插拔 specialist workers。

第一版把骨头长正。器官可以后面慢慢缝。
