// Mock data + shared utilities for Super DeepSeek dashboard
// Exposed via window for cross-script access.

const NOW = new Date();

const fmtTime = (d) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

const PROVIDERS = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    protocol: 'OpenAI 兼容',
    baseUrl: 'https://api.deepseek.com/v1',
    apiKeyStatus: 'configured',
    apiKeyMask: 'sk-************a31f',
    defaultModel: 'deepseek-chat',
    lastTested: '2 分钟前',
    latency: 412,
    status: 'healthy',
    color: '#5eead4',
    short: 'DS',
  },
  {
    id: 'qwen',
    name: 'Qwen',
    protocol: 'OpenAI 兼容',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    apiKeyStatus: 'configured',
    apiKeyMask: 'sk-************7c02',
    defaultModel: 'qwen2.5-coder-32b-instruct',
    lastTested: '14 分钟前',
    latency: 685,
    status: 'healthy',
    color: '#c084fc',
    short: 'QW',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    protocol: 'OpenAI 兼容',
    baseUrl: 'https://openrouter.ai/api/v1',
    apiKeyStatus: 'configured',
    apiKeyMask: 'sk-or-************ff21',
    defaultModel: 'anthropic/claude-3.5-sonnet',
    lastTested: '1 小时前',
    latency: 980,
    status: 'unknown',
    color: '#fb923c',
    short: 'OR',
  },
  {
    id: 'kimi',
    name: 'Kimi',
    protocol: 'OpenAI 兼容',
    baseUrl: 'https://api.moonshot.cn/v1',
    apiKeyStatus: 'missing',
    apiKeyMask: '—',
    defaultModel: 'moonshot-v1-128k',
    lastTested: '从未',
    latency: null,
    status: 'failed',
    color: '#60a5fa',
    short: 'KI',
  },
  {
    id: 'vllm-local',
    name: 'vLLM 本地',
    protocol: 'OpenAI 兼容',
    baseUrl: 'http://127.0.0.1:8000/v1',
    apiKeyStatus: 'configured',
    apiKeyMask: 'EMPTY',
    defaultModel: 'qwen2.5-32b-instruct-awq',
    lastTested: '30 秒前',
    latency: 128,
    status: 'healthy',
    color: '#4ade80',
    short: 'VL',
  },
];

const PROFILES = [
  { id: 'default', name: '默认方案', active: true, desc: 'Claude Code 主用，DeepSeek 路由' },
  { id: 'reasoning', name: '推理优先', active: false, desc: '复杂任务走 DeepSeek-R1 / Qwen QwQ' },
  { id: 'local-only', name: '纯本地', active: false, desc: '全部走 vLLM 本地实例' },
];

const ACTIVE_PROFILE_ROLES = [
  { role: 'main',     label: '主模型',     desc: '通用任务、对话、计划',                provider: 'deepseek',   model: 'deepseek-chat',                 lmStr: 'openai/deepseek-chat',          temp: 0.2, maxTokens: 8192 },
  { role: 'fast_tool',label: '快速 / 工具', desc: 'Claude Code Haiku 路径，工具调用',     provider: 'deepseek',   model: 'deepseek-chat',                 lmStr: 'openai/deepseek-chat',          temp: 0.0, maxTokens: 4096 },
  { role: 'large',    label: '大型 / 推理', desc: '长上下文、复杂推理',                  provider: 'deepseek',   model: 'deepseek-reasoner',             lmStr: 'openai/deepseek-reasoner',      temp: 0.4, maxTokens: 16384 },
  { role: 'verifier', label: '校验',       desc: '审查、二次确认',                      provider: 'qwen',       model: 'qwen2.5-coder-32b-instruct',    lmStr: 'openai/qwen2.5-coder-32b',      temp: 0.0, maxTokens: 4096 },
  { role: 'vision',   label: '视觉',       desc: '图像 / 多模态请求',                   provider: null,         model: null,                            lmStr: '',                               temp: 0.2, maxTokens: 4096 },
  { role: 'fallback', label: '兜底',       desc: '上游不可用时启用',                    provider: 'openrouter', model: 'anthropic/claude-3.5-sonnet',   lmStr: 'openrouter/claude-3.5-sonnet',  temp: 0.2, maxTokens: 8192 },
];

const ALIASES = [
  { id: 'a1', enabled: true,  alias: 'claude-3-5-haiku-latest',   role: 'fast_tool', targetProfile: 'default', targetModel: 'deepseek-chat',      notes: 'Claude Code 快速 / 工具路径必需' },
  { id: 'a2', enabled: true,  alias: 'claude-3-5-haiku-20241022', role: 'fast_tool', targetProfile: 'default', targetModel: 'deepseek-chat',      notes: '版本固定别名' },
  { id: 'a3', enabled: true,  alias: 'claude-3-7-sonnet-latest',  role: 'main',      targetProfile: 'default', targetModel: 'deepseek-chat',      notes: '主模型路径' },
  { id: 'a4', enabled: true,  alias: 'claude-sonnet-4-5',         role: 'main',      targetProfile: 'default', targetModel: 'deepseek-chat',      notes: '新版命名' },
  { id: 'a5', enabled: true,  alias: 'claude-opus-4-1',           role: 'large',     targetProfile: 'default', targetModel: 'deepseek-reasoner', notes: '映射到推理模型' },
  { id: 'a6', enabled: false, alias: 'claude-3-opus-20240229',    role: 'large',     targetProfile: 'default', targetModel: 'deepseek-reasoner', notes: '已弃用，默认关闭' },
];

const COMPAT = [
  { ok: 'ok',   label: 'Anthropic 兼容入口已激活',     desc: '/v1/messages /v1/models 已挂载到本地端口' },
  { ok: 'ok',   label: '/v1/messages 可用',          desc: '支持流式与工具调用透传' },
  { ok: 'ok',   label: '/v1/models 可用',            desc: '返回所有已启用别名' },
  { ok: 'ok',   label: 'Haiku 别名已配置',           desc: '2 个 haiku 别名启用，映射到 fast_tool' },
  { ok: 'ok',   label: 'Sonnet 别名已配置',          desc: '2 个 sonnet 别名启用' },
  { ok: 'ok',   label: 'Opus 别名已配置',            desc: '1 个 opus 别名启用，映射到 large 角色' },
  { ok: 'ok',   label: '账单头清洗已启用',           desc: '非 Anthropic 上游：strip cch / x-anthropic-billing-header' },
  { ok: 'ok',   label: '流式响应已启用',             desc: 'SSE / text/event-stream' },
  { ok: 'warn', label: '工具调用透传：部分降级',     desc: 'OpenAI-tool ↔ Anthropic-tool 字段转换中，复杂 schema 可能丢失字段' },
];

const SANITIZER_BEFORE = [
  { type: 'normal', text: 'POST /v1/messages HTTP/1.1' },
  { type: 'normal', text: 'host: 127.0.0.1:8787' },
  { type: 'normal', text: 'authorization: Bearer sk-superds-local-...' },
  { type: 'normal', text: 'anthropic-version: 2023-06-01' },
  { type: 'del',    text: 'x-anthropic-billing-header: cch=9f31a2bd7c4e1f8a0b6d3e' },
  { type: 'del',    text: 'x-anthropic-billing-request: a3f12c-9e' },
  { type: 'normal', text: '' },
  { type: 'normal', text: '{"model":"claude-3-5-haiku-latest","stream":true,' },
  { type: 'normal', text: ' "system":"You are Claude Code, Anthropic..."}'},
];
const SANITIZER_AFTER = [
  { type: 'normal', text: 'POST /v1/chat/completions HTTP/1.1' },
  { type: 'add',    text: 'host: api.deepseek.com' },
  { type: 'add',    text: 'authorization: Bearer sk-************a31f' },
  { type: 'normal', text: '' },
  { type: 'dim',    text: '# cch / billing header removed' },
  { type: 'normal', text: '' },
  { type: 'normal', text: '{"model":"deepseek-chat","stream":true,' },
  { type: 'normal', text: ' "messages":[{"role":"system","content":"You are Claude Code..."}]}' },
];

// Generate ~40 traces
function makeTraces() {
  const clients = ['Claude Code', 'Claude Code', 'Claude Code', 'OpenAI SDK', 'curl', 'Cursor'];
  const incomingModels = [
    'claude-3-5-haiku-latest',
    'claude-3-5-haiku-latest',
    'claude-3-5-haiku-20241022',
    'claude-sonnet-4-5',
    'claude-3-7-sonnet-latest',
    'claude-opus-4-1',
    'gpt-4o-mini',
  ];
  const resolveMap = {
    'claude-3-5-haiku-latest':   'deepseek-chat',
    'claude-3-5-haiku-20241022': 'deepseek-chat',
    'claude-sonnet-4-5':         'deepseek-chat',
    'claude-3-7-sonnet-latest':  'deepseek-chat',
    'claude-opus-4-1':           'deepseek-reasoner',
    'gpt-4o-mini':               'qwen2.5-coder-32b-instruct',
  };
  const sanitizers = ['cch stripped', 'cch stripped', 'cch stripped', '已透传', '别名解析', '别名解析'];
  const statuses   = ['success','success','success','success','success','success','success','success','success','warn','err'];

  const out = [];
  let t = new Date(NOW);
  for (let i = 0; i < 42; i++) {
    t = new Date(t.getTime() - (40 + Math.random() * 90) * 1000);
    const incoming = incomingModels[(i + (i % 3)) % incomingModels.length];
    const resolved = resolveMap[incoming];
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    const client = clients[i % clients.length];
    const inTok = 800 + Math.floor(Math.random() * 22000);
    const outTok = 100 + Math.floor(Math.random() * 1200);
    const latency = 320 + Math.floor(Math.random() * 1400);
    const cost = (inTok * 0.0000002 + outTok * 0.0000008);
    const san = incoming.startsWith('claude') ? sanitizers[Math.floor(Math.random() * 3)] : '已透传';

    out.push({
      id: 'tr_' + (0xabcdef - i * 17).toString(16).slice(-5),
      time: fmtTime(t),
      timeFull: t,
      client,
      incomingModel: incoming,
      resolvedModel: resolved,
      provider: resolved.startsWith('deepseek') ? 'deepseek' : resolved.startsWith('qwen') ? 'qwen' : 'openrouter',
      status,
      latencyMs: latency,
      inputTokens: inTok,
      outputTokens: outTok,
      costUsd: +cost.toFixed(4),
      sanitizer: san,
      streamed: Math.random() > 0.3,
      replayed: i === 7,
      fallback: i === 11,
      steps: [
        { name: '入口接收',           status: 'success', durationMs: 3 + Math.floor(Math.random() * 5),  summary: 'POST /v1/messages, content-length=' + (inTok * 4) },
        { name: '协议规范化',         status: 'success', durationMs: 5 + Math.floor(Math.random() * 8),  summary: 'Anthropic → 内部表示, system 提取 1 段, 工具 0 个' },
        { name: '解析模型别名',       status: 'success', durationMs: 1 + Math.floor(Math.random() * 3),  summary: `${incoming} → role=${incoming.includes('haiku') ? 'fast_tool' : incoming.includes('opus') ? 'large' : 'main'}` },
        { name: '清洗账单头',         status: san === '已透传' ? 'skip' : 'success', durationMs: 1, summary: san === '已透传' ? '策略 = 透传，未修改' : '剥离 x-anthropic-billing-header (cch=9f31a2...)' },
        { name: '路由到 LiteLLM',      status: status === 'err' ? 'err' : 'success', durationMs: latency - 30, summary: `${resolved} via openai 协议, stream=true` },
        { name: '流式响应',           status: status === 'err' ? 'err' : (status === 'warn' ? 'warn' : 'success'), durationMs: 12 + Math.floor(Math.random() * 24), summary: `${outTok} tokens, ${(outTok/((latency)/1000)).toFixed(0)} tok/s` },
        { name: '完成追踪',           status: 'success', durationMs: 2, summary: 'cost=$' + cost.toFixed(4) },
      ],
    });
  }
  return out;
}
const TRACES = makeTraces();

// 24h-ish line for chart
const VOLUME_24H = Array.from({ length: 48 }, (_, i) => {
  const base = 12 + Math.sin(i / 6) * 8 + (i > 30 ? 14 : 0);
  return Math.max(2, Math.round(base + (Math.random() - 0.5) * 6));
});
const CACHE_SAFE_24H = VOLUME_24H.map(v => Math.round(v * (0.72 + Math.random() * 0.2)));
const SANITIZED_24H = VOLUME_24H.map(v => Math.round(v * (0.55 + Math.random() * 0.25)));

Object.assign(window, {
  PROVIDERS, PROFILES, ACTIVE_PROFILE_ROLES, ALIASES, COMPAT,
  SANITIZER_BEFORE, SANITIZER_AFTER, TRACES, VOLUME_24H, CACHE_SAFE_24H, SANITIZED_24H,
  fmtTime,
});
