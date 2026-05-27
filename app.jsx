// App shell: sidebar + topbar + router
const { useState: useStateApp, useEffect: useEffectApp } = React;

const NAV = [
  { id: 'overview',  label: '概览',          ico: 'activity',  count: null },
  { id: 'setup',     label: '配置向导',      ico: 'wand',      count: null },
  { id: 'providers', label: '上游服务',      ico: 'plug',      count: 5 },
  { id: 'profiles',  label: '模型方案',      ico: 'layers',    count: 3 },
  { id: 'claude',    label: 'Claude Code',   ico: 'sparkles',  count: null, hot: true },
  { id: 'traces',    label: '请求追踪',      ico: 'search',    count: 42 },
  { id: 'sanitizer', label: '清洗与缓存',    ico: 'broom',     count: null },
  { id: 'settings',  label: '设置',          ico: 'cog',       count: null },
];

const PAGE_META = {
  overview:  { crumb: 'gateway / overview',                  h: '概览',                desc: '本地网关运行状态、请求量与最近活动。' },
  setup:     { crumb: 'gateway / setup-wizard',              h: '配置向导',            desc: '四步把 Claude Code 接到本地网关。' },
  providers: { crumb: 'gateway / providers',                 h: '上游服务',            desc: '管理 OpenAI 兼容的上游：DeepSeek / Qwen / vLLM / OpenRouter / 自定义。' },
  profiles:  { crumb: 'gateway / profiles',                  h: '模型方案',            desc: '把角色（主、快速/工具、推理、视觉、兜底）映射到真实上游模型。' },
  claude:    { crumb: 'gateway / claude-code-compatibility', h: 'Claude Code 兼容',    desc: 'Claude 风格的模型别名 → 你的上游。' },
  traces:    { crumb: 'gateway / traces',                    h: '请求追踪',            desc: '每条请求的入站 / 规范化 / 清洗 / 上游 / 响应详情。' },
  sanitizer: { crumb: 'gateway / sanitizer-cache',           h: '清洗与缓存',          desc: '账单头清洗策略，前缀缓存稳定性。' },
  settings:  { crumb: 'gateway / settings',                  h: '设置',                desc: '服务、安全、日志与高级参数。' },
};

const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
  "accent": "#5eead4",
  "density": "comfortable",
  "showHaikuWarning": true,
  "showTopbarTraffic": true
}/*EDITMODE-END*/;

function App() {
  const [active, setActive] = useStateApp('overview');
  const [traceFocus, setTraceFocus] = useStateApp(null);
  const [drawer, setDrawer] = useStateApp(null);
  const [runtime, setRuntime] = useStateApp('augment');
  const [aliases, setAliases] = useStateApp(window.ALIASES);
  const [traces, setTraces] = useStateApp([]);
  const [providers, setProviders] = useStateApp(window.PROVIDERS);
  const [presets, setPresets] = useStateApp([]);
  const [modelCaps, setModelCaps] = useStateApp([]);
  const [profiles, setProfiles] = useStateApp(window.PROFILES);
  const [models, setModels] = useStateApp([]);
  const [defaultProfile, setDefaultProfile] = useStateApp('default');
  const [health, setHealth] = useStateApp(null);
  const [serverOn, setServerOn] = useStateApp(true);
  const [envCopied, setEnvCopied] = useStateApp(false);
  const [t, setTweak] = window.useTweaks ? window.useTweaks(TWEAK_DEFAULS) : [TWEAK_DEFAULS, ()=>{}];

  // Apply accent
  useEffectApp(() => {
    document.documentElement.style.setProperty('--accent', t.accent);
    const c = t.accent;
    document.documentElement.style.setProperty('--accent-soft', hexToRgba(c, 0.08));
    document.documentElement.style.setProperty('--accent-line', hexToRgba(c, 0.25));
  }, [t.accent]);

  useEffectApp(() => {
    if (!window.SuperDSApi) return;
    let cancelled = false;
    const loadLiveData = async () => {
      try {
        const [h, ps, prs, trs, caps, profileData, aliasData] = await Promise.all([
          window.SuperDSApi.health(),
          window.SuperDSApi.providers(),
          window.SuperDSApi.presets(),
          window.SuperDSApi.traces(80),
          window.SuperDSApi.modelCapabilities(),
          window.SuperDSApi.profiles(),
          window.SuperDSApi.aliases(),
        ]);
        if (cancelled) return;
        setHealth(h);
        setServerOn(Boolean(h.ok));
        setProviders(ps);
        setPresets(prs);
        setTraces(trs);
        setModelCaps(caps);
        setProfiles(profileData.profiles);
        setModels(profileData.models);
        setDefaultProfile(profileData.defaultProfile);
        setAliases(aliasData);
      } catch (e) {
        if (!cancelled) setServerOn(false);
      }
    };
    loadLiveData();
    const timer = setInterval(loadLiveData, 8000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  const goto = (id, ctx) => {
    setActive(id);
    if (id === 'traces') setTraceFocus(ctx || null);
  };
  const localEnvText = () => [
    'export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"',
    `export ANTHROPIC_API_KEY="${window.SuperDSApi?.localKey || 'sk-superds-local-change-me'}"`,
    'export OPENAI_BASE_URL="http://127.0.0.1:8787/openai/v1"',
    `export OPENAI_API_KEY="${window.SuperDSApi?.localKey || 'sk-superds-local-change-me'}"`,
  ].join('\n');
  const copyLocalEnv = async () => {
    const text = localEnvText();
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const el = document.createElement('textarea');
      el.value = text;
      el.setAttribute('readonly', '');
      el.style.position = 'fixed';
      el.style.opacity = '0';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    setEnvCopied(true);
    setTimeout(() => setEnvCopied(false), 1400);
  };

  const meta = PAGE_META[active];

  return (
    <div className={`app ${t.density === 'compact' ? 'dense' : ''}`}>
      <SpinStyle />

      {/* ============ TOPBAR ============ */}
      <div className="topbar">
        <div className="brand">
          <div className="brand-mark">SDS</div>
          <div className="brand-name">Super DeepSeek<span className="sub mono">v0.6.2</span></div>
        </div>

        <span className={`chip ${serverOn ? 'live' : ''}`} onClick={() => setServerOn(!serverOn)} style={{ cursor: 'pointer' }} title="点击切换服务状态">
          <span className="dot pulse" />
          {serverOn ? '在线' : '离线'}
        </span>
        <span className="chip mono"><Icon name="server" size={11}/> 127.0.0.1:8787</span>

        <div className="runtime">
          {[
            { v: 'passthrough', l: '透传' },
            { v: 'observe',     l: '观测' },
            { v: 'augment',     l: '增强' },
            { v: 'strict',      l: '严格' },
          ].map(o => (
            <button key={o.v} className={runtime === o.v ? 'active' : ''} onClick={() => setRuntime(o.v)}>{o.l}</button>
          ))}
        </div>

        <span className="chip">
          <Icon name="layers" size={11}/> 方案：<span className="mono" style={{ color: 'var(--text)' }}>{defaultProfile}</span>
        </span>

        <div className="spacer" />

        {t.showTopbarTraffic && (

          <span className="chip mono" title="活跃 / 待处理">
            <span style={{ color: 'var(--ok)' }}>● 2</span>
            <span className="muted">·</span>
            <span style={{ color: 'var(--text-2)' }}>{traces.length}</span>
            <span className="muted">traces</span>
          </span>
        )}

        <button className="btn-mini primary" onClick={copyLocalEnv}>
          <Icon name={envCopied ? 'check' : 'copy'} size={11}/> {envCopied ? '已复制' : '复制本地环境变量'}
        </button>
        <button className="btn-mini" onClick={async () => {
          if (window.SuperDSApi) await window.SuperDSApi.clearLogs();
          setTraces([]);
        }}><Icon name="trash" size={11}/> 清空日志</button>
      </div>

      {/* ============ SIDEBAR ============ */}
      <div className="sidebar">
        <div className="group-title">主功能</div>
        <div className="col" style={{ gap: 1 }}>
          {NAV.slice(0, 4).map(n => (
            <button key={n.id} className={`nav-item ${active === n.id ? 'active' : ''}`} onClick={() => setActive(n.id)}>
              <Icon name={n.ico} size={15} className="ico" />
              <span>{n.label}</span>
              {n.count != null && <span className="count">{n.count}</span>}
            </button>
          ))}
        </div>
        <div className="group-title">观测</div>
        <div className="col" style={{ gap: 1 }}>
          {NAV.slice(4, 7).map(n => (
            <button key={n.id} className={`nav-item ${active === n.id ? 'active' : ''}`} onClick={() => setActive(n.id)}>
              <Icon name={n.ico} size={15} className="ico" />
              <span>{n.label}</span>
              {n.hot && <span className="badge accent" style={{ marginLeft: 'auto' }}>核心</span>}
              {n.count != null && <span className="count">{n.count}</span>}
            </button>
          ))}
        </div>
        <div className="group-title">系统</div>
        <div className="col" style={{ gap: 1 }}>
          {NAV.slice(7).map(n => (
            <button key={n.id} className={`nav-item ${active === n.id ? 'active' : ''}`} onClick={() => setActive(n.id)}>
              <Icon name={n.ico} size={15} className="ico" />
              <span>{n.label}</span>
            </button>
          ))}
        </div>

        <div className="sidebar-foot mono">
          <div className="row">
            <span>构建</span><span>0.6.2 · b9c2f1a</span>
          </div>
          <div className="row">
            <span>LiteLLM</span><span>1.52.3</span>
          </div>
          <div className="row">
            <span>Uptime</span><span className="text-ok">2h 41m</span>
          </div>
        </div>
      </div>

      {/* ============ MAIN ============ */}
      <div className="main">
        <div className="page-head">
          <div>
            <div className="crumbs">{meta.crumb}</div>
            <h1>{meta.h}</h1>
            <div className="desc">{meta.desc}</div>
          </div>
          <div className="actions">
            {active === 'traces' && (
              <>
                <button className="btn"><Icon name="refresh" size={12}/> 自动刷新</button>
                <button className="btn"><Icon name="filter" size={12}/> 高级筛选</button>
              </>
            )}
            {active === 'providers' && (
              <button className="btn primary" onClick={() => setDrawer({ kind: 'provider-new' })}>
                <Icon name="plus" size={12} /> 添加上游
              </button>
            )}
            {active === 'claude' && (
              <>
                <button className="btn"><Icon name="play" size={12}/> 发一个测试请求</button>
                <button className="btn primary"><Icon name="copy" size={12}/> 复制 env</button>
              </>
            )}
          </div>
        </div>

        {active === 'overview'  && <PageOverview  goto={goto} traces={traces} providers={providers} />}
        {active === 'setup'     && <PageSetup     goto={goto} />}
        {active === 'providers' && <PageProviders openDrawer={setDrawer} providers={providers} presets={presets} onProvidersChange={setProviders} />}
        {active === 'profiles'  && (
          <PageProfiles
            modelCaps={modelCaps}
            profiles={profiles}
            models={models}
            providers={providers}
            defaultProfile={defaultProfile}
            onProfilesChange={setProfiles}
            onDefaultProfileChange={setDefaultProfile}
            onModelCapsChange={setModelCaps}
          />
        )}
        {active === 'claude'    && <PageClaude    aliases={aliases} setAliases={setAliases} profiles={profiles} showHaikuWarning={t.showHaikuWarning} />}
        {active === 'traces'    && <PageTraces    initialId={traceFocus} traces={traces} setTraces={setTraces} />}
        {active === 'sanitizer' && <PageSanitizer />}
        {active === 'settings'  && <PageSettings  runtime={runtime} setRuntime={setRuntime} />}
      </div>

      {/* ============ DRAWER ============ */}
      {drawer && (
        <ProviderDrawer
          drawer={drawer}
          onClose={() => setDrawer(null)}
          onSaved={async () => {
            if (window.SuperDSApi) {
              setProviders(await window.SuperDSApi.providers());
            }
          }}
        />
      )}

      {/* ============ TWEAKS ============ */}
      {window.TweaksPanel && (
        <window.TweaksPanel title="Tweaks">
          <window.TweakSection label="外观">
            <window.TweakColor label="强调色" value={t.accent}
              onChange={(v) => setTweak('accent', v)}
              options={['#5eead4','#60a5fa','#fbbf24','#c084fc','#fb923c','#4ade80']} />
            <window.TweakRadio label="密度" value={t.density}
              onChange={(v) => setTweak('density', v)}
              options={[{value:'comfortable',label:'宽松'},{value:'compact',label:'紧凑'}]} />
          </window.TweakSection>
          <window.TweakSection label="提示">
            <window.TweakToggle label="顶栏显示流量" value={t.showTopbarTraffic} onChange={(v)=>setTweak('showTopbarTraffic', v)} />
            <window.TweakToggle label="Haiku 警告（Claude 页）" value={t.showHaikuWarning} onChange={(v)=>setTweak('showHaikuWarning', v)} />
          </window.TweakSection>
          <window.TweakSection label="导航">
            <window.TweakSelect label="跳转页面" value={active} onChange={setActive}
              options={NAV.map(n => ({ value: n.id, label: n.label }))} />
          </window.TweakSection>
        </window.TweaksPanel>
      )}
    </div>
  );
}

function ProviderDrawer({ drawer, onClose, onSaved }) {
  const p = drawer.payload || {};
  const isEdit = drawer.kind === 'provider-edit';
  const initialModels = normalizeModelListApp(p.models || p.suggestedModels || p.defaultModel || '');
  const [name, setName] = useStateApp(p.name || '');
  const [protocol, setProtocol] = useStateApp((p.protocol || '').includes('Anthropic') ? 'anthropic' : 'openai');
  const [baseUrl, setBaseUrl] = useStateApp(p.baseUrl || '');
  const [apiKeyEnv, setApiKeyEnv] = useStateApp(p.apiKeyEnv || p.api_key_env || '');
  const [apiKey, setApiKey] = useStateApp('');
  const [defaultModel, setDefaultModel] = useStateApp(p.defaultModel || '');
  const [modelText, setModelText] = useStateApp(initialModels.join('\n'));
  const [saving, setSaving] = useStateApp(false);
  const modelList = () => normalizeModelListApp(modelText);
  const providerPayload = () => {
    const models = modelList();
    return {
      id: p.id,
      name,
      protocol,
      base_url: baseUrl,
      api_key_env: apiKeyEnv,
      api_key: apiKey,
      default_model: defaultModel || models[0] || '',
      models,
    };
  };
  const addModel = (model) => {
    const next = normalizeModelListApp([...modelList(), model]);
    setModelText(next.join('\n'));
    if (!defaultModel && model) setDefaultModel(model);
  };
  const save = async () => {
    setSaving(true);
    try {
      if (window.SuperDSApi) {
        await window.SuperDSApi.saveProvider(providerPayload());
        onSaved && await onSaved();
      }
      onClose();
    } finally {
      setSaving(false);
    }
  };
  return (
    <>
      <div className="drawer-back" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-h">
          <div className="t row" style={{ gap: 10 }}>
            <Icon name="plug" size={14} />
            <span style={{ fontWeight: 600 }}>{isEdit ? `编辑上游 · ${p.name}` : '添加上游'}</span>
          </div>
          <button className="btn sm ghost" onClick={onClose}><Icon name="x" size={12}/></button>
        </div>
        <div className="drawer-b">
          <Field2 label="名称"><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：DeepSeek" /></Field2>
          <Field2 label="协议">
            <select className="select" value={protocol} onChange={(e) => setProtocol(e.target.value)}>
              <option value="openai">OpenAI 兼容</option>
              <option value="anthropic">Anthropic 兼容</option>
              <option value="litellm">LiteLLM</option>
            </select>
          </Field2>
          <Field2 label="Base URL"><input className="input mono" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.example.com/v1" /></Field2>
          <Field2 label="环境变量名"><input className="input mono" value={apiKeyEnv} onChange={(e) => setApiKeyEnv(e.target.value)} placeholder="DEEPSEEK_API_KEY" /></Field2>
          <Field2 label="API Key"><SecretInput value={apiKey} onChange={setApiKey} placeholder={isEdit && p.apiKeyStatus === 'configured' ? '留空则保留已保存密钥' : 'sk-...'} /></Field2>
          <Field2 label="模型列表">
            <textarea
              className="input mono"
              value={modelText}
              onChange={(e) => {
                setModelText(e.target.value);
                const next = normalizeModelListApp(e.target.value);
                if (!defaultModel && next[0]) setDefaultModel(next[0]);
              }}
              placeholder={'deepseek-chat\ndeepseek-reasoner'}
              rows={5}
              style={{ resize: 'vertical', minHeight: 112, lineHeight: 1.5 }}
            />
            {p.suggestedModels?.length > 0 && (
              <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                {p.suggestedModels.map(m => (
                  <button key={m} className="btn-mini mono" onClick={() => addModel(m)}>{m}</button>
                ))}
              </div>
            )}
          </Field2>
          <Field2 label="默认模型">
            <select className="select mono" value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)}>
              <option value="">使用第一个模型</option>
              {modelList().map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </Field2>
          <Field2 label="LiteLLM 模型字符串（可选）"><input className="input mono" placeholder="openai/deepseek-chat" /></Field2>
          <div className="grid grid-2">
            <Field2 label="超时 (ms)"><input className="input mono" defaultValue="30000" /></Field2>
            <Field2 label="重试次数"><input className="input mono" defaultValue="2" /></Field2>
          </div>
          <div className="divider"/>
          <ConnectionTestButton providerId={p.id || 'custom'} model={defaultModel} provider={providerPayload()} />
        </div>
        <div className="drawer-f">
          <button className="btn ghost" onClick={onClose}>取消</button>
          <button className="btn primary" onClick={save} disabled={saving}>{saving ? '正在保存…' : isEdit ? '保存修改' : '添加上游'}</button>
        </div>
      </div>
    </>
  );
}
function normalizeModelListApp(raw) {
  const rows = Array.isArray(raw) ? raw : String(raw || '').split(/[\n,]+/);
  const out = [];
  const seen = new Set();
  rows.forEach(item => {
    const value = (typeof item === 'object' ? item?.id || item?.actual_model : item || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    out.push(value);
  });
  return out;
}
function Field2({ label, children }) {
  return (
    <div className="field"><div className="field-label">{label}</div>{children}</div>
  );
}

function hexToRgba(hex, a) {
  const h = hex.replace('#','');
  const r = parseInt(h.slice(0,2),16), g = parseInt(h.slice(2,4),16), b = parseInt(h.slice(4,6),16);
  return `rgba(${r},${g},${b},${a})`;
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
