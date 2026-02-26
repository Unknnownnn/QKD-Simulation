/*
  EveDashboard.jsx — Eve (eavesdropper) attack simulation panel.
  Configure attack parameters, activate/deactivate attacks, and monitor their effects.
*/
import React, { useState, useEffect } from 'react';
import { FiZap, FiShield, FiAlertTriangle, FiRadio, FiActivity } from 'react-icons/fi';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { getEveStatus, activateEve, deactivateEve, getNetworkAlerts } from '../api';

const ATTACK_TYPES = [
  { value: 'intercept_resend', label: 'Intercept-Resend', desc: 'Eve intercepts qubits, measures them, and resends — introduces detectable errors.', icon: '🎯' },
  { value: 'pns',              label: 'Photon Number Splitting', desc: 'Eve splits multi-photon pulses to extract key information silently.', icon: '🔬' },
  { value: 'trojan_horse',     label: 'Trojan Horse', desc: 'Eve injects bright pulses into Alice\'s equipment to learn bit values.', icon: '🐴' },
  { value: 'noise_injection',  label: 'Noise Injection', desc: 'Eve floods the quantum channel with noise to mask her eavesdropping.', icon: '📡' },
];

export default function EveDashboard({ topology, onRefresh }) {
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState({
    attack_type: 'intercept_resend',
    target_links: ['A→R1'],
    intercept_rate: 0.5,
  });
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);

  // Available link options from topology
  const links = (topology?.links || []).filter(l => l.src < l.dst);

  const fetchStatus = async () => {
    try {
      const s = await getEveStatus();
      setStatus(s);
    } catch {}
  };
  const fetchAlerts = async () => {
    try {
      const a = await getNetworkAlerts();
      setAlerts(a);
    } catch {}
  };

  useEffect(() => { fetchStatus(); fetchAlerts(); }, [topology]);

  const handleActivate = async () => {
    setLoading(true);
    try {
      await activateEve({
        attack_type: config.attack_type,
        target_links: config.target_links,
        intercept_rate: config.intercept_rate,
      });
      await fetchStatus();
      onRefresh?.();
    } finally { setLoading(false); }
  };

  const handleDeactivate = async () => {
    setLoading(true);
    try {
      await deactivateEve();
      await fetchStatus();
      onRefresh?.();
    } finally { setLoading(false); }
  };

  const active = status?.active ?? false;
  const qberHistory = (alerts || []).map((a, i) => ({
    idx: i, qber: (a.qber * 100).toFixed(1), threshold: a.threshold,
  }));

  return (
    <div style={styles.container}>
      {/* Left: Config panel */}
      <div style={styles.configPanel}>
        {/* Status card */}
        <div className="card" style={{
          marginBottom: '16px',
          borderColor: active ? 'rgba(214,48,49,0.5)' : 'rgba(0,184,148,0.3)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <FiZap size={16} color={active ? '#d63031' : '#00b894'} />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: active ? '#d63031' : '#00b894' }}>
              {active ? '⚡ Eve Active' : '🛡 Eve Inactive'}
            </h3>
          </div>
          {active && status && (
            <div style={{ fontSize: '12px', color: '#c4c4c4' }}>
              <div>Attack: <span style={{ color: '#ff7675' }}>{status.attack_type}</span></div>
              <div>Targets: <span style={{ color: '#fdcb6e' }}>{(status.target_links || []).join(', ')}</span></div>
              <div>Intensity: <span style={{ color: '#74b9ff' }}>{((status.intensity || 0) * 100).toFixed(0)}%</span></div>
            </div>
          )}
          <button
            className={`btn ${active ? 'btn-green' : 'btn-red'}`}
            style={{ width: '100%', marginTop: '12px' }}
            onClick={active ? handleDeactivate : handleActivate}
            disabled={loading}
          >
            {loading ? '...' : active ? '🛡 Deactivate Eve' : '⚡ Activate Eve'}
          </button>
        </div>

        {/* Attack type selection */}
        <div className="card" style={{ marginBottom: '16px' }}>
          <h4 style={styles.subTitle}>Attack Type</h4>
          {ATTACK_TYPES.map(at => (
            <label key={at.value} style={{
              ...styles.radioCard,
              borderColor: config.attack_type === at.value ? '#74b9ff' : 'rgba(80,100,220,0.15)',
              background: config.attack_type === at.value ? 'rgba(116,185,255,0.08)' : 'transparent',
            }}>
              <input
                type="radio" name="attack_type" value={at.value}
                checked={config.attack_type === at.value}
                onChange={() => setConfig(c => ({ ...c, attack_type: at.value }))}
                style={{ display: 'none' }}
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: '12px' }}>{at.icon} {at.label}</div>
                <div style={{ fontSize: '10px', color: '#7986cb', marginTop: '2px' }}>{at.desc}</div>
              </div>
            </label>
          ))}
        </div>

        {/* Target link & intensity */}
        <div className="card">
          <h4 style={styles.subTitle}>Parameters</h4>
          <div style={{ marginBottom: '12px' }}>
            <label style={styles.label}>Target Links</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
              {(links.length === 0
                ? [{ src: 'A', dst: 'R1' }, { src: 'A', dst: 'R2' }, { src: 'R1', dst: 'B' }]
                : links
              ).map(l => {
                const key = `${l.src}→${l.dst}`;
                const checked = config.target_links.includes(key);
                return (
                  <label key={key} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                    <input type="checkbox" checked={checked}
                      onChange={() => setConfig(c => ({
                        ...c,
                        target_links: checked
                          ? c.target_links.filter(x => x !== key)
                          : [...c.target_links, key],
                      }))}
                      style={{ accentColor: '#74b9ff' }}
                    />
                    {l.src} → {l.dst}
                  </label>
                );
              })}
            </div>
          </div>
          <div>
            <label style={styles.label}>Intercept Rate: {(config.intercept_rate * 100).toFixed(0)}%</label>
            <input type="range" min="0" max="1" step="0.05"
              value={config.intercept_rate}
              onChange={e => setConfig(c => ({ ...c, intercept_rate: parseFloat(e.target.value) }))}
              style={{ width: '100%' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#7986cb' }}>
              <span>Subtle</span><span>Aggressive</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Monitoring panel */}
      <div style={styles.monitorPanel}>
        {/* QBER impact chart */}
        <div className="card" style={{ marginBottom: '16px' }}>
          <h4 style={styles.subTitle}><FiActivity size={14} /> QBER Impact</h4>
          {qberHistory.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={qberHistory}>
                <defs>
                  <linearGradient id="qberGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#d63031" stopOpacity={0.4}/>
                    <stop offset="100%" stopColor="#d63031" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="idx" hide />
                <YAxis domain={[0, 50]} tickFormatter={v => `${v}%`} fontSize={10} stroke="#7986cb" />
                <Tooltip formatter={v => `${v}%`} contentStyle={{ background: '#0e0e2a', border: '1px solid #232350' }} />
                <ReferenceLine y={11} stroke="#fdcb6e" strokeDasharray="5 5" label={{ value: 'Warning 11%', fill: '#fdcb6e', fontSize: 10 }} />
                <ReferenceLine y={20} stroke="#d63031" strokeDasharray="5 5" label={{ value: 'Critical 20%', fill: '#d63031', fontSize: 10 }} />
                <Area type="monotone" dataKey="qber" stroke="#d63031" fill="url(#qberGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ textAlign: 'center', color: '#7986cb', fontSize: '12px', padding: '40px 0' }}>
              No QBER data yet. Activate Eve or generate keys to see impact.
            </div>
          )}
        </div>

        {/* Effect indicators */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px' }}>
          <StatCard label="Compromised Links" value={
            (topology?.links || []).filter(l => l.compromised).length
          } color="#d63031" icon="🔗" />
          <StatCard label="QBER Alerts" value={alerts.length} color="#fdcb6e" icon="⚠" />
          <StatCard label="Keys Invalidated" value={status?.keys_invalidated ?? 0} color="#e17055" icon="🔑" />
          <StatCard label="Route Changes" value={status?.route_changes ?? 0} color="#74b9ff" icon="🔄" />
        </div>

        {/* Alert feed */}
        <div className="card">
          <h4 style={styles.subTitle}><FiAlertTriangle size={14} /> Security Event Feed</h4>
          <div style={{ maxHeight: '260px', overflow: 'auto' }}>
            {alerts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: '#7986cb', fontSize: '12px' }}>
                No security events
              </div>
            ) : (
              alerts.map((a, i) => (
                <div key={i} style={styles.alertItem}>
                  <span style={{ fontSize: '14px' }}>
                    {a.threshold === 'critical' ? '🔴' : '🟡'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600 }}>
                      {a.link_id} — QBER {(a.qber * 100).toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '10px', color: '#7986cb' }}>
                      {a.action_taken}
                    </div>
                    <div style={{ fontSize: '9px', color: '#5c6bc0' }}>
                      {new Date(a.timestamp).toLocaleTimeString() || ''}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, icon }) {
  return (
    <div style={{
      padding: '12px', background: 'rgba(17,17,48,0.8)', borderRadius: '8px',
      border: `1px solid ${color}33`, textAlign: 'center',
    }}>
      <div style={{ fontSize: '18px' }}>{icon}</div>
      <div style={{ fontSize: '20px', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '10px', color: '#7986cb' }}>{label}</div>
    </div>
  );
}

const styles = {
  container: { display: 'flex', flex: 1, overflow: 'hidden' },
  configPanel: {
    width: '320px', padding: '16px', overflow: 'auto',
    borderRight: '1px solid rgba(80,100,220,0.2)', background: 'rgba(14,14,42,0.3)',
  },
  monitorPanel: { flex: 1, padding: '16px', overflow: 'auto' },
  subTitle: {
    fontSize: '13px', fontWeight: 600, color: '#e8eaf6',
    display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px',
  },
  label: { display: 'block', fontSize: '11px', color: '#7986cb', marginBottom: '4px' },
  select: {
    width: '100%', padding: '8px 10px', fontSize: '12px',
    background: '#0e0e2a', color: '#e8eaf6', border: '1px solid rgba(80,100,220,0.3)',
    borderRadius: '6px', outline: 'none',
  },
  radioCard: {
    display: 'block', padding: '10px 12px', marginBottom: '6px',
    border: '1px solid rgba(80,100,220,0.15)', borderRadius: '8px', cursor: 'pointer',
    transition: 'all 0.15s',
  },
  alertItem: {
    display: 'flex', alignItems: 'flex-start', gap: '8px',
    padding: '8px 0', borderBottom: '1px solid rgba(80,100,220,0.1)',
  },
};
