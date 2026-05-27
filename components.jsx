// Shared components for Super DeepSeek dashboard
const { useState, useEffect, useRef, useMemo } = React;

// ---- Icons (lucide-style SVGs, inline) ----
const Icon = ({ name, size = 16, stroke = 2, className = '', ...rest }) => {
  const paths = {
    'activity':    '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    'server':      '<rect x="2" y="3" width="20" height="6" rx="2"/><rect x="2" y="15" width="20" height="6" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>',
    'wand':        '<path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8 19 13"/><path d="M15 9h0"/><path d="M17.8 6.2 19 5"/><path d="m3 21 9-9"/><path d="M12.2 6.2 11 5"/>',
    'plug':        '<path d="M12 22v-5"/><path d="M9 7V2"/><path d="M15 7V2"/><path d="M6 13V8a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4z"/>',
    'layers':      '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    'bot':         '<path d="M12 8V4H8"/><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    'search':      '<circle cx="11" cy="11" r="7"/><path d="m21 21-3.5-3.5"/>',
    'broom':       '<path d="m13.4 2.6 8 8L13 19a4 4 0 0 1-5.6 0L3 14.6a4 4 0 0 1 0-5.6L13.4 2.6z"/><path d="m11 7 6 6"/>',
    'cog':         '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    'check':       '<polyline points="20 6 9 17 4 12"/>',
    'x':           '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    'alert':       '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    'info':        '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    'copy':        '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    'eye':         '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    'eye-off':     '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><path d="m1 1 22 22"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/>',
    'play':        '<polygon points="5 3 19 12 5 21 5 3"/>',
    'refresh':     '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"/><path d="M20.49 15A9 9 0 0 1 5.64 18.36L1 14"/>',
    'trash':       '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    'plus':        '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    'edit':        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"/>',
    'chevron-r':   '<polyline points="9 18 15 12 9 6"/>',
    'chevron-d':   '<polyline points="6 9 12 15 18 9"/>',
    'arrow-right': '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    'download':    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    'filter':      '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    'database':    '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    'shield':      '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    'zap':         '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    'key':         '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
    'list':        '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
    'box':         '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    'route':       '<circle cx="6" cy="19" r="3"/><circle cx="18" cy="5" r="3"/><path d="M6.7 17.3 17.3 6.7"/>',
    'sparkles':    '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"/>',
    'lock':        '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    'terminal':    '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    'circle':      '<circle cx="12" cy="12" r="10"/>',
    'cpu':         '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="2" x2="9" y2="4"/><line x1="15" y1="2" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="22"/><line x1="15" y1="20" x2="15" y2="22"/><line x1="20" y1="9" x2="22" y2="9"/><line x1="20" y1="15" x2="22" y2="15"/><line x1="2" y1="9" x2="4" y2="9"/><line x1="2" y1="15" x2="4" y2="15"/>',
    'clock':       '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    'gauge':       '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} {...rest}
         dangerouslySetInnerHTML={{ __html: paths[name] || paths['circle'] }} />
  );
};

// ---- StatusBadge ----
const StatusBadge = ({ status, children, tone, className = '' }) => {
  const map = {
    healthy:    { c: 'ok',   label: '健康' },
    success:    { c: 'ok',   label: '成功' },
    online:     { c: 'ok',   label: '在线' },
    enabled:    { c: 'ok',   label: '已启用' },
    configured: { c: 'ok',   label: '已配置' },
    warn:       { c: 'warn', label: '警告' },
    pending:    { c: 'warn', label: '待定' },
    unknown:    { c: 'warn', label: '未知' },
    failed:     { c: 'err',  label: '失败' },
    err:        { c: 'err',  label: '错误' },
    error:      { c: 'err',  label: '错误' },
    offline:    { c: 'err',  label: '离线' },
    missing:    { c: 'err',  label: '缺失' },
    disabled:   { c: 'neutral', label: '已停用' },
    skip:       { c: 'neutral', label: '跳过' },
    info:       { c: 'info', label: '信息' },
  };
  const m = map[status] || { c: tone || 'neutral', label: status };
  return (
    <span className={`badge ${m.c} ${className}`}>
      <span className="dot"></span>
      {children || m.label}
    </span>
  );
};

// ---- MetricCard ----
const MetricCard = ({ label, value, unit, delta, icon, spark }) => (
  <div className="metric">
    <div className="lbl">
      {icon && <Icon name={icon} size={12} />}
      {label}
    </div>
    <div className="val">{value}{unit && <span className="unit">{unit}</span>}</div>
    {delta && (
      <div className={`delta ${delta.dir === 'up' ? 'up' : 'down'}`}>
        <Icon name={delta.dir === 'up' ? 'arrow-right' : 'arrow-right'} size={10}
              style={{ transform: delta.dir === 'up' ? 'rotate(-45deg)' : 'rotate(45deg)' }} />
        {delta.value}
      </div>
    )}
    {spark && <div className="spark"><Sparkline data={spark} width={70} height={22} color="var(--accent)" /></div>}
  </div>
);

// ---- Sparkline ----
const Sparkline = ({ data, width = 100, height = 28, color = 'var(--accent)', fill = true, strokeWidth = 1.5 }) => {
  if (!data || !data.length) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 2) - 1;
    return [x, y];
  });
  const line = points.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = line + ` L${width},${height} L0,${height} Z`;
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      {fill && <path d={area} fill={color} opacity={0.12} />}
      <path d={line} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
};

// ---- Line/Area chart ----
const AreaChart = ({ series, height = 180, labels }) => {
  // series: [{ name, data, color }]
  const W = 700, H = height, padL = 30, padR = 10, padT = 14, padB = 24;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const n = series[0].data.length;
  const allVals = series.flatMap(s => s.data);
  const maxV = Math.max(1, Math.ceil(Math.max(...allVals) * 1.15));
  const ticks = [0, Math.round(maxV / 2), maxV];

  const xOf = (i) => padL + (i / (n - 1)) * innerW;
  const yOf = (v) => padT + innerH - (v / maxV) * innerH;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={height} preserveAspectRatio="none" style={{ display: 'block' }}>
      {/* grid */}
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={yOf(t)} y2={yOf(t)} stroke="#1f242b" strokeDasharray="2 4" />
          <text x={padL - 6} y={yOf(t) + 3} fontSize="9" textAnchor="end" fill="#6a7079" fontFamily="var(--font-mono)">{t}</text>
        </g>
      ))}
      {labels && labels.map((l, i) => (
        i % 8 === 0 && <text key={i} x={xOf(i)} y={H - 6} fontSize="9" textAnchor="middle" fill="#6a7079" fontFamily="var(--font-mono)">{l}</text>
      ))}
      {series.map((s, si) => {
        const pts = s.data.map((v, i) => `${xOf(i)},${yOf(v)}`).join(' L');
        const area = `M${xOf(0)},${yOf(0)} L${pts} L${xOf(n - 1)},${yOf(0)} Z`;
        const line = `M${pts}`;
        return (
          <g key={si}>
            {s.fill !== false && <path d={area} fill={s.color} opacity="0.1" />}
            <path d={line} fill="none" stroke={s.color} strokeWidth="1.5" />
          </g>
        );
      })}
    </svg>
  );
};

// ---- CopyButton ----
const CopyButton = ({ text, label = '复制', size = 'sm', variant = 'btn', icon = 'copy' }) => {
  const [copied, setCopied] = useState(false);
  const onClick = (e) => {
    e.stopPropagation();
    if (navigator.clipboard) navigator.clipboard.writeText(typeof text === 'function' ? text() : text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  const cls = variant === 'btn' ? `btn ${size === 'sm' ? 'sm' : ''} ${copied ? 'primary' : ''}` : `copy-btn ${copied ? 'copied' : ''}`;
  return (
    <button className={cls} onClick={onClick}>
      <Icon name={copied ? 'check' : icon} size={12} />
      {copied ? '已复制' : label}
    </button>
  );
};

// ---- EnvVarCopyBlock ----
const EnvVarCopyBlock = ({ title, lines, badge }) => {
  const text = lines.map(l => l.raw || l).join('\n');
  return (
    <div className="card">
      <div className="card-h">
        <div className="t"><Icon name="terminal" size={14} /> {title}{badge && <span style={{ marginLeft: 8 }}>{badge}</span>}</div>
        <CopyButton text={text} variant="copy-btn" label="复制" />
      </div>
      <div className="card-b" style={{ padding: 0 }}>
        <pre className="code" style={{ borderRadius: 0, border: 'none', margin: 0 }}>
          {lines.map((l, i) => (
            <div key={i}>
              {typeof l === 'string' ? <span>{l}</span> : (
                <React.Fragment>
                  <span className="c">{l.cmd || 'export'} </span>
                  <span className="k">{l.k}</span>
                  <span>=</span>
                  <span className="s">"{l.v}"</span>
                </React.Fragment>
              )}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
};

// ---- Secret Input ----
const SecretInput = ({ value, placeholder, readonly, onChange }) => {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input
        className="input mono"
        type={show ? 'text' : 'password'}
        value={value || ''}
        placeholder={placeholder}
        readOnly={readonly}
        onChange={(e) => onChange && onChange(e.target.value)}
        style={{ paddingRight: 64 }}
      />
      <div style={{ position: 'absolute', right: 6, top: 4, display: 'flex', gap: 2 }}>
        <button className="btn sm ghost" onClick={() => setShow(!show)} title={show ? '隐藏' : '显示'}>
          <Icon name={show ? 'eye-off' : 'eye'} size={12} />
        </button>
        <CopyButton text={value || ''} variant="copy-btn" label="" icon="copy" />
      </div>
    </div>
  );
};

// ---- ConnectionTestButton ----
const ConnectionTestButton = ({ onResult, providerId = 'deepseek', model, provider }) => {
  const [state, setState] = useState('idle'); // idle | testing | ok | err
  const [info, setInfo] = useState(null);
  const run = async () => {
    setState('testing');
    setInfo(null);
    if (window.SuperDSApi) {
      try {
        const result = await window.SuperDSApi.testConnection({ providerId, model, provider });
        setState(result.ok ? 'ok' : 'err');
        setInfo(result);
        onResult && onResult(result);
        return;
      } catch (e) {
        const result = { ok: false, error: e.message };
        setState('err');
        setInfo(result);
        onResult && onResult(result);
        return;
      }
    }
    setTimeout(() => {
      const ok = Math.random() > 0.18;
      setState(ok ? 'ok' : 'err');
      const result = ok
        ? { ok: true, ms: 280 + Math.floor(Math.random() * 360), model: 'deepseek-chat', tokens: 8 }
        : { ok: false, msg: 'connect ECONNREFUSED — 检查 API key 或 base URL' };
      setInfo(result);
      onResult && onResult(result);
    }, 900);
  };
  return (
    <div className="col" style={{ gap: 8 }}>
      <button className={`btn ${state === 'ok' ? '' : state === 'err' ? 'danger' : 'primary'}`} onClick={run} disabled={state === 'testing'}>
        {state === 'testing' && <Icon name="refresh" size={12} className="spin" />}
        {state === 'testing' ? '正在测试…' : state === 'ok' ? <><Icon name="check" size={12} />连接成功</> : state === 'err' ? <><Icon name="alert" size={12} />连接失败</> : <><Icon name="plug" size={12} />测试连接</>}
      </button>
      {info && (
        <div className={`tiny mono ${info.ok ? 'text-ok' : 'text-err'}`} style={{ paddingLeft: 2 }}>
          {info.ok
            ? `${info.status || 'healthy'} · ${info.latency_ms ?? info.ms}ms · TTFB ${info.ttfb_ms ?? '—'}ms · model = ${info.model || 'deepseek-chat'}`
            : (info.error || info.msg || info.status)}
        </div>
      )}
    </div>
  );
};

// ---- JSON Viewer ----
const renderJson = (v, depth = 0, redactKeys = []) => {
  const indent = '  '.repeat(depth);
  if (v === null) return <span className="null">null</span>;
  if (typeof v === 'boolean') return <span className="bool">{String(v)}</span>;
  if (typeof v === 'number') return <span className="num">{v}</span>;
  if (typeof v === 'string') return <span className="str">"{v}"</span>;
  if (Array.isArray(v)) {
    if (!v.length) return <span>[]</span>;
    return (
      <span>{'['}
        {v.map((x, i) => (
          <div key={i} style={{ paddingLeft: 14 }}>
            {renderJson(x, depth + 1, redactKeys)}{i < v.length - 1 ? ',' : ''}
          </div>
        ))}
        {indent}{']'}
      </span>
    );
  }
  const entries = Object.entries(v);
  if (!entries.length) return <span>{'{}'}</span>;
  return (
    <span>{'{'}
      {entries.map(([k, x], i) => {
        const redact = redactKeys.includes(k.toLowerCase());
        return (
          <div key={k} style={{ paddingLeft: 14 }}>
            <span className="key">"{k}"</span>: {redact ? <span className="redact">"&lt;redacted&gt;"</span> : renderJson(x, depth + 1, redactKeys)}
            {i < entries.length - 1 ? ',' : ''}
          </div>
        );
      })}
      {indent}{'}'}
    </span>
  );
};
const PayloadViewer = ({ data, redact = ['authorization', 'api-key', 'x-api-key', 'x-anthropic-billing-header'] }) => (
  <div className="json">{renderJson(data, 0, redact)}</div>
);

// ---- TraceTimeline ----
const TraceTimeline = ({ steps }) => (
  <div className="timeline">
    {steps.map((s, i) => (
      <div key={i} className="tl-item">
        <div className={`tl-dot ${s.status === 'warn' ? 'warn' : s.status === 'err' ? 'err' : s.status === 'skip' ? 'skip' : ''}`}>
          {s.status === 'skip' && <div style={{ width: 4, height: 4, background: 'var(--text-4)', borderRadius: '50%', position: 'absolute', top: 3, left: 3 }} />}
        </div>
        <div>
          <div className="tl-name">
            {s.name}
            {s.status === 'skip' && <span className="badge subtle" style={{ marginLeft: 8 }}>跳过</span>}
            {s.status === 'warn' && <span className="badge warn" style={{ marginLeft: 8 }}>警告</span>}
            {s.status === 'err' && <span className="badge err" style={{ marginLeft: 8 }}>错误</span>}
          </div>
          <div className="tl-meta">{s.summary}</div>
        </div>
        <div className="tl-dur">{s.durationMs}ms</div>
      </div>
    ))}
  </div>
);

// ---- CompatibilityChecklist ----
const CompatibilityChecklist = ({ items }) => (
  <div>
    {items.map((it, i) => (
      <div key={i} className={`compat-row ${it.ok === 'warn' ? 'warn' : it.ok === 'err' ? 'err' : ''}`}>
        <div className="ico">
          <Icon name={it.ok === 'ok' ? 'check' : it.ok === 'warn' ? 'alert' : 'x'} size={16} stroke={2.5} />
        </div>
        <div>
          <div style={{ fontSize: 12.5 }}>{it.label}</div>
          <div className="desc">{it.desc}</div>
        </div>
        <StatusBadge status={it.ok === 'ok' ? 'success' : it.ok === 'warn' ? 'warn' : 'failed'}>
          {it.ok === 'ok' ? '通过' : it.ok === 'warn' ? '注意' : '失败'}
        </StatusBadge>
      </div>
    ))}
  </div>
);

// ---- SanitizerDiff ----
const SanitizerDiff = ({ before, after }) => (
  <div className="diff-pair">
    <div className="diff-block">
      <div className="ttl"><span>清洗前 · 入站</span><span className="text-err">+ cch</span></div>
      {before.map((l, i) => (
        <div key={i} className={`line ${l.type === 'del' ? 'del' : l.type === 'dim' ? 'dim' : ''}`}>{l.text || '\u00A0'}</div>
      ))}
    </div>
    <div className="diff-block">
      <div className="ttl"><span>清洗后 · 出站</span><span className="text-ok">cache-safe</span></div>
      {after.map((l, i) => (
        <div key={i} className={`line ${l.type === 'add' ? 'add' : l.type === 'dim' ? 'dim' : ''}`}>{l.text || '\u00A0'}</div>
      ))}
    </div>
  </div>
);

// ---- Switch ----
const Switch = ({ on, onChange }) => (
  <button className={`switch ${on ? 'on' : ''}`} onClick={(e) => { e.stopPropagation(); onChange(!on); }} />
);

// ---- Segmented ----
const Seg = ({ options, value, onChange }) => (
  <div className="seg">
    {options.map(o => (
      <button key={o.value} className={value === o.value ? 'active' : ''} onClick={() => onChange(o.value)}>{o.label}</button>
    ))}
  </div>
);

// ---- spin keyframe ----
const SpinStyle = () => (
  <style>{`@keyframes spin{to{transform:rotate(360deg)}} .spin{animation:spin 0.8s linear infinite;}`}</style>
);

Object.assign(window, {
  Icon, StatusBadge, MetricCard, Sparkline, AreaChart, CopyButton,
  EnvVarCopyBlock, SecretInput, ConnectionTestButton, PayloadViewer,
  TraceTimeline, CompatibilityChecklist, SanitizerDiff, Switch, Seg, SpinStyle,
});
