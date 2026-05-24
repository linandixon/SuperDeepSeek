# Prompt for Claude Design: Super DeepSeek Dashboard Frontend

You are a senior product designer and frontend engineer. Design and implement a polished frontend prototype for a local developer tool called **Super DeepSeek**.

## Product Summary

Super DeepSeek is a **local AI harness gateway**.

It runs on a local port, exposes Anthropic-compatible and OpenAI-compatible endpoints, and lets users route Claude Code / Cursor / SDK requests through a local dashboard. Users configure upstream models such as DeepSeek, Qwen, OpenRouter, Kimi, local vLLM, or any OpenAI-compatible model.

The frontend is not a chat app and not a marketing website. It is a **local control panel / observability dashboard / compatibility console**.

Think: local proxy dashboard + request inspector + model routing control panel.

## Tech Requirements

Build a frontend-only prototype with mock data.

Use:

- React
- TypeScript
- Tailwind CSS
- shadcn/ui style components
- lucide-react icons
- Recharts for small metrics charts if useful

Do not require a real backend. Use mocked local state and fake API calls.

The final UI should feel production-ready, compact, technical, and easy to operate.

## Visual Style

Preferred style:

- Developer tool, not SaaS landing page
- Dark mode first, but clean enough for light mode later
- Dense but readable
- Slight glass/terminal feel, but not overdesigned
- Use cards, tabs, badges, tables, sidebars, drawers
- Status colors should be meaningful
- Avoid big empty marketing hero sections
- Make it feel like a tool you keep open while Claude Code is running

Tone:

- Precise
- Calm
- Slightly sharp
- Not cute
- Not corporate

## Main User Flow

A user should be able to:

1. Open `http://127.0.0.1:8787`
2. See server status
3. Configure one upstream provider:
   - Provider name
   - Base URL
   - API key
   - Model
4. Test connection
5. Configure model aliases for Claude Code:
   - Haiku alias
   - Sonnet alias
   - Opus alias
6. Copy environment variables for Claude Code
7. Run Claude Code through the local endpoint
8. Watch request logs and trace details
9. See whether `x-anthropic-billing-header` / random `cch` was stripped or canonicalized
10. Replay or export a trace

## Navigation

Create a left sidebar with these sections:

1. Overview
2. Setup
3. Providers
4. Profiles
5. Claude Code
6. Traces
7. Sanitizer & Cache
8. Settings

The top bar should show:

- Server status: Online / Offline
- Local port: `127.0.0.1:8787`
- Runtime mode: Pass-through / Observe / Augment / Strict
- Active profile
- Small button: Copy Local Env
- Small button: Clear Logs

## Page 1: Overview

Show summary cards:

- Requests today
- Success rate
- Avg latency
- Input tokens
- Output tokens
- Estimated cost
- Cache-safe requests
- Sanitized billing headers

Include a small line chart for request volume and a compact table for recent requests.

Recent requests table columns:

- Time
- Client
- Incoming model
- Resolved upstream
- Status
- Latency
- Tokens
- Sanitizer badge

Example rows:

- Client: Claude Code
- Incoming model: `claude-3-5-haiku-latest`
- Upstream: `deepseek-chat`
- Status: Success
- Sanitizer: `cch stripped`

## Page 2: Setup Wizard

Make this page friendly but not fluffy.

Steps:

1. Choose target client:
   - Claude Code
   - OpenAI SDK
   - Both

2. Configure upstream provider:
   - Provider type dropdown: DeepSeek, Qwen, OpenRouter, Kimi, Custom OpenAI-compatible
   - Base URL input
   - API key input with masked display
   - Model input
   - Test Connection button

3. Configure local endpoint:
   - Local host: `127.0.0.1`
   - Port: `8787`
   - Local API key: generated, masked, copy button

4. Copy env vars:
   - Claude Code block
   - OpenAI SDK block

Claude Code env block example:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export ANTHROPIC_API_KEY="sk-superds-local-..."
```

OpenAI env block example:

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8787/openai/v1"
export OPENAI_API_KEY="sk-superds-local-..."
```

Include copy buttons.

## Page 3: Providers

Show providers as cards/table.

Provider fields:

- Name
- Protocol: OpenAI-compatible / Anthropic-compatible / LiteLLM
- Base URL
- API key status: configured / missing
- Default model
- Last tested
- Status: healthy / failed / unknown

Actions:

- Add Provider
- Edit
- Test
- Delete
- Duplicate

Provider form should include:

- Provider name
- Protocol
- Base URL
- API key
- Default model
- Optional LiteLLM model name
- Timeout
- Max retries

Use a modal or side drawer.

## Page 4: Profiles

Profiles map roles to actual upstream models.

Show a profile editor with these roles:

- Main model
- Fast/tool model
- Large/reasoning model
- Verifier model
- Vision model
- Fallback model

Each role maps to:

- Provider
- Model
- LiteLLM model string
- Temperature default
- Max token default

Make the active profile obvious.

Include a warning if no `fast/tool` role is configured, because Claude Code may rely on a Haiku-like small model path.

## Page 5: Claude Code Compatibility

This is the most important page.

It should explain:

> Super DeepSeek exposes Claude-like model aliases for compatibility. These aliases are mapped to your configured upstream models. This does not mean the upstream model is Anthropic; it is a local compatibility layer.

Show a **Compatibility Checklist**:

- Anthropic-compatible endpoint active
- `/v1/messages` available
- `/v1/models` available
- Haiku alias configured
- Sonnet alias configured
- Opus alias configured
- Billing header sanitizer enabled
- Streaming enabled
- Tool calls pass-through enabled

Use green/yellow/red status badges.

### Model Alias Table

Columns:

- Enabled
- Incoming alias
- Role
- Target profile
- Target upstream model
- Notes

Default aliases:

- `claude-3-5-haiku-latest` → `fast_tool`
- `claude-3-5-haiku-20241022` → `fast_tool`
- `claude-3-7-sonnet-latest` → `main`
- `claude-sonnet-4-5` → `main`
- `claude-opus-4-1` → `large`

The UI must make `haiku` visually important. If no enabled alias contains `haiku`, show a warning:

> Haiku alias missing. Claude Code may stall, misroute tool calls, or behave strangely without a small/fast Claude-like model name.

### Copy Env Vars Panel

Show copyable blocks for:

Claude Code:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export ANTHROPIC_API_KEY="sk-superds-local-..."
```

OpenAI-compatible clients:

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8787/openai/v1"
export OPENAI_API_KEY="sk-superds-local-..."
```

## Page 6: Traces

This page should feel like a request inspector.

Layout:

- Left: request list
- Right: selected trace detail

### Request List Columns

- Time
- Client
- Incoming model
- Resolved model
- Status
- Latency
- Cost
- Sanitizer badge

Filters:

- Client
- Status
- Model
- Sanitizer action
- Time range
- Search text

### Trace Detail

Use tabs:

1. Timeline
2. Incoming
3. Normalized
4. Sanitized
5. Upstream
6. Response
7. Errors

Timeline steps example:

- Ingress
- Normalize protocol
- Resolve model alias
- Strip billing header
- Route to LiteLLM
- Stream response
- Finalize trace

Each step has:

- Status
- Duration
- Summary
- Expandable payload preview

Important badges:

- `cch stripped`
- `alias resolved`
- `streaming`
- `fallback used`
- `replayed`

Buttons:

- Replay
- Export JSON
- Export Markdown
- Copy trace ID
- Delete trace

Payload viewers must show redacted secrets. Example:

```json
{
  "authorization": "Bearer sk-...redacted",
  "x-anthropic-billing-header": "cch=<redacted>"
}
```

## Page 7: Sanitizer & Cache

This page controls cache stability.

Main card:

**Claude Billing Header Sanitizer**

Explain:

> Some Claude Code requests may include a volatile `x-anthropic-billing-header` line with a random `cch` value. When forwarding to third-party upstream models, this can destroy prefix cache stability. Super DeepSeek can strip or canonicalize it before routing.

Controls:

- Policy:
  - Pass through
  - Strip for non-Anthropic upstreams
  - Always strip
  - Canonicalize
- Show detected count
- Show last action
- Show sample before/after diff

Before:

```text
x-anthropic-billing-header: cch=9f31a2...
You are Claude Code...
```

After:

```text
You are Claude Code...
```

Cache stability card:

- Stable system prefix: yes/no
- Tool schema order stable: yes/no
- Volatile timestamp detected: yes/no
- Billing header stripped: yes/no
- Estimated cache-safe rate

Include a small chart:

- Requests
- Cache-safe requests
- Sanitized requests

## Page 8: Settings

Settings groups:

### Server

- Host
- Port
- Bind localhost only
- Runtime mode:
  - Pass-through
  - Observe
  - Augment
  - Strict

### Security

- Local API key
- Rotate local key
- Redact secrets in logs
- Allow raw export
- Confirm before clearing traces

### Logs

- Retention days
- Max stored traces
- Clear all traces
- Export config
- Import config

### Advanced

- LiteLLM mode:
  - embedded
  - sidecar
- Timeout
- Retry count
- Stream buffer size
- Debug mode

## Components to Build

Please create reusable components:

- `StatusBadge`
- `MetricCard`
- `ProviderCard`
- `ProfileRoleSelector`
- `ModelAliasTable`
- `CompatibilityChecklist`
- `EnvVarCopyBlock`
- `TraceList`
- `TraceTimeline`
- `PayloadViewer`
- `SanitizerDiff`
- `RuntimeModeSelector`
- `SecretInput`
- `ConnectionTestButton`

## Mock Data

Use realistic mock data.

Example provider:

```ts
{
  id: "deepseek",
  name: "DeepSeek",
  protocol: "openai",
  baseUrl: "https://api.deepseek.com/v1",
  apiKeyStatus: "configured",
  defaultModel: "deepseek-chat",
  status: "healthy"
}
```

Example alias:

```ts
{
  id: "alias_haiku",
  enabled: true,
  alias: "claude-3-5-haiku-latest",
  role: "fast_tool",
  targetProfile: "default",
  targetModel: "deepseek-chat",
  notes: "Required for Claude Code fast/tool model compatibility"
}
```

Example trace:

```ts
{
  id: "tr_8f41a",
  time: "14:32:08",
  client: "Claude Code",
  incomingModel: "claude-3-5-haiku-latest",
  resolvedModel: "deepseek-chat",
  status: "success",
  latencyMs: 842,
  inputTokens: 18421,
  outputTokens: 612,
  costUsd: 0.0042,
  sanitizer: "cch stripped",
  steps: [
    { name: "Ingress", status: "success", durationMs: 4 },
    { name: "Normalize Anthropic request", status: "success", durationMs: 8 },
    { name: "Resolve alias", status: "success", durationMs: 2 },
    { name: "Strip billing header", status: "success", durationMs: 1 },
    { name: "Route via LiteLLM", status: "success", durationMs: 811 },
    { name: "Stream response", status: "success", durationMs: 16 }
  ]
}
```

## Interaction Requirements

- Test Connection button should simulate loading and success/error states
- Copy buttons should show copied feedback
- Alias table should allow enable/disable
- Runtime mode selector should update UI state
- Trace list should select and display trace detail
- Replay button should simulate creating a new trace
- Sanitizer policy changes should update cache stability badges
- Secret inputs should be masked by default

## Important UX Rules

1. Never show full API keys in the UI.
2. Make it obvious that Claude-like names are compatibility aliases.
3. Make the Haiku alias warning prominent.
4. Make `x-anthropic-billing-header` sanitizer visible and understandable.
5. Logs should be useful without being visually overwhelming.
6. The app should look ready for a real backend, even though it uses mock data.
7. Avoid marketing copy. This is a tool, not a launch page.

## Deliverable

Generate a complete React frontend prototype.

It should include:

- App layout
- Sidebar navigation
- All pages above
- Mock data
- Working local interactions
- Responsive layout
- Clean component structure
- No real network calls required

Make the UI polished enough that a developer can immediately understand how to connect Claude Code to this local gateway and inspect what is happening.
