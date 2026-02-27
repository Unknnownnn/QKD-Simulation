/*
  EveAttackerView.jsx — Eve's interceptor console.
  Shows raw intercepted qubits and captured ciphertext for the attacker role.
  Completely separate from the normal user dashboard.
*/
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  getEveStatus, activateEve, deactivateEve, getEveIntercepts,
  getTopology, getLinks,
  eveStealKey, generateCompromisedKey, clearStolenKeys,
} from '../api';

const ATTACK_TYPES = [
  { value: 'intercept_resend', label: 'Intercept-Resend', icon: '🎯', shortDesc: '~25% QBER — causes detectable errors' },
  { value: 'pns',              label: 'PNS Attack',        icon: '🔬', shortDesc: '~3% QBER — very stealthy' },
  { value: 'trojan_horse',     label: 'Trojan Horse',      icon: '🐴', shortDesc: '~2% QBER — injects bright pulses' },
  { value: 'noise_injection',  label: 'Noise Injection',   icon: '📡', shortDesc: '~18% QBER — masks eavesdropping' },
];

// ── Helpers ────────────────────────────────────────────────────────── //

function hexChunks(hexStr, w = 32) {
  const chunks = [];
  for (let i = 0; i < hexStr.length; i += w) chunks.push(hexStr.slice(i, i + w));
  return chunks;
}

function fmtTime(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString('en-US', { hour12: false });
}

function basisSymbol(b) {
  return b === '+' ? '⊕' : b === 'x' ? '⊗' : b;
}

// ── Sub-components ─────────────────────────────────────────────────── //

function BlinkDot({ active }) {
  const [on, setOn] = useState(true);
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setOn(v => !v), 600);
    return () => clearInterval(t);
  }, [active]);
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: active ? (on ? '#a29bfe' : '#2a0a6e') : '#333',
      boxShadow: active && on ? '0 0 6px #a29bfe' : 'none',
      transition: 'background 0.2s',
    }} />
  );
}

function QubitRow({ q, idx }) {
  const match = q.basis_match;
  const disturbed = q.disturbed;
  return (
    <tr style={{
      background: idx % 2 === 0 ? 'rgba(80,100,220,0.04)' : 'transparent',
      borderBottom: '1px solid rgba(80,100,220,0.08)',
      fontFamily: 'monospace',
      fontSize: '11px',
    }}>
      <td style={td('#555')}>{String(q.qubit_id).padStart(4, '0')}</td>
      <td style={td('#aaa', 'center')}><span style={{ color: '#74b9ff' }}>{basisSymbol(q.alice_basis)}</span></td>
      <td style={td('#aaa', 'center')}><span style={{ color: '#a29bfe' }}>{basisSymbol(q.eve_basis)}</span></td>
      <td style={td('#eee', 'center')}>{q.eve_measured}</td>
      <td style={td(q.alice_bit !== null ? '#00e676' : '#555', 'center')}>
        {q.alice_bit !== null ? q.alice_bit : '?'}
      </td>
      <td style={{ ...td('', 'center') }}>
        {match
          ? <span style={{ color: '#00e676', fontSize: '13px' }}>✓</span>
          : <span style={{ color: '#ff4444', fontSize: '13px' }}>✗</span>}
      </td>
      <td style={{ ...td('', 'center') }}>
        {disturbed
          ? <span style={{ color: '#ff7675', fontSize: '10px' }}>ERR</span>
          : <span style={{ color: '#2d3436', fontSize: '10px' }}>—</span>}
      </td>
    </tr>
  );
}
function td(color = '#ccc', textAlign = 'left') {
  return { padding: '3px 8px', color, textAlign, verticalAlign: 'middle' };
}

function CapturedMessage({ m, idx }) {
  const [expanded, setExpanded] = useState(false);
  const chunks = hexChunks(m.ciphertext_hex || '', 48);
  return (
    <div style={{
      marginBottom: '8px',
      border: '1px solid rgba(80,100,220,0.25)',
      borderRadius: '6px',
      background: 'rgba(17,17,48,0.6)',
      overflow: 'hidden',
    }}>
      {/* Header row */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '6px 10px', cursor: 'pointer',
          background: 'rgba(74,114,196,0.1)',
          userSelect: 'none',
        }}
        onClick={() => setExpanded(v => !v)}
      >
        <span style={{ color: '#74b9ff', fontFamily: 'monospace', fontSize: '10px' }}>
          [{String(idx + 1).padStart(3, '0')}]
        </span>
        <span style={{ color: '#fdcb6e', fontFamily: 'monospace', fontSize: '11px', flex: 1 }}>
          {m.sender || 'unknown'} → {m.channel}
        </span>
        <span style={{ color: '#666', fontSize: '10px' }}>{fmtTime(m.timestamp)}</span>
        <span style={{ color: '#555', fontSize: '11px' }}>{expanded ? '▲' : '▼'}</span>
      </div>
      {/* Stats row */}
      <div style={{ display: 'flex', gap: '12px', padding: '4px 10px', borderBottom: '1px solid rgba(80,100,220,0.15)' }}>
        <span style={metaTag}>LEN: {m.plaintext_len}B</span>
        <span style={metaTag}>CIPHER: {(m.ciphertext_hex || '').length / 2}B</span>
        {m.key_id && <span style={metaTag}>KEY: {m.key_id.slice(0, 12)}…</span>}
        <span style={{ ...metaTag, color: m.decrypted ? '#00e676' : '#7986cb' }}>
          DECRYPT: {m.decrypted ? 'SUCCESS' : 'INTERCEPTED'}
        </span>
      </div>
      {/* Plaintext reveal (since Eve intercepted mid-wire in simulation) */}
      {m.plaintext && (
        <div style={{ padding: '6px 10px', background: 'rgba(0,230,118,0.06)', borderBottom: '1px solid rgba(0,230,118,0.12)', fontFamily: 'monospace', fontSize: '11px' }}>
          <span style={{ color: '#555', fontSize: '9px' }}>PLAINTEXT » </span>
          <span style={{ color: '#00e676' }}>{m.plaintext}</span>
        </div>
      )}
      {/* Hex dump */}
      {expanded && (
          <div style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: '10px', background: 'rgba(14,14,42,0.5)' }}>
          <div style={{ color: '#555', marginBottom: '4px' }}>── CIPHERTEXT HEX DUMP ──</div>
          {chunks.map((chunk, i) => (
            <div key={i} style={{ display: 'flex', gap: '12px', marginBottom: '1px' }}>
              <span style={{ color: '#333', minWidth: '32px' }}>
                {String(i * 24).padStart(4, '0').slice(-4)}
              </span>
              <span style={{ color: '#e17055', letterSpacing: '0.5px' }}>
                {chunk.match(/.{1,2}/g)?.join(' ') || chunk}
              </span>
              <span style={{ color: '#444' }}>
                {(chunk.match(/.{1,2}/g) || [])
                  .map(h => {
                    const c = parseInt(h, 16);
                    return c >= 32 && c < 127 ? String.fromCharCode(c) : '·';
                  }).join('')}
              </span>
            </div>
          ))}
          <div style={{ color: '#333', marginTop: '6px', fontSize: '9px' }}>
            ⚠ OTP/AES-GCM encrypted — without the QKD key, decryption is computationally infeasible.
          </div>
        </div>
      )}
    </div>
  );
}
const metaTag = { fontSize: '9px', color: '#888', fontFamily: 'monospace' };

// ── Main Component ───────────────────────────────────────────────────── //

export default function EveAttackerView({ onWsEvent }) {
  const [eveStatus, setEveStatus] = useState(null);
  const [intercepts, setIntercepts] = useState(null);
  const [topology, setTopology] = useState(null);
  const [config, setConfig] = useState({
    attack_type: 'intercept_resend',
    target_links: ['A→R1'],
    intercept_rate: 0.7,
  });
  const [loading, setLoading] = useState(false);
  const [compromiseLoading, setCompromiseLoading] = useState(false);
  const [scanLines, setScanLines] = useState(0);
  const qubitScrollRef = useRef(null);
  const autoScroll = useRef(true);

  // Scanline counter for terminal effect
  useEffect(() => {
    const t = setInterval(() => setScanLines(n => (n + 1) % 1000), 80);
    return () => clearInterval(t);
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [s, ic, topo] = await Promise.all([
        getEveStatus(), getEveIntercepts(128, 50), getTopology(),
      ]);
      setEveStatus(s);
      setIntercepts(ic);
      setTopology(topo);
    } catch {}
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Poll every 2 s
  useEffect(() => {
    const t = setInterval(fetchAll, 2000);
    return () => clearInterval(t);
  }, [fetchAll]);

  // Auto-scroll qubit table
  useEffect(() => {
    if (autoScroll.current && qubitScrollRef.current) {
      qubitScrollRef.current.scrollTop = qubitScrollRef.current.scrollHeight;
    }
  }, [intercepts?.qubits?.length]);

  const handleActivate = async () => {
    setLoading(true);
    try {
      await activateEve({
        attack_type: config.attack_type,
        target_links: config.target_links,
        intercept_rate: config.intercept_rate,
      });
      await fetchAll();
    } finally { setLoading(false); }
  };

  const handleDeactivate = async () => {
    setLoading(true);
    try {
      await deactivateEve();
      await fetchAll();
    } finally { setLoading(false); }
  };

  // Generate a fresh key AND silently give Eve a copy
  const handleCompromiseKey = async () => {
    setCompromiseLoading(true);
    try {
      await generateCompromisedKey({ key_length: 512 });
      await fetchAll();
    } catch (e) {
      console.error('Compromise key error:', e);
    } finally { setCompromiseLoading(false); }
  };

  // Steal the current active key Eve can see on the wire
  const handleStealKey = async () => {
    setCompromiseLoading(true);
    try {
      await eveStealKey();
      await fetchAll();
    } catch (e) {
      console.error('Steal key error:', e);
    } finally { setCompromiseLoading(false); }
  };

  const handleClearStolenKeys = async () => {
    await clearStolenKeys();
    await fetchAll();
  };

  const active = eveStatus?.active ?? false;
  const qubits = intercepts?.qubits ?? [];
  const msgs = intercepts?.messages ?? [];
  const stolenKeys = intercepts?.stolen_key_ids ?? [];
  const links = (topology?.links || []).filter(l => l.src < l.dst);
  const decryptedCount = msgs.filter(m => m.decrypted).length;

  const matchRate = intercepts && intercepts.qubits_total > 0
    ? ((intercepts.qubits_matched / intercepts.qubits_total) * 100).toFixed(1)
    : '0.0';
  const exposeRate = intercepts && intercepts.qubits_total > 0
    ? ((intercepts.key_bits_exposed / intercepts.qubits_total) * 100).toFixed(1)
    : '0.0';

  return (
    <div style={styles.root}>
      {/* ── Top Banner ── */}
      <div style={styles.banner}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BlinkDot active={active} />
          <span style={styles.bannerTitle}>EVE'S INTERCEPT CONSOLE</span>
            <span style={{ ...styles.bannerBadge, background: active ? 'rgba(74,114,196,0.2)' : 'transparent', borderColor: '#74b9ff', color: '#74b9ff' }}>
            {active ? '⚡ INTERCEPT ACTIVE' : '◼ STANDBY'}
          </span>
          {active && eveStatus && (
            <span style={{ ...styles.bannerBadge, color: '#fdcb6e', borderColor: '#fdcb6e44' }}>
              {eveStatus.attack_type?.toUpperCase().replace(/_/g, '-')} on {(eveStatus.target_links || []).join(', ')}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '20px', fontSize: '11px', fontFamily: 'monospace' }}>
          <span style={{ color: '#555' }}>USER: <span style={{ color: '#74b9ff' }}>eve@eve-node</span></span>
          <span style={{ color: '#555' }}>MODE: <span style={{ color: '#a29bfe' }}>QUANTUM INTERCEPT</span></span>
          <span style={{ color: '#555' }}>FRAME: <span style={{ color: '#444' }}>{String(scanLines).padStart(4, '0')}</span></span>
        </div>
      </div>

      {/* ── Stat strip ── */}
      <div style={styles.statStrip}>
        {[
          { label: 'QUBITS INTERCEPTED', value: intercepts?.qubits_total ?? 0, color: '#ff4444' },
          { label: 'BASIS MATCH RATE', value: `${matchRate}%`, color: '#fdcb6e' },
          { label: 'KEY BITS EXPOSED', value: intercepts?.key_bits_exposed ?? 0, color: '#00e676' },
          { label: 'KEY EXPOSURE RATE', value: `${exposeRate}%`, color: '#74b9ff' },
          { label: 'MSGS CAPTURED', value: intercepts?.messages_captured ?? 0, color: '#e17055' },
          { label: 'DECRYPTED', value: decryptedCount, color: decryptedCount > 0 ? '#00e676' : '#555' },
          { label: 'KEYS STOLEN', value: stolenKeys.length, color: stolenKeys.length > 0 ? '#a29bfe' : '#555' },
        ].map(s => (
          <div key={s.label} style={styles.statItem}>
            <div style={{ fontSize: '18px', fontWeight: 700, color: s.color, fontFamily: 'monospace' }}>{s.value}</div>
            <div style={{ fontSize: '9px', color: '#555', letterSpacing: '0.5px' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* ── Main 3-column Layout ── */}
      <div style={styles.body}>

        {/* ── LEFT: Attack Control ── */}
        <div style={styles.leftPanel}>
          <div style={styles.panelTitle}>⚙ ATTACK CONTROL</div>

          {/* Attack type */}
          <div style={styles.section}>
            <div style={styles.sectionLabel}>ATTACK VECTOR</div>
            {ATTACK_TYPES.map(at => (
              <label key={at.value} style={{
                ...styles.radioRow,
                borderColor: config.attack_type === at.value ? '#74b9ff' : 'rgba(80,100,220,0.15)',
                background: config.attack_type === at.value ? 'rgba(74,114,196,0.15)' : 'transparent',
              }}>
                <input
                  type="radio" name="attack_type" value={at.value}
                  checked={config.attack_type === at.value}
                  onChange={() => setConfig(c => ({ ...c, attack_type: at.value }))}
                  style={{ display: 'none' }}
                />
                <span>{at.icon}</span>
                <div>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#ddd' }}>{at.label}</div>
                  <div style={{ fontSize: '9px', color: '#666' }}>{at.shortDesc}</div>
                </div>
              </label>
            ))}
          </div>

          {/* Target links — checkboxes for multi-select */}
          <div style={styles.section}>
            <div style={styles.sectionLabel}>TARGET LINKS ({config.target_links.length} selected)</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {(links.length === 0
                ? [{ src: 'A', dst: 'R1', compromised: false }, { src: 'A', dst: 'R2', compromised: false }, { src: 'R1', dst: 'B', compromised: false }]
                : links
              ).map(l => {
                const key = `${l.src}→${l.dst}`;
                const checked = config.target_links.includes(key);
                return (
                  <label key={key} style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    padding: '5px 8px', borderRadius: '4px', cursor: 'pointer',
                    background: checked ? 'rgba(74,114,196,0.15)' : 'transparent',
                    border: `1px solid ${checked ? '#74b9ff' : 'rgba(80,100,220,0.15)'}`,
                    fontSize: '11px', fontFamily: 'monospace',
                  }}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setConfig(c => ({
                          ...c,
                          target_links: checked
                            ? c.target_links.filter(x => x !== key)
                            : [...c.target_links, key],
                        }));
                      }}
                      style={{ accentColor: '#74b9ff' }}
                    />
                    <span style={{ color: checked ? '#74b9ff' : '#888' }}>{l.src} → {l.dst}</span>
                    {l.compromised && <span style={{ fontSize: '9px', color: '#fdcb6e', marginLeft: 'auto' }}>⚠</span>}
                  </label>
                );
              })}
            </div>
          </div>

          {/* Intensity */}
          <div style={styles.section}>
            <div style={styles.sectionLabel}>INTERCEPT RATE: {(config.intercept_rate * 100).toFixed(0)}%</div>
            <input
              type="range" min="0" max="1" step="0.05"
              value={config.intercept_rate}
              onChange={e => setConfig(c => ({ ...c, intercept_rate: parseFloat(e.target.value) }))}  
              style={{ width: '100%', accentColor: '#74b9ff' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#555', marginTop: '2px' }}>
              <span>LOW NOISE</span><span>FULL TAP</span>
            </div>
          </div>

          {/* Action button */}
          <button
            onClick={active ? handleDeactivate : handleActivate}
            disabled={loading || (!active && config.target_links.length === 0)}
            style={{
              width: '100%', padding: '12px',
              background: active ? 'rgba(0,100,0,0.2)' : 'rgba(74,114,196,0.2)',
              border: `1px solid ${active ? '#00b894' : '#74b9ff'}`,
              borderRadius: '6px',
              color: active ? '#00e676' : '#74b9ff',
              fontFamily: 'monospace', fontSize: '13px',
              fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '1px', marginTop: '8px',
            }}
          >
            {loading ? '[ ... ]' : active ? '[ DEACTIVATE EVE ]' : '[ ACTIVATE EVE ]'}
          </button>

          {/* Active status */}
          {active && eveStatus && (
            <div style={{ marginTop: '10px', padding: '8px', background: 'rgba(74,114,196,0.08)', borderRadius: '4px', fontSize: '10px', fontFamily: 'monospace' }}>
              <div style={{ color: '#555', marginBottom: '4px' }}>── STATUS ──</div>
              <div><span style={{ color: '#555' }}>TYPE: </span><span style={{ color: '#74b9ff' }}>{eveStatus.attack_type}</span></div>
              <div><span style={{ color: '#555' }}>LINKS: </span><span style={{ color: '#fdcb6e' }}>{(eveStatus.target_links || []).join(', ')}</span></div>
              <div><span style={{ color: '#555' }}>QBER Δ: </span><span style={{ color: '#ff7675' }}>{(eveStatus.qber_impact * 100).toFixed(1)}%</span></div>
              <div><span style={{ color: '#555' }}>BATCHES: </span><span style={{ color: '#74b9ff' }}>{eveStatus.intercepted_count}</span></div>
            </div>
          )}

          {/* Disclaimer */}
          <div style={{ marginTop: 'auto', padding: '8px', fontSize: '9px', color: '#333', fontFamily: 'monospace', lineHeight: 1.4 }}>
            ⚠ Alice & Bob CANNOT see this console.<br />
            Their QKD system will detect anomalous QBER<br />
            and may reroute around compromised links.
          </div>

          {/* ── KEY COMPROMISE ── */}
          <div style={{ borderTop: '1px solid rgba(162,155,254,0.2)', paddingTop: '12px', marginTop: '8px' }}>
            <div style={{ ...styles.sectionLabel, color: '#a29bfe' }}>🔑 KEY COMPROMISE</div>
            <div style={{ fontSize: '9px', color: '#555', marginBottom: '8px', lineHeight: 1.5 }}>
              Silent steal: grab a copy of the key<br />
              without any QBER disturbance.<br />
              <span style={{ color: stolenKeys.length > 0 ? '#a29bfe' : '#444' }}>
                {stolenKeys.length > 0
                  ? `${stolenKeys.length} key(s) compromised — all traffic readable`
                  : 'Alice & Bob remain unaware.'}
              </span>
            </div>
            <button
              onClick={handleCompromiseKey}
              disabled={compromiseLoading}
              style={{
                width: '100%', padding: '8px', marginBottom: '6px',
                background: 'rgba(162,155,254,0.12)',
                border: '1px solid rgba(162,155,254,0.35)',
                borderRadius: '6px', color: '#a29bfe',
                fontFamily: 'monospace', fontSize: '10px',
                cursor: compromiseLoading ? 'not-allowed' : 'pointer',
              }}
            >
              {compromiseLoading ? '[ WORKING... ]' : '[ 🔑 GEN COMPROMISED KEY ]'}
            </button>
            <button
              onClick={handleStealKey}
              disabled={compromiseLoading}
              style={{
                width: '100%', padding: '8px',
                background: 'rgba(253,203,110,0.08)',
                border: '1px solid rgba(253,203,110,0.25)',
                borderRadius: '6px', color: '#fdcb6e',
                fontFamily: 'monospace', fontSize: '10px',
                cursor: compromiseLoading ? 'not-allowed' : 'pointer',
              }}
            >
              [ 🕵️ STEAL CURRENT KEY ]
            </button>

            {/* Stolen key list */}
            {stolenKeys.length > 0 && (
              <div style={{ marginTop: '8px', padding: '6px 8px', background: 'rgba(162,155,254,0.07)', borderRadius: '4px', fontSize: '9px', fontFamily: 'monospace' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ color: '#a29bfe' }}>COMPROMISED KEYS</span>
                  <span
                    onClick={handleClearStolenKeys}
                    style={{ color: '#e17055', cursor: 'pointer', fontSize: '9px' }}
                    title="Clear stolen keys"
                  >✕ clear</span>
                </div>
                {stolenKeys.slice(-5).map(kid => (
                  <div key={kid} style={{ color: '#fdcb6e', marginBottom: '2px' }}>
                    ✓ {kid.slice(0, 18)}…
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── CENTER: Qubit Intercept Stream ── */}
        <div style={styles.centerPanel}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={styles.panelTitle}>
              📡 RAW QUBIT INTERCEPT STREAM
              {active && <span style={{ marginLeft: '8px', fontSize: '9px', color: '#a29bfe', animation: 'none' }}> ● LIVE</span>}
            </div>
            <div style={{ fontSize: '9px', color: '#555', fontFamily: 'monospace' }}>
              <label style={{ cursor: 'pointer', userSelect: 'none' }}>
                <input type="checkbox" checked={autoScroll.current}
                  onChange={e => { autoScroll.current = e.target.checked; }}
                  style={{ marginRight: '4px' }}
                />
                AUTO-SCROLL
              </label>
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', gap: '16px', marginBottom: '6px', fontSize: '9px', fontFamily: 'monospace' }}>
            <span style={{ color: '#74b9ff' }}>⊕ rectilinear (+)</span>
            <span style={{ color: '#a29bfe' }}>⊗ diagonal (×)</span>
            <span style={{ color: '#00e676' }}>✓ basis match</span>
            <span style={{ color: '#ff4444' }}>✗ basis mismatch</span>
            <span style={{ color: '#ff7675' }}>ERR disturbed</span>
          </div>

          {/* Table */}
          <div
            ref={qubitScrollRef}
            style={{ flex: 1, overflow: 'auto', borderRadius: '4px', border: '1px solid rgba(80,100,220,0.15)' }}
          >
            {qubits.length === 0 ? (
              <div style={styles.emptyState}>
                <div style={{ fontSize: '32px', marginBottom: '8px' }}>📡</div>
                <div style={{ color: '#555', fontFamily: 'monospace', fontSize: '12px' }}>
                  NO INTERCEPT DATA<br />
                  <span style={{ fontSize: '10px', color: '#333' }}>Activate Eve to begin capturing qubits</span>
                </div>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'rgba(74,114,196,0.2)', position: 'sticky', top: 0, zIndex: 1 }}>
                    {['#', 'Alice Basis', 'Eve Basis', 'Measured', 'Actual', 'Match', 'Disturbed'].map(h => (
                      <th key={h} style={{
                        padding: '5px 8px', fontSize: '9px', fontWeight: 700,
                        color: '#888', textAlign: 'center',
                        fontFamily: 'monospace', letterSpacing: '0.5px',
                        borderBottom: '1px solid rgba(80,100,220,0.3)',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {qubits.map((q, i) => <QubitRow key={q.qubit_id} q={q} idx={i} />)}
                </tbody>
              </table>
            )}
          </div>

          {/* Bottom info */}
          {qubits.length > 0 && (
            <div style={{ marginTop: '6px', fontSize: '9px', color: '#444', fontFamily: 'monospace', display: 'flex', gap: '16px' }}>
              <span>Showing last {qubits.length} qubits</span>
              <span style={{ color: '#555' }}>
                KEY RECONSTRUCTION: Eve knows ~{matchRate}% of sifted key bits
                — <span style={{ color: stolenKeys.length > 0 ? '#00e676' : '#74b9ff' }}>
                  {stolenKeys.length > 0
                    ? `🔑 FULL KEY STOLEN — decrypting all traffic`
                    : 'insufficient to decrypt messages'}
                </span>
              </span>
            </div>
          )}
        </div>

        {/* ── RIGHT: Captured Messages ── */}
        <div style={styles.rightPanel}>
          <div style={styles.panelTitle}>
            📥 CAPTURED CIPHERTEXT
            {msgs.length > 0 && (
              <span style={{ marginLeft: '6px', background: 'rgba(74,114,196,0.25)', color: '#74b9ff', fontSize: '10px', padding: '1px 6px', borderRadius: '10px' }}>
                {msgs.length}
              </span>
            )}
          </div>

          {msgs.length === 0 ? (
            <div style={styles.emptyState}>
              <div style={{ fontSize: '28px', marginBottom: '8px' }}>📭</div>
              <div style={{ color: '#555', fontFamily: 'monospace', fontSize: '11px', textAlign: 'center' }}>
                NO MESSAGES CAPTURED<br />
                <span style={{ fontSize: '9px', color: '#333' }}>
                  Messages from Alice/Bob captured<br />when Eve is active
                </span>
              </div>
            </div>
          ) : (
            <div style={{ overflow: 'auto', flex: 1 }}>
              {msgs.map((m, i) => <CapturedMessage key={m.msg_id} m={m} idx={i} />)}
            </div>
          )}

          {/* Analysis note */}
          {msgs.length > 0 && (
            <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(14,14,42,0.6)', borderRadius: '4px', fontSize: '9px', fontFamily: 'monospace', color: '#7986cb', lineHeight: 1.5 }}>
              <span style={{ color: '#74b9ff' }}>ANALYSIS: </span>
              {stolenKeys.length > 0 ? (
                <>
                  Messages encrypted with <span style={{ color: '#a29bfe' }}>compromised keys</span> are
                  being <span style={{ color: '#00e676' }}>decrypted in real time</span>.<br />
                  <span style={{ color: '#fdcb6e' }}>Alice &amp; Bob are unaware their key was stolen.</span>
                </>
              ) : (
                <>
                  Messages are encrypted with QKD-derived OTP/AES keys.<br />
                  Eve captured the ciphertext but lacks the quantum key.<br />
                  <span style={{ color: '#555' }}>Information-theoretic security — brute force: infeasible.</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────── //

const styles = {
  root: {
    display: 'flex', flexDirection: 'column',
    height: '100%', overflow: 'hidden',
    background: '#0a0a1e',
    color: '#ccc',
    fontFamily: 'monospace',
  },
  banner: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '8px 16px',
    background: 'rgba(74,114,196,0.1)',
    borderBottom: '1px solid rgba(80,100,220,0.25)',
  },
  bannerTitle: {
    fontSize: '13px', fontWeight: 700,
    color: '#74b9ff', letterSpacing: '2px',
  },
  bannerBadge: {
    fontSize: '10px', padding: '2px 8px',
    border: '1px solid rgba(80,100,220,0.3)',
    borderRadius: '3px', letterSpacing: '0.5px',
  },
  statStrip: {
    display: 'flex', gap: 0,
    borderBottom: '1px solid rgba(80,100,220,0.2)',
    background: 'rgba(14,14,42,0.5)',
  },
  statItem: {
    flex: 1, padding: '8px 12px', textAlign: 'center',
    borderRight: '1px solid rgba(80,100,220,0.1)',
  },
  body: {
    display: 'flex', flex: 1, overflow: 'hidden',
  },
  leftPanel: {
    width: '240px', minWidth: '220px',
    display: 'flex', flexDirection: 'column',
    padding: '12px',
    borderRight: '1px solid rgba(80,100,220,0.2)',
    background: 'rgba(10,10,30,0.4)',
    overflow: 'auto',
  },
  centerPanel: {
    flex: 1, display: 'flex', flexDirection: 'column',
    padding: '12px',
    overflow: 'hidden',
    borderRight: '1px solid rgba(80,100,220,0.2)',
  },
  rightPanel: {
    width: '300px', minWidth: '260px',
    display: 'flex', flexDirection: 'column',
    padding: '12px',
    overflow: 'hidden',
    background: 'rgba(10,10,30,0.3)',
  },
  panelTitle: {
    fontSize: '11px', fontWeight: 700, color: '#74b9ff',
    letterSpacing: '1px', marginBottom: '10px',
    display: 'flex', alignItems: 'center',
  },
  section: { marginBottom: '14px' },
  sectionLabel: {
    fontSize: '9px', color: '#7986cb', letterSpacing: '1px',
    marginBottom: '6px',
  },
  radioRow: {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '7px 10px', marginBottom: '4px',
    border: '1px solid rgba(80,100,220,0.15)', borderRadius: '5px',
    cursor: 'pointer',
  },
  select: {
    width: '100%', padding: '7px 8px', fontSize: '11px',
    background: '#0a0a1e', color: '#a0b0e0',
    border: '1px solid rgba(80,100,220,0.3)', borderRadius: '4px',
    outline: 'none',
  },
  emptyState: {
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    flex: 1, height: '200px',
    color: '#7986cb',
  },
};
