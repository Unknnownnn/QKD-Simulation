/*
  KeyManagement.jsx — QKD Key generation, pool management, and lifecycle.
*/
import React, { useState, useEffect } from 'react';
import { FiKey, FiRefreshCw, FiShield, FiAlertTriangle, FiTrash2, FiZap } from 'react-icons/fi';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { generateKey, listKeys, getKeyPool, listSessions, clearKeyPool } from '../api';

export default function KeyManagement({ keyPool: initialPool, onRefresh }) {
  const [keyPool, setKeyPool] = useState(initialPool);
  const [keys, setKeys] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSession, setLastSession] = useState(null);

  // Config
  const [keyLength, setKeyLength] = useState(512);
  const [noiseDepol, setNoiseDepol] = useState(0.02);
  const [noiseLoss, setNoiseLoss] = useState(0.05);
  const [eveActive, setEveActive] = useState(false);
  const [eveRate, setEveRate] = useState(1.0);

  const refresh = async () => {
    try {
      const [pool, keyList, sessList] = await Promise.all([
        getKeyPool(), listKeys(), listSessions()
      ]);
      setKeyPool(pool);
      setKeys(keyList);
      setSessions(sessList);
      onRefresh?.();
    } catch {}
  };

  useEffect(() => { refresh(); }, []);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const result = await generateKey({
        key_length: keyLength,
        noise_depol: noiseDepol,
        noise_loss: noiseLoss,
        eve_active: eveActive,
        eve_intercept_rate: eveRate,
      });
      setLastSession(result);
      await refresh();
    } catch (err) {
      console.error('Key gen error:', err);
    }
    setLoading(false);
  };

  const handleClearPool = async () => {
    await clearKeyPool();
    await refresh();
  };

  const qberData = lastSession?.qber_history?.map((q, i) => ({ index: i, qber: q * 100 })) || [];

  return (
    <div style={styles.container}>
      {/* Left: Settings */}
      <div style={styles.settingsPanel}>
        <h3 style={styles.panelTitle}><FiKey size={16} /> QKD Key Generation</h3>

        <div style={styles.formGroup}>
          <label style={styles.label}>Key Length (qubits)</label>
          <input type="number" value={keyLength} onChange={e => setKeyLength(+e.target.value)}
                 min={64} max={4096} step={64} style={styles.input} />
        </div>

        <div style={styles.formGroup}>
          <label style={styles.label}>Depolarization Noise</label>
          <input type="range" min={0} max={0.3} step={0.005} value={noiseDepol}
                 onChange={e => setNoiseDepol(+e.target.value)} style={styles.slider} />
          <span style={styles.sliderValue}>{(noiseDepol * 100).toFixed(1)}%</span>
        </div>

        <div style={styles.formGroup}>
          <label style={styles.label}>Photon Loss</label>
          <input type="range" min={0} max={0.5} step={0.01} value={noiseLoss}
                 onChange={e => setNoiseLoss(+e.target.value)} style={styles.slider} />
          <span style={styles.sliderValue}>{(noiseLoss * 100).toFixed(0)}%</span>
        </div>

        <div style={styles.checkboxGroup}>
          <label style={{ ...styles.label, color: '#ff7675', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input type="checkbox" checked={eveActive} onChange={e => setEveActive(e.target.checked)} />
            Enable Eve (Eavesdropper)
          </label>
        </div>

        {eveActive && (
          <div style={styles.formGroup}>
            <label style={styles.label}>Eve Intercept Rate</label>
            <input type="range" min={0} max={1} step={0.1} value={eveRate}
                   onChange={e => setEveRate(+e.target.value)} style={styles.slider} />
            <span style={styles.sliderValue}>{(eveRate * 100).toFixed(0)}%</span>
          </div>
        )}

        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}
                style={{ width: '100%', justifyContent: 'center', padding: '12px', marginTop: '12px' }}>
          <FiZap size={14} />
          {loading ? 'Generating...' : 'Generate QKD Key'}
        </button>

        <button className="btn btn-red btn-sm" onClick={handleClearPool}
                style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }}>
          <FiTrash2 size={12} /> Clear Pool
        </button>

        {/* Pool Status */}
        <div style={styles.poolStatus}>
          <h4 style={styles.subTitle}>Key Pool Status</h4>
          {keyPool && (
            <div style={styles.statsGrid}>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{keyPool.active_keys}</span>
                <span style={styles.statLabel}>Active</span>
              </div>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{keyPool.used_keys}</span>
                <span style={styles.statLabel}>Used</span>
              </div>
              <div style={styles.statItem}>
                <span style={{ ...styles.statValue, color: keyPool.compromised_keys > 0 ? '#d63031' : '#e8eaf6' }}>
                  {keyPool.compromised_keys}
                </span>
                <span style={styles.statLabel}>Compromised</span>
              </div>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{keyPool.total_keys}</span>
                <span style={styles.statLabel}>Total</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Results */}
      <div style={styles.resultsPanel}>
        {/* Last session result */}
        {lastSession && (
          <div className="card" style={{ marginBottom: '12px' }}>
            <div style={styles.panelHeader}>
              <h4 style={styles.subTitle}>
                <FiShield size={14} /> Last Session: {lastSession.session_id}
              </h4>
              <span className={`badge ${lastSession.eve_detected ? 'badge-critical' : 'badge-safe'}`}>
                {lastSession.eve_detected ? '⚠ Eve Detected' : '✓ Secure'}
              </span>
            </div>

            <div style={styles.statsGrid}>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{lastSession.raw_count}</span>
                <span style={styles.statLabel}>Raw Qubits</span>
              </div>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{lastSession.sifted_count}</span>
                <span style={styles.statLabel}>Sifted</span>
              </div>
              <div style={styles.statItem}>
                <span style={{ ...styles.statValue, color: lastSession.qber > 0.11 ? '#d63031' : '#00b894' }}>
                  {(lastSession.qber * 100).toFixed(2)}%
                </span>
                <span style={styles.statLabel}>QBER</span>
              </div>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{lastSession.final_key_bits}</span>
                <span style={styles.statLabel}>Key Bits</span>
              </div>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{lastSession.duration_ms?.toFixed(0)}ms</span>
                <span style={styles.statLabel}>Duration</span>
              </div>
              <div style={styles.statItem}>
                <span style={styles.statValue}>{lastSession.lost_count}</span>
                <span style={styles.statLabel}>Lost</span>
              </div>
            </div>

            {/* QBER Chart */}
            {qberData.length > 0 && (
              <div style={{ marginTop: '12px', height: '150px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={qberData}>
                    <defs>
                      <linearGradient id="qberGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#74b9ff" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#74b9ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(80,100,220,0.15)" />
                    <XAxis dataKey="index" tick={{ fontSize: 10, fill: '#7986cb' }} />
                    <YAxis tick={{ fontSize: 10, fill: '#7986cb' }} domain={[0, 'auto']} />
                    <Tooltip
                      contentStyle={{ background: '#111130', border: '1px solid rgba(80,100,220,0.3)', borderRadius: '6px', fontSize: '12px' }}
                      labelStyle={{ color: '#7986cb' }}
                    />
                    <Area type="monotone" dataKey="qber" stroke="#74b9ff" fill="url(#qberGrad)" strokeWidth={2} />
                    {/* Threshold line at 11% */}
                    <Line type="monotone" dataKey={() => 11} stroke="#d63031" strokeDasharray="5 5" strokeWidth={1} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {lastSession.key_sha256 && (
              <div style={{ marginTop: '8px', fontSize: '11px', color: '#a29bfe', fontFamily: 'var(--font-mono)' }}>
                SHA-256: {lastSession.key_sha256}
              </div>
            )}
          </div>
        )}

        {/* Keys list */}
        <div className="card">
          <div style={styles.panelHeader}>
            <h4 style={styles.subTitle}><FiKey size={14} /> Key Registry</h4>
            <button className="btn btn-sm" onClick={refresh}><FiRefreshCw size={12} /> Refresh</button>
          </div>
          <div style={styles.keyList}>
            {keys.length === 0 ? (
              <div style={styles.emptyState}>No keys generated yet</div>
            ) : (
              keys.map(k => (
                <div key={k.key_id} style={styles.keyItem}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FiKey size={12} color={
                      k.status === 'active' ? '#00b894' :
                      k.status === 'used' ? '#7986cb' :
                      k.status === 'compromised' ? '#d63031' : '#fdcb6e'
                    } />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                      {k.key_id}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '11px', color: '#7986cb' }}>
                      {k.key_bits} bits · QBER {(k.qber * 100).toFixed(1)}%
                    </span>
                    <span className={`badge ${
                      k.status === 'active' ? 'badge-safe' :
                      k.status === 'used' ? 'badge-info' :
                      'badge-critical'
                    }`}>{k.status}</span>
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

const styles = {
  container: { display: 'flex', flex: 1, overflow: 'hidden' },
  settingsPanel: {
    width: '300px', padding: '16px', overflow: 'auto',
    borderRight: '1px solid rgba(80,100,220,0.2)', background: 'rgba(14,14,42,0.3)',
  },
  resultsPanel: { flex: 1, padding: '16px', overflow: 'auto' },
  panelTitle: {
    fontSize: '15px', fontWeight: 600, color: '#e8eaf6',
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px',
  },
  subTitle: {
    fontSize: '13px', fontWeight: 600, color: '#e8eaf6',
    display: 'flex', alignItems: 'center', gap: '6px',
  },
  panelHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px',
  },
  formGroup: { marginBottom: '14px' },
  label: { display: 'block', fontSize: '12px', color: '#7986cb', marginBottom: '4px' },
  input: {
    width: '100%', padding: '8px', background: 'rgba(12,12,36,0.8)',
    border: '1px solid rgba(80,100,220,0.3)', borderRadius: '6px',
    color: '#e8eaf6', fontSize: '13px', boxSizing: 'border-box',
  },
  slider: { width: 'calc(100% - 50px)', verticalAlign: 'middle' },
  sliderValue: { fontSize: '12px', color: '#74b9ff', marginLeft: '8px' },
  checkboxGroup: { marginBottom: '14px' },
  poolStatus: {
    marginTop: '20px', padding: '12px',
    background: 'rgba(0,0,0,0.2)', borderRadius: '8px',
  },
  statsGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginTop: '8px',
  },
  statItem: {
    textAlign: 'center', padding: '8px',
    background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
  },
  statValue: { display: 'block', fontSize: '16px', fontWeight: 700, color: '#e8eaf6' },
  statLabel: { display: 'block', fontSize: '10px', color: '#7986cb', marginTop: '2px' },
  keyList: { maxHeight: '300px', overflow: 'auto' },
  keyItem: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '8px 10px', borderBottom: '1px solid rgba(80,100,220,0.1)',
  },
  emptyState: { textAlign: 'center', padding: '30px', color: '#7986cb', fontSize: '13px' },
};
