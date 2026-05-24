// Thin API client for the static dashboard.
const SUPERDS_LOCAL_KEY = 'sk-superds-local-change-me';

async function apiJson(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail?.message || data?.detail || data?.error?.message || res.statusText);
  }
  return data;
}

function maskKey(provider) {
  if (provider.api_key) return 'sk-************configured';
  return provider.api_key_env ? `$${provider.api_key_env}` : '—';
}

function providerColor(id) {
  const colors = {
    deepseek: '#5eead4',
    qwen: '#c084fc',
    openrouter: '#fb923c',
    kimi: '#60a5fa',
    siliconflow: '#4ade80',
    litellm: '#fbbf24',
    ollama: '#a8aeb8',
    vllm: '#4ade80',
  };
  return colors[id] || '#a8aeb8';
}

function toProviderCard(provider) {
  const id = provider.id || provider.name || 'provider';
  return {
    ...provider,
    id,
    name: provider.name || id,
    protocol: provider.protocol === 'anthropic' ? 'Anthropic 兼容' : 'OpenAI 兼容',
    baseUrl: provider.base_url || provider.baseUrl || '',
    apiKeyEnv: provider.api_key_env || provider.apiKeyEnv || '',
    apiKeyStatus: provider.api_key ? 'configured' : 'missing',
    apiKeyMask: provider.apiKeyMask || maskKey(provider),
    defaultModel: provider.default_model || provider.defaultModel || '',
    lastTested: provider.last_tested || '尚未测试',
    latency: provider.latency_ms || null,
    status: provider.status || (provider.api_key ? 'unknown' : 'failed'),
    color: providerColor(id),
    short: (provider.name || id).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || 'AI',
  };
}

function fromBackendTrace(t) {
  const started = t.started_at ? new Date(t.started_at * 1000) : new Date();
  const usage = t.usage || {};
  const request = t.request || {};
  const response = t.response || {};
  const sanitizer = t.sanitizer || {};
  return {
    id: t.trace_id,
    time: window.fmtTime ? window.fmtTime(started) : started.toLocaleTimeString(),
    client: t.client_name || t.client_protocol || 'unknown',
    incomingModel: t.incoming_model || '',
    resolvedModel: t.upstream_model || '',
    status: t.status === 'error' ? 'err' : t.status,
    latencyMs: t.latency_ms || 0,
    inputTokens: usage.inputTokens || usage.input_tokens || 0,
    outputTokens: usage.outputTokens || usage.output_tokens || 0,
    costUsd: usage.estimatedCostUsd || 0,
    sanitizer: sanitizer.billingHeaderAction === 'stripped' ? 'cch stripped' : sanitizer.billingHeaderAction || '已透传',
    streamed: Boolean(request.body && request.body.stream),
    fallback: Array.isArray(request.route_attempts) && request.route_attempts.length > 1,
    steps: (t.steps || []).map(s => ({
      name: s.name,
      status: s.status === 'error' ? 'err' : s.status,
      summary: s.summary,
      durationMs: s.durationMs || 0,
    })),
    request,
    response,
    raw: t,
  };
}

window.SuperDSApi = {
  localKey: SUPERDS_LOCAL_KEY,
  async health() {
    return apiJson('/api/health');
  },
  async providers() {
    const data = await apiJson('/api/providers');
    return (data.data || []).map(toProviderCard);
  },
  async presets() {
    const data = await apiJson('/api/provider-presets');
    return data.data || [];
  },
  async traces(limit = 100) {
    const data = await apiJson(`/api/traces?limit=${limit}`);
    const rows = (data.data || []).map(fromBackendTrace);
    return rows.length ? rows : window.TRACES;
  },
  async modelCapabilities() {
    const data = await apiJson('/api/model-capabilities');
    return data.data || [];
  },
  async profiles() {
    const data = await apiJson('/api/profiles');
    return {
      profiles: data.data || [],
      models: data.models || [],
      providers: (data.providers || []).map(toProviderCard),
      defaultProfile: data.default_profile || 'default',
    };
  },
  async saveProfile(profile, setDefault = false) {
    return apiJson('/api/profiles', {
      method: 'POST',
      body: JSON.stringify({ ...profile, set_default: setDefault }),
    });
  },
  async visionCheck(modelId) {
    return apiJson('/api/vision-check', {
      method: 'POST',
      body: JSON.stringify({ model_id: modelId }),
    });
  },
  async saveProvider(provider) {
    const data = await apiJson('/api/providers', {
      method: 'POST',
      body: JSON.stringify(provider),
    });
    return data.provider;
  },
  async deleteProvider(providerId) {
    return apiJson(`/api/providers/${encodeURIComponent(providerId)}`, {
      method: 'DELETE',
    });
  },
  async testConnection({ providerId, model, provider } = {}) {
    return apiJson('/api/test-connection', {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId, model, ...(provider || {}) }),
    });
  },
  async routerStatus() {
    return apiJson('/api/router/status');
  },
  async claudeSmoke() {
    return apiJson('/v1/messages', {
      method: 'POST',
      headers: { Authorization: `Bearer ${SUPERDS_LOCAL_KEY}` },
      body: JSON.stringify({
        model: 'claude-3-5-haiku-latest',
        max_tokens: 64,
        messages: [{ role: 'user', content: 'Super DeepSeek smoke test.' }],
      }),
    });
  },
};
