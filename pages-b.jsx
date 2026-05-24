// Pages: Claude Code, Traces, Sanitizer & Cache, Settings
const { useState: useStateB, useMemo: useMemoB, useEffect: useEffectB } = React;

// ============ Page: Claude Code Compatibility ============
function PageClaude({ aliases, setAliases, showHaikuWarning = true }) {
  const haikuEnabled = aliases.some(a => a.enabled && a.alias.includes('haiku'));

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="alert info">
        <Icon name="info" size={16} className="ico" />
        <div>
          <div className="ttl">这是一个本地兼容层</div>
          Super DeepSeek 暴露 Claude 风格的模型别名，方便 Claude Code 直连。<b>这并不代表上游就是 Anthropic</b>——所有别名都会被解析到你在「方案」里配置的真实上游模型。
        </div>
      </div>

      {!haikuEnabled && showHaikuWarning && (
        <div className="alert warn">
          <Icon name="alert" size={16} className="ico" />
          <div>
            <div className="ttl">Haiku 别名缺失</div>
            未启用任何包含 <code className="mono">haiku</code> 的别名。Claude Code 的快速 / 工具路径可能会停滞、工具调用错路或行为异常。建议启用至少一个 haiku 别名映射到 <code className="mono">fast_tool</code> 角色。
          </div>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: '1.4fr 1fr', gap: 14 }}>
        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="check" size={14} /> 兼容性检查</div>
            <button className="btn-mini"><Icon name="refresh" size={11}/> 重新检测</button>
          </div>
          <div className="card-b tight">
            <CompatibilityChecklist items={window.COMPAT} />
          </div>
        </div>

        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="terminal" size={14} /> 环境变量</div>
            <span className="muted tiny mono">localhost:8787</span>
          </div>
          <div className="card-b col" style={{ gap: 10 }}>
            <EnvVarCopyBlock
              title="Claude Code"
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
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-h">
          <div className="t"><Icon name="route" size={14} /> 模型别名表</div>
          <div className="row" style={{ gap: 8 }}>
            <span className="muted tiny">{aliases.filter(a => a.enabled).length} / {aliases.length} 已启用</span>
            <button className="btn sm"><Icon name="plus" size={11}/> 添加别名</button>
          </div>
        </div>
        <div className="card-b tight">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 50 }}>启用</th>
                <th>入站别名</th>
                <th>角色</th>
                <th>目标方案</th>
                <th>目标上游模型</th>
                <th>说明</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {aliases.map(a => {
                const isHaiku = a.alias.includes('haiku');
                return (
                  <tr key={a.id} style={{ opacity: a.enabled ? 1 : 0.55 }}>
                    <td><Switch on={a.enabled} onChange={(v) => setAliases(aliases.map(x => x.id === a.id ? { ...x, enabled: v } : x))} /></td>
                    <td>
                      <span className={`mono ${isHaiku ? 'text-accent' : ''}`} style={{ fontSize: 12, fontWeight: isHaiku ? 600 : 400 }}>{a.alias}</span>
                      {isHaiku && <span className="badge accent" style={{ marginLeft: 8 }}>HAIKU</span>}
                    </td>
                    <td><span className="badge neutral">{a.role}</span></td>
                    <td className="mono tiny muted">{a.targetProfile}</td>
                    <td className="mono" style={{ fontSize: 12 }}>{a.targetModel}</td>
                    <td className="muted tiny">{a.notes}</td>
                    <td className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
                      <button className="btn sm ghost"><Icon name="edit" size={11}/></button>
                      <button className="btn sm ghost danger"><Icon name="trash" size={11}/></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============ Page: Traces ============
function PageTraces({ initialId, traces, setTraces }) {
  const safeTraces = traces && traces.length ? traces : window.TRACES;
  const [selectedId, setSelectedId] = useStateB(initialId || safeTraces[0].id);
  const [tab, setTab] = useStateB('timeline');
  const [search, setSearch] = useStateB('');
  const [filterStatus, setFilterStatus] = useStateB('all');
  const [filterClient, setFilterClient] = useStateB('all');

  useEffectB(() => { if (initialId) setSelectedId(initialId); }, [initialId]);

  const filtered = useMemoB(() => safeTraces.filter(t => {
    if (filterStatus !== 'all' && t.status !== filterStatus) return false;
    if (filterClient !== 'all' && t.client !== filterClient) return false;
    if (search && !(t.incomingModel.includes(search) || t.id.includes(search) || t.client.toLowerCase().includes(search.toLowerCase()))) return false;
    return true;
  }), [safeTraces, search, filterStatus, filterClient]);

  const sel = safeTraces.find(t => t.id === selectedId) || safeTraces[0];

  const replay = () => {
    const t = { ...sel, id: 'tr_' + Math.floor(Math.random() * 0xfffff).toString(16).padStart(5, '0'), time: window.fmtTime(new Date()), replayed: true };
    setTraces([t, ...traces]);
    setSelectedId(t.id);
  };

  return (
    <div className="col" style={{ gap: 12 }}>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
          <Icon name="search" size={12} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-3)' }} />
          <input className="input mono" placeholder="搜索 trace id / 模型 / 客户端…" value={search} onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 30 }} />
        </div>
        <select className="select" style={{ width: 130 }} value={filterClient} onChange={e=>setFilterClient(e.target.value)}>
          <option value="all">全部客户端</option>
          <option value="Claude Code">Claude Code</option>
          <option value="OpenAI SDK">OpenAI SDK</option>
          <option value="curl">curl</option>
          <option value="Cursor">Cursor</option>
        </select>
        <select className="select" style={{ width: 110 }} value={filterStatus} onChange={e=>setFilterStatus(e.target.value)}>
          <option value="all">全部状态</option>
          <option value="success">成功</option>
          <option value="warn">警告</option>
          <option value="err">错误</option>
        </select>
        <Seg options={[{value:'1h',label:'1h'},{value:'24h',label:'24h'},{value:'7d',label:'7d'}]} value="24h" onChange={()=>{}} />
        <button className="btn sm"><Icon name="filter" size={11}/></button>
        <button className="btn sm"><Icon name="download" size={11}/> 导出</button>
      </div>

      <div className="trace-layout">
        {/* Left: list */}
        <div className="card trace-list">
          <div style={{ display: 'grid', gridTemplateColumns: '60px 1fr 1fr 60px 60px 80px', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--line)', position: 'sticky', top: 0, background: 'var(--bg-1)', zIndex: 1 }}>
            <div className="label">时间</div>
            <div className="label">入站</div>
            <div className="label">→ 上游</div>
            <div className="label" style={{ textAlign: 'right' }}>延迟</div>
            <div className="label" style={{ textAlign: 'right' }}>费用</div>
            <div className="label">状态</div>
          </div>
          {filtered.map(t => (
            <div key={t.id} className={`trace-row ${t.id === selectedId ? 'selected' : ''}`} onClick={() => setSelectedId(t.id)}>
              <div className="t">{t.time}</div>
              <div className="m" title={t.incomingModel}>
                {t.incomingModel.replace('claude-', 'c-').replace('-latest', '')}
                {t.replayed && <span className="badge violet" style={{ marginLeft: 4, fontSize: 9 }}>重放</span>}
              </div>
              <div className="m text-accent" title={t.resolvedModel}>{t.resolvedModel}</div>
              <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>{t.latencyMs}</div>
              <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-3)' }}>${t.costUsd.toFixed(4)}</div>
              <div><StatusBadge status={t.status} /></div>
            </div>
          ))}
          {filtered.length === 0 && <div className="empty">没有匹配的追踪。</div>}
        </div>

        {/* Right: detail */}
        <div className="card trace-detail">
          <div className="card-h">
            <div className="row" style={{ gap: 12 }}>
              <div className="t"><Icon name="search" size={14}/> <span className="mono">{sel.id}</span></div>
              <StatusBadge status={sel.status} />
              {sel.replayed && <span className="badge violet"><span className="dot"/>已重放</span>}
              {sel.fallback && <span className="badge warn"><span className="dot"/>启用兜底</span>}
              {sel.streamed && <span className="badge accent"><span className="dot"/>streaming</span>}
              {sel.sanitizer === 'cch stripped' && <span className="badge violet"><span className="dot"/>cch stripped</span>}
              <span className="badge subtle">alias resolved</span>
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className="btn sm" onClick={replay}><Icon name="play" size={11}/> 重放</button>
              <button className="btn sm"><Icon name="download" size={11}/> JSON</button>
              <button className="btn sm"><Icon name="download" size={11}/> Markdown</button>
              <CopyButton text={sel.id} variant="copy-btn" label="trace id" />
              <button className="btn sm ghost danger"><Icon name="trash" size={11}/></button>
            </div>
          </div>

          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--line)', display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
            <Kv k="时间" v={sel.time} />
            <Kv k="客户端" v={sel.client} />
            <Kv k="入站模型" v={sel.incomingModel} />
            <Kv k="解析为" v={sel.resolvedModel} accent />
            <Kv k="延迟 / Tokens / 费用" v={`${sel.latencyMs}ms · ${sel.inputTokens}→${sel.outputTokens} · $${sel.costUsd.toFixed(4)}`} />
          </div>

          <div className="tabs">
            {[
              { v: 'timeline',  l: '时间线',  c: sel.steps.length },
              { v: 'incoming',  l: '入站',    c: null },
              { v: 'normalized',l: '规范化',  c: null },
              { v: 'sanitized', l: '清洗',    c: sel.sanitizer === 'cch stripped' ? 2 : 0 },
              { v: 'upstream',  l: '上游',    c: null },
              { v: 'response',  l: '响应',    c: null },
              { v: 'errors',    l: '错误',    c: sel.status === 'err' ? 1 : 0 },
            ].map(t => (
              <button key={t.v} className={tab === t.v ? 'active' : ''} onClick={() => setTab(t.v)}>
                {t.l}{t.c != null && <span className="count">{t.c}</span>}
              </button>
            ))}
          </div>

          <div style={{ padding: 14, overflow: 'auto', flex: 1 }}>
            {tab === 'timeline' && <TraceTimeline steps={sel.steps} />}
            {tab === 'incoming' && (
              <PayloadViewer data={sel.request ? {
                method: 'POST',
                path: sel.raw?.client_protocol === 'openai' ? '/openai/v1/chat/completions' : '/v1/messages',
                headers: sel.request.headers || {},
                body: sel.request.body || {},
              } : {
                method: 'POST', path: '/v1/messages',
                headers: {
                  'host': '127.0.0.1:8787',
                  'authorization': 'Bearer sk-superds-local-...',
                  'anthropic-version': '2023-06-01',
                  'x-anthropic-billing-header': 'cch=9f31a2bd7c4e1f8a',
                  'content-type': 'application/json',
                  'user-agent': 'claude-code/1.0.40',
                },
                body: {
                  model: sel.incomingModel,
                  stream: true,
                  max_tokens: 4096,
                  system: 'You are Claude Code, Anthropic\u2019s official CLI for Claude.',
                  messages: [{ role: 'user', content: 'Refactor this function to use async/await.' }],
                  tools: [{ name: 'read_file', description: 'Read a file', input_schema: { type: 'object' } }],
                },
              }} />
            )}
            {tab === 'normalized' && (
              <PayloadViewer data={sel.request?.route_attempts ? {
                protocol: 'internal/v1',
                model_alias: sel.incomingModel,
                resolved_model: sel.resolvedModel,
                route_attempts: sel.request.route_attempts,
                sanitizer: sel.raw?.sanitizer || sel.sanitizer,
              } : {
                protocol: 'internal/v1', model_alias: sel.incomingModel, role: 'fast_tool',
                system: ['You are Claude Code, Anthropic\u2019s official CLI for Claude.'],
                messages: [{ role: 'user', content: 'Refactor this function to use async/await.' }],
                tools: [{ name: 'read_file', description: 'Read a file', schema: '{...}' }],
                meta: { stream: true, max_tokens: 4096, normalized_at: sel.time },
              }} />
            )}
            {tab === 'sanitized' && (
              <div className="col" style={{ gap: 14 }}>
                <SanitizerDiff before={window.SANITIZER_BEFORE} after={window.SANITIZER_AFTER} />
                <div className="alert ok"><Icon name="check" size={16} className="ico"/><div><div className="ttl">前缀缓存安全</div>本次请求的入站 system + 工具 schema 与历史请求保持一致；剥离 cch 后哈希命中。</div></div>
              </div>
            )}
            {tab === 'upstream' && (
              <PayloadViewer data={sel.request?.upstream_payload ? {
                target: sel.raw?.upstream_provider_id || 'upstream',
                method: 'POST',
                body: sel.request.upstream_payload,
                route_attempts: sel.request.route_attempts || [],
              } : {
                target: 'https://api.deepseek.com/v1/chat/completions',
                method: 'POST',
                headers: { 'authorization': 'Bearer sk-...redacted', 'content-type': 'application/json' },
                body: {
                  model: sel.resolvedModel, stream: true, temperature: 0,
                  messages: [
                    { role: 'system', content: 'You are Claude Code, Anthropic\u2019s official CLI for Claude.' },
                    { role: 'user', content: 'Refactor this function to use async/await.' },
                  ],
                  tools: [{ type: 'function', function: { name: 'read_file', description: 'Read a file', parameters: {} } }],
                },
              }} />
            )}
            {tab === 'response' && (
              <PayloadViewer data={sel.response || {
                status: 200, stream: true, chunks: sel.outputTokens, finish_reason: 'stop',
                content: 'Sure — here is a refactor:\n```ts\nasync function load(url){…}\n```',
                usage: { input_tokens: sel.inputTokens, output_tokens: sel.outputTokens },
              }} />
            )}
            {tab === 'errors' && (
              sel.status === 'err'
                ? <PayloadViewer data={{ error: { type: 'upstream_timeout', code: 'ETIMEDOUT', message: '上游 deepseek-chat 在 30000ms 内无响应' } }} />
                : <div className="empty">本次追踪没有错误。</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
function Kv({ k, v, accent }) {
  return (
    <div className="col" style={{ gap: 2 }}>
      <div className="label">{k}</div>
      <div className={`mono ${accent ? 'text-accent' : ''}`} style={{ fontSize: 12 }}>{v}</div>
    </div>
  );
}

// ============ Page: Sanitizer & Cache ============
function PageSanitizer() {
  const [policy, setPolicy] = useStateB('strip-non-anthropic');
  const stripped = policy !== 'pass';
  const cacheRate = policy === 'pass' ? 38 : policy === 'always-strip' ? 92 : policy === 'canonicalize' ? 88 : 76;

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="card">
        <div className="card-h">
          <div className="t"><Icon name="broom" size={14}/> Claude 账单头清洗器</div>
          <span className="badge violet"><span className="dot"/>检测到 1,422 / 1,842</span>
        </div>
        <div className="card-b col" style={{ gap: 14 }}>
          <div className="muted" style={{ fontSize: 12.5, maxWidth: 760 }}>
            部分 Claude Code 请求会带上一行 <code className="mono">x-anthropic-billing-header</code>，其中 <code className="mono">cch</code> 值在每次会话都会变。直接转发到第三方上游会破坏 <b>前缀缓存稳定性</b>。Super DeepSeek 可以在路由前剥离或规范化这一行。
          </div>

          <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {[
              { v: 'pass', t: '透传', d: '原样转发，可能击穿缓存' },
              { v: 'strip-non-anthropic', t: '非 Anthropic 上游剥离', d: '推荐 · 仅在第三方上游时剥离' },
              { v: 'always-strip', t: '始终剥离', d: '一律删除该 header' },
              { v: 'canonicalize', t: '规范化', d: '将 cch 替换为常量值' },
            ].map(o => (
              <button key={o.v} className="prov-card" onClick={() => setPolicy(o.v)} style={{ borderColor: policy === o.v ? 'var(--accent)' : 'var(--line)', textAlign: 'left' }}>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <div style={{ fontWeight: 600, fontSize: 12.5 }}>{o.t}</div>
                  {policy === o.v && <Icon name="check" size={12} className="text-accent" />}
                </div>
                <div className="muted tiny" style={{ marginTop: 4 }}>{o.d}</div>
              </button>
            ))}
          </div>

          <div className="row" style={{ gap: 24, paddingTop: 4 }}>
            <Kv k="检测计数 (24h)" v="1,422" />
            <Kv k="最近动作" v={stripped ? '剥离 (cch=9f31a2…)' : '透传'} />
            <Kv k="预估缓存友好率" v={`${cacheRate}%`} accent />
          </div>

          <div>
            <div className="label" style={{ marginBottom: 8 }}>样本 · 清洗前 / 清洗后</div>
            <SanitizerDiff before={window.SANITIZER_BEFORE} after={window.SANITIZER_AFTER} />
          </div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1.4fr', gap: 14 }}>
        <div className="card">
          <div className="card-h"><div className="t"><Icon name="database" size={14}/> 缓存稳定性</div></div>
          <div className="card-b" style={{ padding: 0 }}>
            {[
              { l: '系统前缀稳定',        ok: 'ok',   v: '是' },
              { l: '工具 schema 顺序稳定', ok: 'ok',   v: '是' },
              { l: '检测到时间戳波动',    ok: 'warn', v: '在 1 处' },
              { l: '账单头已剥离',        ok: stripped ? 'ok' : 'err', v: stripped ? '是' : '否' },
              { l: '预估缓存友好率',      ok: cacheRate > 70 ? 'ok' : cacheRate > 50 ? 'warn' : 'err', v: `${cacheRate}%` },
            ].map((it, i) => (
              <div key={i} className={`compat-row ${it.ok === 'warn' ? 'warn' : it.ok === 'err' ? 'err' : ''}`}>
                <div className="ico"><Icon name={it.ok === 'ok' ? 'check' : it.ok === 'warn' ? 'alert' : 'x'} size={14} stroke={2.5} /></div>
                <div style={{ fontSize: 12.5 }}>{it.l}</div>
                <div className="mono" style={{ fontSize: 12, color: it.ok === 'ok' ? 'var(--ok)' : it.ok === 'warn' ? 'var(--warn)' : 'var(--err)' }}>{it.v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-h">
            <div className="t"><Icon name="activity" size={14}/> 24 小时清洗趋势</div>
            <div className="row" style={{ gap: 14, fontSize: 11 }}>
              <span className="row" style={{ gap: 5 }}><i style={{ width: 8, height: 2, background: 'var(--text-2)' }} /><span className="muted">请求</span></span>
              <span className="row" style={{ gap: 5 }}><i style={{ width: 8, height: 2, background: 'var(--accent)' }} /><span className="muted">缓存友好</span></span>
              <span className="row" style={{ gap: 5 }}><i style={{ width: 8, height: 2, background: 'var(--violet)' }} /><span className="muted">已清洗</span></span>
            </div>
          </div>
          <div className="card-b">
            <AreaChart
              series={[
                { name: '请求', data: window.VOLUME_24H, color: '#a8aeb8', fill: false },
                { name: '缓存友好', data: window.CACHE_SAFE_24H, color: '#5eead4' },
                { name: '已清洗', data: window.SANITIZED_24H, color: '#c084fc', fill: false },
              ]}
              labels={Array.from({length:48},(_,i)=>String(Math.floor(i/2)).padStart(2,'0')+':'+(i%2?'30':'00'))}
              height={200}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ============ Page: Settings ============
function PageSettings({ runtime, setRuntime }) {
  return (
    <div className="col" style={{ gap: 14, maxWidth: 920 }}>
      <SettingsSection title="服务" icon="server">
        <div className="grid grid-3">
          <Field label="Host"><input className="input mono" defaultValue="127.0.0.1" /></Field>
          <Field label="端口"><input className="input mono" defaultValue="8787" /></Field>
          <Field label="仅监听本机" align="end"><Switch on={true} onChange={()=>{}} /></Field>
        </div>
        <div className="field">
          <div className="field-label">运行模式</div>
          <div className="row" style={{ gap: 6 }}>
            {[
              { v: 'passthrough', l: '透传',  d: '不修改上下游内容' },
              { v: 'observe',     l: '观测',  d: '记录但不改写' },
              { v: 'augment',     l: '增强',  d: '清洗 / 注入 / 改写' },
              { v: 'strict',      l: '严格',  d: '强制安全策略与缓存优化' },
            ].map(o => (
              <button key={o.v} className="prov-card" onClick={()=>setRuntime(o.v)} style={{ flex: 1, borderColor: runtime === o.v ? 'var(--accent)' : 'var(--line)', textAlign: 'left', padding: 12 }}>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <div style={{ fontWeight: 600, fontSize: 12.5 }}>{o.l}</div>
                  {runtime === o.v && <Icon name="check" size={12} className="text-accent" />}
                </div>
                <div className="muted tiny" style={{ marginTop: 4 }}>{o.d}</div>
              </button>
            ))}
          </div>
        </div>
      </SettingsSection>

      <SettingsSection title="安全" icon="shield">
        <Field label="本地 API Key">
          <div className="row" style={{ gap: 8 }}>
            <div style={{ flex: 1 }}><SecretInput value="sk-superds-local-change-me" readonly /></div>
            <button className="btn"><Icon name="refresh" size={12}/> 轮换 Key</button>
          </div>
        </Field>
        <ToggleRow label="日志中遮蔽密钥" desc="渲染前对所有 token / key 进行掩码" on={true} />
        <ToggleRow label="允许原始导出" desc="允许 JSON 导出包含未遮蔽的 payload" on={false} />
        <ToggleRow label="清除追踪前需确认" on={true} />
      </SettingsSection>

      <SettingsSection title="日志" icon="list">
        <div className="grid grid-2">
          <Field label="保留天数"><input className="input mono" defaultValue="7" /></Field>
          <Field label="最多存储 trace"><input className="input mono" defaultValue="5000" /></Field>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn danger"><Icon name="trash" size={12}/> 清空所有追踪</button>
          <button className="btn"><Icon name="download" size={12}/> 导出配置</button>
          <button className="btn"><Icon name="copy" size={12}/> 导入配置</button>
        </div>
      </SettingsSection>

      <SettingsSection title="高级" icon="cog">
        <div className="grid grid-2">
          <Field label="LiteLLM 模式">
            <select className="select" defaultValue="embedded">
              <option value="embedded">内嵌 (embedded)</option>
              <option value="sidecar">边车 (sidecar)</option>
            </select>
          </Field>
          <Field label="超时 (ms)"><input className="input mono" defaultValue="30000" /></Field>
          <Field label="重试次数"><input className="input mono" defaultValue="2" /></Field>
          <Field label="流缓冲大小 (KB)"><input className="input mono" defaultValue="64" /></Field>
        </div>
        <ToggleRow label="调试模式" desc="打印完整路由决策日志到 stdout" on={false} />
      </SettingsSection>
    </div>
  );
}

function SettingsSection({ title, icon, children }) {
  return (
    <div className="card">
      <div className="card-h"><div className="t"><Icon name={icon} size={14}/> {title}</div></div>
      <div className="card-b col" style={{ gap: 12 }}>{children}</div>
    </div>
  );
}
function Field({ label, children, align }) {
  return (
    <div className="field" style={align === 'end' ? { alignSelf: 'flex-end' } : {}}>
      <div className="field-label">{label}</div>
      <div className="row" style={align === 'end' ? { height: 32, alignItems: 'center' } : {}}>{children}</div>
    </div>
  );
}
function ToggleRow({ label, desc, on: initial }) {
  const [on, setOn] = useStateB(initial);
  return (
    <div className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderTop: '1px solid var(--line)' }}>
      <div>
        <div style={{ fontSize: 12.5 }}>{label}</div>
        {desc && <div className="muted tiny" style={{ marginTop: 2 }}>{desc}</div>}
      </div>
      <Switch on={on} onChange={setOn} />
    </div>
  );
}

Object.assign(window, { PageClaude, PageTraces, PageSanitizer, PageSettings });
