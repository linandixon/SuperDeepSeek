// Pages: Overview, Setup, Providers, Profiles
const { useState: useStateA, useMemo: useMemoA, useEffect: useEffectA } = React;

// ============ Page: Overview ============
function PageOverview({ goto, traces, providers = window.PROVIDERS }) {
  const recent = traces.slice(0, 8);
  const totalRequests = traces.length;
  const successful = traces.filter(t => t.status === 'success').length;
  const successRate = totalRequests ? ((successful / totalRequests) * 100).toFixed(1) : '0';
  const avgLatency = totalRequests ? Math.round(traces.reduce((sum, t) => sum + (t.latencyMs || 0), 0) / totalRequests) : 0;
  const inputTokens = traces.reduce((sum, t) => sum + (t.inputTokens || 0), 0);
  const outputTokens = traces.reduce((sum, t) => sum + (t.outputTokens || 0), 0);
  const totalCost = traces.reduce((sum, t) => sum + (t.costUsd || 0), 0);
  const strippedCount = traces.filter(t => t.sanitizer === 'cch stripped').length;
  const volumeSeries = tracesToHourlySeries(traces);
  const strippedSeries = tracesToHourlySeries(traces.filter(t => t.sanitizer === 'cch stripped'));
  const zeroSeries = Array.from({ length: 48 }, () => 0);
  const chartSeries = totalRequests ? volumeSeries : zeroSeries;
  const fmtCompact = (n) => n >= 1000000 ? `${(n / 1000000).toFixed(2)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n);
  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="grid grid-4">
        <MetricCard label="今日请求" value={String(totalRequests)} icon="activity" spark={chartSeries} />
        <MetricCard label="成功率"   value={successRate} unit="%" icon="check" spark={chartSeries} />
        <MetricCard label="平均延迟" value={String(avgLatency)} unit="ms" icon="gauge" spark={chartSeries} />
        <MetricCard label="预估开销" value={`$${totalCost.toFixed(4)}`} icon="zap" spark={chartSeries} />
      </div>
      <div className="grid grid-4">
        <MetricCard label="输入 Token"   value={fmtCompact(inputTokens)} icon="arrow-right" />
        <MetricCard label="输出 Token"   value={fmtCompact(outputTokens)}  icon="arrow-right" />
        <MetricCard label="缓存友好请求" value={totalRequests ? ((strippedCount / totalRequests) * 100).toFixed(1) : '0'} unit="%" icon="database" />
        <MetricCard label="清洗的账单头" value={String(strippedCount)} icon="broom" />
      </div>

      <div className="grid overview-grid">
        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="activity" size={14} /> 请求量 · 最近 24 小时</div>
            <div className="row" style={{ gap: 14, fontSize: 11 }}>
              <span className="row" style={{ gap: 5 }}><i style={{ width: 8, height: 2, background: 'var(--accent)' }} /><span className="muted">总请求</span></span>
              <span className="row" style={{ gap: 5 }}><i style={{ width: 8, height: 2, background: 'var(--info)' }} /><span className="muted">缓存友好</span></span>
              <span className="row" style={{ gap: 5 }}><i style={{ width: 8, height: 2, background: 'var(--violet)' }} /><span className="muted">已清洗</span></span>
              <Seg options={[{value:'24h',label:'24小时'},{value:'7d',label:'7天'},{value:'30d',label:'30天'}]} value="24h" onChange={()=>{}} />
            </div>
          </div>
          <div className="card-b" style={{ padding: '6px 6px 0' }}>
            <AreaChart
              series={[
                { name: '请求', data: chartSeries, color: '#5eead4' },
                { name: '缓存友好', data: totalRequests ? strippedSeries : zeroSeries, color: '#60a5fa', fill: false },
                { name: '已清洗', data: totalRequests ? strippedSeries : zeroSeries, color: '#c084fc', fill: false },
              ]}
              labels={Array.from({length:48},(_,i)=>{const h=Math.floor(i/2);return `${String(h).padStart(2,'0')}:${i%2?'30':'00'}`})}
              height={210}
            />
          </div>
        </div>
        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="server" size={14} /> 上游健康</div>
            <button className="btn-mini" onClick={() => goto('providers')}>全部 <Icon name="chevron-r" size={11} /></button>
          </div>
          <div className="card-b" style={{ padding: 0 }}>
            {providers.map(p => (
              <div key={p.id} style={{ display: 'grid', gridTemplateColumns: '24px 1fr auto auto', gap: 10, padding: '10px 14px', borderBottom: '1px solid var(--line)', alignItems: 'center' }}>
                <div style={{ width: 20, height: 20, borderRadius: 4, background: 'var(--bg-3)', display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: p.color, border: `1px solid ${p.color}33` }}>{p.short}</div>
                <div>
                  <div style={{ fontSize: 12.5 }}>{p.name}</div>
                  <div className="muted tiny mono">{p.defaultModel}</div>
                </div>
                <div className="mono tiny muted">{p.latency ? p.latency + 'ms' : '—'}</div>
                <StatusBadge status={p.status === 'healthy' ? 'success' : p.status === 'unknown' ? 'unknown' : 'failed'} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-h">
          <div className="t"><Icon name="list" size={14} /> 最近请求</div>
          <div className="row" style={{ gap: 8 }}>
            <input className="input" placeholder="过滤…" style={{ width: 200, height: 26 }} />
            <button className="btn-mini" onClick={() => goto('traces')}>打开追踪 <Icon name="arrow-right" size={11} /></button>
          </div>
        </div>
        <div className="card-b tight">
          <table className="tbl">
            <thead><tr>
              <th style={{ width: 70 }}>时间</th>
              <th>客户端</th>
              <th>入站模型</th>
              <th>解析为上游</th>
              <th>状态</th>
              <th className="num">延迟</th>
              <th className="num">Token</th>
              <th>清洗</th>
            </tr></thead>
            <tbody>
              {recent.map(t => (
                <tr key={t.id} style={{ cursor: 'pointer' }} onClick={() => goto('traces', t.id)}>
                  <td className="cell-mono muted">{t.time}</td>
                  <td>{t.client}</td>
                  <td className="cell-mono">{t.incomingModel}</td>
                  <td className="cell-mono text-accent">{t.resolvedModel}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td className="num">{t.latencyMs}ms</td>
                  <td className="num muted">{((t.inputTokens + t.outputTokens) / 1000).toFixed(1)}K</td>
                  <td>
                    {t.sanitizer === 'cch stripped'
                      ? <span className="badge violet"><span className="dot"/>cch stripped</span>
                      : <span className="badge subtle">{t.sanitizer}</span>}
                  </td>
                </tr>
              ))}
              {recent.length === 0 && (
                <tr>
                  <td colSpan="8"><div className="empty">暂无请求历史。</div></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function tracesToHourlySeries(traces) {
  const series = Array.from({ length: 48 }, () => 0);
  const now = Date.now();
  traces.forEach(t => {
    const started = t.raw?.started_at ? t.raw.started_at * 1000 : t.timeFull?.getTime?.();
    if (!started) return;
    const ageMs = now - started;
    if (ageMs < 0 || ageMs > 24 * 60 * 60 * 1000) return;
    const bucket = 47 - Math.floor(ageMs / (30 * 60 * 1000));
    if (bucket >= 0 && bucket < series.length) series[bucket] += 1;
  });
  return series;
}

// ============ Page: Setup Wizard ============
function PageSetup({ goto }) {
  const [step, setStep] = useStateA(2);
  const [client, setClient] = useStateA('both');
  const [providerType, setProviderType] = useStateA('deepseek');
  const [baseUrl, setBaseUrl] = useStateA('https://api.deepseek.com/v1');
  const [apiKey, setApiKey] = useStateA('');
  const [model, setModel] = useStateA('deepseek-chat');

  const steps = [
    { n: 1, label: '选择目标客户端' },
    { n: 2, label: '配置上游服务' },
    { n: 3, label: '本地端点' },
    { n: 4, label: '复制环境变量' },
  ];

  return (
    <div className="col" style={{ gap: 16, maxWidth: 920 }}>
      <div className="steps">
        {steps.map((s, i) => (
          <React.Fragment key={s.n}>
            <div className={`step ${step === s.n ? 'active' : step > s.n ? 'done' : ''}`}>
              <div className="num">{step > s.n ? <Icon name="check" size={12} stroke={3} /> : s.n}</div>
              {s.label}
            </div>
            {i < steps.length - 1 && <div className="step-line" />}
          </React.Fragment>
        ))}
      </div>

      {step === 1 && (
        <div className="card">
          <div className="card-h"><div className="t">1 · 选择目标客户端</div></div>
          <div className="card-b col" style={{ gap: 12 }}>
            <div className="muted" style={{ fontSize: 12.5 }}>选择需要本地代理转发的客户端，会决定后续生成的环境变量。</div>
            <div className="grid grid-3" style={{ gap: 10 }}>
              {[
                { v: 'claude', name: 'Claude Code', desc: '通过 Anthropic 兼容端点接入', ic: 'sparkles' },
                { v: 'openai', name: 'OpenAI SDK', desc: 'OpenAI Python / Node SDK', ic: 'cpu' },
                { v: 'both',   name: '两者都要', desc: '同端口暴露两套兼容协议', ic: 'box' },
              ].map(o => (
                <button key={o.v} className="prov-card" onClick={() => setClient(o.v)} style={{ borderColor: client === o.v ? 'var(--accent)' : 'var(--line)', textAlign: 'left' }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <div className="logo" style={{ color: 'var(--accent)' }}><Icon name={o.ic} size={16} /></div>
                    {client === o.v && <Icon name="check" size={14} className="text-accent" />}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600 }}>{o.name}</div>
                    <div className="muted tiny" style={{ marginTop: 2 }}>{o.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="card">
          <div className="card-h"><div className="t">2 · 配置上游服务</div></div>
          <div className="card-b col" style={{ gap: 14 }}>
            <div className="grid grid-2">
              <div className="field">
                <div className="field-label">提供方类型 <span className="hint">openai 兼容协议</span></div>
                <select className="select" value={providerType} onChange={(e) => setProviderType(e.target.value)}>
                  <option value="deepseek">DeepSeek</option>
                  <option value="qwen">Qwen / 通义千问</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="kimi">Kimi / Moonshot</option>
                  <option value="vllm">本地 vLLM</option>
                  <option value="custom">自定义 OpenAI 兼容</option>
                </select>
              </div>
              <div className="field">
                <div className="field-label">默认模型</div>
                <input className="input mono" value={model} onChange={(e)=>setModel(e.target.value)} />
              </div>
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <div className="field-label">Base URL</div>
                <input className="input mono" value={baseUrl} onChange={(e)=>setBaseUrl(e.target.value)} />
              </div>
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <div className="field-label">API Key <span className="hint">永远不会回显完整内容</span></div>
                <SecretInput value={apiKey} onChange={setApiKey} />
              </div>
            </div>
            <div className="divider" />
            <ConnectionTestButton
              providerId={providerType}
              model={model}
              provider={{
                id: providerType,
                name: providerType,
                protocol: 'openai',
                base_url: baseUrl,
                api_key: apiKey,
                default_model: model,
              }}
            />
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="card">
          <div className="card-h"><div className="t">3 · 本地端点</div></div>
          <div className="card-b col" style={{ gap: 12 }}>
            <div className="grid grid-3">
              <div className="field">
                <div className="field-label">本地 Host</div>
                <input className="input mono" defaultValue="127.0.0.1" />
              </div>
              <div className="field">
                <div className="field-label">端口</div>
                <input className="input mono" defaultValue="8787" />
              </div>
              <div className="field">
                <div className="field-label">绑定模式</div>
                <select className="select" defaultValue="local">
                  <option value="local">仅本机 (loopback)</option>
                  <option value="lan">局域网 (0.0.0.0)</option>
                </select>
              </div>
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <div className="field-label">本地 API Key <span className="hint">客户端连本地端点时使用</span></div>
                <SecretInput value="sk-superds-local-change-me" readonly />
              </div>
            </div>
            <div className="alert info">
              <Icon name="info" size={16} className="ico" />
              <div>
                <div className="ttl">本地 Key 不会被发往上游</div>
                Super DeepSeek 只在本地校验该 Key；转发到上游时会替换为提供方的实际 API Key。
              </div>
            </div>
          </div>
        </div>
      )}

      {step === 4 && <StepEnvVars />}

      <div className="row" style={{ justifyContent: 'space-between' }}>
        <button className="btn" disabled={step === 1} onClick={() => setStep(step - 1)}>
          <Icon name="chevron-r" size={12} style={{ transform: 'rotate(180deg)' }} /> 上一步
        </button>
        <div className="row" style={{ gap: 8 }}>
          {step === 4 && <button className="btn ghost" onClick={() => goto('claude')}>查看 Claude Code 兼容性 →</button>}
          {step < 4 ? (
            <button className="btn primary" onClick={() => setStep(step + 1)}>下一步 <Icon name="arrow-right" size={12} /></button>
          ) : (
            <button className="btn primary" onClick={() => goto('overview')}>完成 <Icon name="check" size={12} /></button>
          )}
        </div>
      </div>
    </div>
  );
}

function StepEnvVars() {
  return (
    <div className="col" style={{ gap: 12 }}>
      <div className="card">
        <div className="card-h"><div className="t">4 · 复制环境变量</div><span className="muted tiny">将以下内容粘贴到 shell 启动文件，或在终端中临时 export</span></div>
        <div className="card-b col" style={{ gap: 12 }}>
          <EnvVarCopyBlock
            title="Claude Code"
            badge={<span className="badge accent">已配置 5 个别名</span>}
            lines={[
              { k: 'ANTHROPIC_BASE_URL', v: 'http://127.0.0.1:8787' },
              { k: 'ANTHROPIC_API_KEY',  v: 'sk-superds-local-change-me' },
            ]}
          />
          <EnvVarCopyBlock
            title="OpenAI 兼容客户端"
            lines={[
              { k: 'OPENAI_BASE_URL', v: 'http://127.0.0.1:8787/openai/v1' },
              { k: 'OPENAI_API_KEY',  v: 'sk-superds-local-change-me' },
            ]}
          />
          <div className="alert ok">
            <Icon name="check" size={16} className="ico" />
            <div>
              <div className="ttl">设置完成，可以试运行</div>
              在新终端中执行 <code className="mono" style={{ color: 'var(--accent)' }}>claude code --version</code>，然后回到「请求追踪」页面观察首条请求被本地路由。
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============ Page: Providers ============
function PageProviders({ openDrawer, providers = window.PROVIDERS, presets = [], onProvidersChange }) {
  const [tests, setTests] = useStateA({});
  const [deleting, setDeleting] = useStateA(null);
  const [presetFilter, setPresetFilter] = useStateA('all');
  const applyPreset = (preset) => {
    const existing = providers.find(p => p.id === preset.id) || {};
    openDrawer({
      kind: existing.id ? 'provider-edit' : 'provider-new',
      payload: {
        ...existing,
        id: preset.id,
        name: preset.name,
        protocol: preset.protocol,
        baseUrl: preset.base_url,
        apiKeyEnv: preset.api_key_env,
        defaultModel: preset.default_model,
        models: existing.models || preset.suggested_models || [preset.default_model].filter(Boolean),
        suggestedModels: preset.suggested_models || [],
      },
    });
  };
  const runTest = async (p) => {
    setTests(x => ({ ...x, [p.id]: { state: 'testing' } }));
    try {
      const result = await window.SuperDSApi.testConnection({ providerId: p.id, model: p.defaultModel });
      setTests(x => ({ ...x, [p.id]: { state: result.ok ? 'ok' : 'err', result } }));
    } catch (e) {
      setTests(x => ({ ...x, [p.id]: { state: 'err', result: { error: e.message } } }));
    }
  };
  const deleteProvider = async (p) => {
    if (!window.SuperDSApi || deleting) return;
    const ok = window.confirm ? window.confirm(`删除上游「${p.name}」？关联模型会一起移除。`) : true;
    if (!ok) return;
    setDeleting(p.id);
    try {
      await window.SuperDSApi.deleteProvider(p.id);
      const next = await window.SuperDSApi.providers();
      onProvidersChange && onProvidersChange(next);
    } catch (e) {
      setTests(x => ({ ...x, [p.id]: { state: 'err', result: { error: e.message } } }));
    } finally {
      setDeleting(null);
    }
  };
  const shownPresets = presetFilter === 'all' ? presets : presets.filter(p => p.category === presetFilter);
  return (
    <div className="col" style={{ gap: 14 }}>
      {presets.length > 0 && (
        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="box" size={14}/> 上游预设</div>
            <Seg
              value={presetFilter}
              onChange={setPresetFilter}
              options={[
                { value: 'all', label: '全部' },
                { value: 'coding', label: 'Coding' },
                { value: 'aggregator', label: '聚合' },
                { value: 'local', label: '本地' },
              ]}
            />
          </div>
          <div className="card-b">
            <div className="grid grid-4 preset-grid">
              {shownPresets.slice(0, 8).map(p => (
                <button key={p.id} className="prov-card preset-card" onClick={() => applyPreset(p)}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <div className="logo" style={{ background: providerColorLocal(p.id) + '22', color: providerColorLocal(p.id), border: `1px solid ${providerColorLocal(p.id)}55` }}>
                      {(p.name || p.id).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase()}
                    </div>
                    <span className="badge neutral">{p.category}</span>
                  </div>
                  <div className="preset-card-main">
                    <div className="preset-card-title">{p.name}</div>
                    <div className="preset-card-url muted tiny mono">{p.base_url}</div>
                  </div>
                  <div className="row preset-card-foot" style={{ justifyContent: 'space-between', gap: 8 }}>
                    <div className="preset-card-model mono tiny">{p.default_model}</div>
                    <span className="badge accent">使用</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="row" style={{ gap: 8 }}>
          <input className="input" placeholder="搜索上游…" style={{ width: 260 }} />
          <Seg options={[{value:'all',label:'全部'},{value:'healthy',label:'健康'},{value:'failed',label:'异常'}]} value="all" onChange={()=>{}} />
        </div>
        <button className="btn primary" onClick={() => openDrawer({ kind: 'provider-new' })}>
          <Icon name="plus" size={12} /> 添加上游
        </button>
      </div>

      <div className="grid grid-3">
        {providers.map(p => {
          const test = tests[p.id];
          const status = test?.state === 'ok' ? 'healthy' : test?.state === 'err' ? 'failed' : p.status;
          return (
          <div key={p.id} className="prov-card">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div className="row" style={{ gap: 10 }}>
                <div className="logo" style={{ background: p.color + '22', color: p.color, border: `1px solid ${p.color}55` }}>{p.short}</div>
                <div>
                  <div style={{ fontWeight: 600 }}>{p.name}</div>
                  <div className="muted tiny">{p.protocol}</div>
                </div>
              </div>
              <StatusBadge status={status === 'healthy' ? 'success' : status === 'unknown' ? 'unknown' : 'failed'} />
            </div>
            <div className="col" style={{ gap: 4 }}>
              <div className="kv"><span className="k">URL</span><span className="v" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>{p.baseUrl}</span></div>
              <div className="kv"><span className="k">默认模型</span><span className="v">{p.defaultModel}</span></div>
              <div className="kv"><span className="k">模型数量</span><span className="v">{(p.models || []).length || (p.defaultModel ? 1 : 0)}</span></div>
              <div className="kv"><span className="k">API Key</span>
                <span className="v">{p.apiKeyMask}</span>
                {p.apiKeyStatus === 'configured' ? <span className="badge ok" style={{ marginLeft: 6 }}><span className="dot"/>已配置</span> : <span className="badge err" style={{ marginLeft: 6 }}><span className="dot"/>缺失</span>}
              </div>
              <div className="kv"><span className="k">上次测试</span><span className="v">
                {test?.state === 'testing'
                  ? '正在进行 Stream Check…'
                  : test?.result
                    ? `${test.result.status} · ${test.result.latency_ms || '—'}ms · TTFB ${test.result.ttfb_ms || '—'}ms`
                    : <>{p.lastTested}{p.latency && <span className="muted"> · {p.latency}ms</span>}</>}
              </span></div>
            </div>
            <div className="row" style={{ gap: 6, justifyContent: 'flex-end', marginTop: 'auto' }}>
              <button className="btn sm" onClick={() => openDrawer({ kind: 'provider-edit', payload: p })}><Icon name="edit" size={11} /> 编辑</button>
              <button className="btn sm" onClick={() => runTest(p)} disabled={test?.state === 'testing'}>
                <Icon name={test?.state === 'testing' ? 'refresh' : 'plug'} size={11} className={test?.state === 'testing' ? 'spin' : ''} />
                测试
              </button>
              <button className="btn sm ghost"><Icon name="copy" size={11} /></button>
              <button className="btn sm ghost danger" onClick={() => deleteProvider(p)} disabled={deleting === p.id}>
                <Icon name={deleting === p.id ? 'refresh' : 'trash'} size={11} className={deleting === p.id ? 'spin' : ''} />
              </button>
            </div>
          </div>
        );})}
      </div>
    </div>
  );
}

function providerColorLocal(id) {
  const colors = { deepseek: '#5eead4', qwen: '#c084fc', openrouter: '#fb923c', kimi: '#60a5fa', siliconflow: '#4ade80', litellm: '#fbbf24', ollama: '#a8aeb8', vllm: '#4ade80' };
  return colors[id] || '#a8aeb8';
}

// ============ Page: Profiles ============
const PROFILE_ROLE_DEFS = [
  { role: 'main', key: 'main_model', label: '主模型', desc: '通用任务、对话、计划' },
  { role: 'fast_tool', key: 'fast_tool_model', label: '快速 / 工具', desc: 'Claude Code Haiku 路径，工具调用' },
  { role: 'large', key: 'large_model', label: '大型 / 推理', desc: '长上下文、复杂推理' },
  { role: 'verifier', key: 'verifier_model', label: '校验', desc: '审查、二次确认' },
  { role: 'vision', key: 'vision_model', label: '视觉', desc: '图像 / 多模态请求' },
  { role: 'fallback', key: 'fallback_model', label: '兜底', desc: '未配置时使用主模型' },
];

function cloneProfileForEdit(profile) {
  return {
    id: profile?.id || 'default',
    name: profile?.name || 'Default',
    main_model: profile?.main_model || '',
    fast_tool_model: profile?.fast_tool_model || '',
    large_model: profile?.large_model || '',
    verifier_model: profile?.verifier_model || '',
    vision_model: profile?.vision_model || '',
    fallback_model: profile?.fallback_model || '',
    failover: profile?.failover || {},
  };
}

function PageProfiles({ modelCaps = [], profiles = [], models = [], providers = [], defaultProfile = 'default', onProfilesChange, onDefaultProfileChange, onModelCapsChange }) {
  const liveProfiles = profiles.length ? profiles : window.PROFILES;
  const firstProfile = liveProfiles.find(p => p.id === defaultProfile) || liveProfiles[0] || {};
  const [activeId, setActiveId] = useStateA(firstProfile.id || 'default');
  const [draft, setDraft] = useStateA(cloneProfileForEdit(firstProfile));
  const [setAsDefault, setSetAsDefault] = useStateA(true);
  const [saving, setSaving] = useStateA(false);
  const [visionChecking, setVisionChecking] = useStateA(false);
  const [visionCheckResult, setVisionCheckResult] = useStateA(null);

  useEffectA(() => {
    const next = liveProfiles.find(p => p.id === activeId) || firstProfile;
    if (next?.id) {
      setActiveId(next.id);
      setDraft(cloneProfileForEdit(next));
      setSetAsDefault(next.id === defaultProfile);
    }
  }, [profiles.length, defaultProfile]);

  const selectProfile = (profile) => {
    setActiveId(profile.id);
    setDraft(cloneProfileForEdit(profile));
    setSetAsDefault(profile.id === defaultProfile);
  };
  const updateDraft = (key, value) => setDraft(d => ({ ...d, [key]: value }));
  const modelProvider = (model) => providers.find(p => p.id === model?.provider_id);
  const groupedModels = useMemoA(() => {
    const selectedIds = new Set(PROFILE_ROLE_DEFS.map(r => draft[r.key]).filter(Boolean));
    const usedIds = new Set();
    const currentModels = models.filter(m => providers.some(p => p.id === m.provider_id));
    currentModels.forEach(m => usedIds.add(m.id));
    const legacySelected = models.filter(m => selectedIds.has(m.id) && !usedIds.has(m.id));
    const rows = {};
    for (const model of currentModels) {
      const provider = modelProvider(model);
      const key = provider?.id || model.provider_id || 'unknown';
      if (!rows[key]) rows[key] = { provider, label: provider?.name || key, models: [] };
      rows[key].models.push(model);
    }
    const groups = Object.entries(rows);
    if (legacySelected.length) {
      groups.push(['legacy', { provider: null, label: '旧配置（当前已选）', models: legacySelected }]);
    }
    return groups;
  }, [models, providers, draft]);
  const saveProfile = async () => {
    if (!window.SuperDSApi) return;
    setSaving(true);
    try {
      const result = await window.SuperDSApi.saveProfile(draft, setAsDefault);
      const profileData = await window.SuperDSApi.profiles();
      const caps = await window.SuperDSApi.modelCapabilities();
      onProfilesChange && onProfilesChange(profileData.profiles);
      onDefaultProfileChange && onDefaultProfileChange(profileData.defaultProfile);
      onModelCapsChange && onModelCapsChange(caps);
      setActiveId(result.profile.id);
      setDraft(cloneProfileForEdit(result.profile));
    } finally {
      setSaving(false);
    }
  };
  const runVisionCheck = async () => {
    if (!window.SuperDSApi || !draft.vision_model) return;
    setVisionChecking(true);
    setVisionCheckResult(null);
    try {
      const result = await window.SuperDSApi.visionCheck(draft.vision_model);
      const caps = await window.SuperDSApi.modelCapabilities();
      onModelCapsChange && onModelCapsChange(caps);
      setVisionCheckResult(result);
    } catch (e) {
      setVisionCheckResult({ ok: false, vision_status: 'unknown', error: e.message });
    } finally {
      setVisionChecking(false);
    }
  };
  const cloneProfile = () => {
    const suffix = Date.now().toString(36).slice(-4);
    const id = `${draft.id || 'profile'}-${suffix}`;
    setActiveId(id);
    setDraft({ ...draft, id, name: `${draft.name || 'Profile'} 副本` });
    setSetAsDefault(false);
  };
  const createProfile = () => {
    const id = `profile-${Date.now().toString(36).slice(-5)}`;
    const base = cloneProfileForEdit(firstProfile);
    setActiveId(id);
    setDraft({ ...base, id, name: '新方案' });
    setSetAsDefault(false);
  };
  const visionModel = models.find(m => m.id === draft.vision_model);
  const visionCaps = modelCaps.find(m => m.id === draft.vision_model)?.capabilities || {};
  const visionOk = !draft.vision_model || visionCaps.vision_status !== 'verified_unsupported';
  const visionLabel = (caps) => caps.vision_status === 'verified_supported' ? '可看图' : caps.vision_status === 'verified_unsupported' ? '不能看图' : '未检测';
  const visionTone = (caps) => caps.vision_status === 'verified_supported' ? 'ok' : caps.vision_status === 'verified_unsupported' ? 'err' : 'warn';
  return (
    <div className="grid profile-layout">
      <div className="card">
        <div className="card-h">
          <div className="t"><Icon name="layers" size={14} /> 方案</div>
          <button className="btn-mini" onClick={createProfile}><Icon name="plus" size={11}/></button>
        </div>
        <div className="card-b tight">
          {liveProfiles.map(p => (
            <button key={p.id} onClick={() => selectProfile(p)}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left',
                      padding: '10px 12px', borderBottom: '1px solid var(--line)',
                      background: activeId === p.id ? 'var(--accent-soft)' : 'transparent',
                      borderLeft: activeId === p.id ? '2px solid var(--accent)' : '2px solid transparent',
                    }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div style={{ fontWeight: 500 }}>{p.name}</div>
                {p.id === defaultProfile && <span className="badge accent">当前</span>}
              </div>
              <div className="muted tiny mono" style={{ marginTop: 3 }}>{p.id}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="col" style={{ gap: 14 }}>
        {!visionOk && (
        <div className="alert warn">
          <Icon name="alert" size={16} className="ico" />
          <div>
            <div className="ttl">视觉角色能力不匹配</div>
            当前视觉角色选择了 <code className="mono">{visionModel?.actual_model || draft.vision_model}</code>，但能力矩阵里没有标记为视觉模型。
          </div>
        </div>
        )}
        {visionCheckResult && (
        <div className={`alert ${visionCheckResult.ok ? 'ok' : visionCheckResult.vision_status === 'verified_unsupported' ? 'err' : 'warn'}`}>
          <Icon name={visionCheckResult.ok ? 'check' : 'alert'} size={16} className="ico" />
          <div>
            <div className="ttl">视觉检测：{visionLabel({ vision_status: visionCheckResult.vision_status })}</div>
            {visionCheckResult.model || ''}{visionCheckResult.status ? ` · ${visionCheckResult.status}` : ''}{visionCheckResult.error ? ` · ${visionCheckResult.error}` : ''}
          </div>
        </div>
        )}

        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="route" size={14}/> 角色 → 上游模型</div>
            <div className="row" style={{ gap: 8 }}>
              <span className="muted tiny mono">profile = {draft.id}</span>
              <button className="btn sm" onClick={cloneProfile}><Icon name="copy" size={11}/> 克隆</button>
              <button className="btn sm" onClick={runVisionCheck} disabled={visionChecking || !draft.vision_model}>
                <Icon name={visionChecking ? 'refresh' : 'eye'} size={11} className={visionChecking ? 'spin' : ''}/> 检测视觉
              </button>
              <button className="btn sm primary" onClick={saveProfile} disabled={saving}>
                {saving ? <><Icon name="refresh" size={11} className="spin"/> 保存中</> : '保存方案'}
              </button>
            </div>
          </div>
          <div className="card-b tight col" style={{ gap: 0 }}>
            <div className="grid grid-2" style={{ padding: 12, gap: 10, borderBottom: '1px solid var(--line)' }}>
              <Field2 label="方案 ID"><input className="input mono" value={draft.id} onChange={(e) => updateDraft('id', e.target.value)} /></Field2>
              <Field2 label="方案名称"><input className="input" value={draft.name} onChange={(e) => updateDraft('name', e.target.value)} /></Field2>
              <label className="row tiny" style={{ gap: 8, gridColumn: '1 / -1' }}>
                <input type="checkbox" checked={setAsDefault} onChange={(e) => setSetAsDefault(e.target.checked)} />
                保存后设为当前默认方案
              </label>
            </div>
            <div className="role-row" style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg-1)' }}>
              <div className="label">角色</div>
              <div className="label">选择模型</div>
              <div className="label">LiteLLM 模型字符串</div>
              <div className="label">状态</div>
            </div>
            {PROFILE_ROLE_DEFS.map(r => {
              const selected = models.find(m => m.id === draft[r.key]);
              const p = modelProvider(selected);
              const caps = modelCaps.find(m => m.id === selected?.id)?.capabilities || {};
              const isCurrentDefault = Boolean(p && selected?.actual_model === p.defaultModel);
              const isKnownProviderModel = Boolean(p && (p.models || []).includes(selected?.actual_model));
              const isFastTool = r.role === 'fast_tool';
              return (
                <div key={r.role} className="role-row">
                  <div>
                    <div className="role-name">
                      {r.label}
                      {isFastTool && <span className="badge accent">Claude Code 需要</span>}
                      {r.role === 'vision' && !p && <span className="badge warn">未配置</span>}
                    </div>
                    <div className="role-desc">{r.desc}</div>
                  </div>
                  <div className="profile-model-cell">
                    <select className="select mono profile-model-select" value={draft[r.key] || ''} onChange={(e) => updateDraft(r.key, e.target.value)}>
                      <option value="">未配置</option>
                      {groupedModels.map(([providerId, group]) => (
                        <optgroup key={providerId} label={group.label}>
                          {group.models.map(m => (
                            <option key={m.id} value={m.id}>{m.actual_model}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    <div className="profile-model-sub">
                      {p ? (
                        <span>{p.name} · {isCurrentDefault ? '默认' : isKnownProviderModel ? '已配置' : '旧配置'}</span>
                      ) : <span>未配置</span>}
                    </div>
                  </div>
                  <div className="mono tiny muted">{selected?.litellm_model || '—'}</div>
                  <div className="profile-picker">
                    <div className="row" style={{ gap: 4, flexWrap: 'wrap' }}>
                      <span className={`badge ${isKnownProviderModel ? 'ok' : 'warn'}`}>{isCurrentDefault ? '默认' : isKnownProviderModel ? '已配置' : selected ? '旧配置' : '未选'}</span>
                      {r.role === 'vision'
                        ? <span className={`badge ${visionTone(caps)}`}>{visionLabel(caps)}</span>
                        : <span className="badge neutral">{draft.vision_model ? '图片走视觉' : '无视觉角色'}</span>}
                      <span className={`badge ${caps.tools ? 'ok' : 'neutral'}`}>{caps.tools ? 'tools' : 'no tools'}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {modelCaps.length > 0 && (
          <div className="card">
            <div className="card-h">
              <div className="t"><Icon name="cpu" size={14}/> 模型能力矩阵</div>
              <span className="muted tiny">vision / tools / reasoning state</span>
            </div>
            <div className="card-b tight">
              <table className="tbl">
                <thead><tr><th>模型</th><th>角色</th><th>视觉</th><th>工具</th><th>Reasoning 状态</th><th>API</th></tr></thead>
                <tbody>
                  {modelCaps.map(m => (
                    <tr key={m.id}>
                      <td className="mono">{m.actual_model}</td>
                      <td><span className="badge neutral">{m.role}</span></td>
                      <td>
                        <StatusBadge status={m.capabilities.vision_status === 'verified_supported' ? 'enabled' : m.capabilities.vision_status === 'verified_unsupported' ? 'disabled' : 'unknown'}>
                          {visionLabel(m.capabilities)}
                        </StatusBadge>
                      </td>
                      <td><StatusBadge status={m.capabilities.tools ? 'enabled' : 'disabled'}>{m.capabilities.tools ? '支持' : '不支持'}</StatusBadge></td>
                      <td className="mono tiny">{m.capabilities.reasoning_state}</td>
                      <td className="mono tiny muted">{m.capabilities.api_format}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { PageOverview, PageSetup, PageProviders, PageProfiles });
