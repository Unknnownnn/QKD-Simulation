/*
  StatusBar.jsx — Bottom status bar showing connection, user, key pool, and smart routing status.
*/
import React from 'react';

export default function StatusBar({ user, connected, keyPool, topology, alerts }) {
  const smartRouting = topology?.smart_routing_enabled ?? false;
  const alertCount = (alerts || []).length;
  return (
    <div style={styles.bar}>
      {/* Connection */}
      <div style={styles.item}>
        <span style={{ ...styles.dot, background: connected ? '#00b894' : '#d63031' }} />
        <span>{connected ? 'Connected' : 'Disconnected'}</span>
      </div>

      {/* User */}
      <div style={styles.item}>
        <span style={{ fontSize: '11px', color: '#7986cb' }}>User:</span>
        <span style={{ fontWeight: 600, color: '#74b9ff' }}>{user?.display_name || user?.username || '—'}</span>
      </div>

      {/* Key pool */}
      <div style={styles.item}>
        <span style={{ fontSize: '11px', color: '#7986cb' }}>Keys:</span>
        <span style={{ fontWeight: 600, color: (keyPool?.active_keys ?? 0) > 0 ? '#00b894' : '#fdcb6e' }}>
          {keyPool?.active_keys ?? 0} active
        </span>
      </div>

      {/* Smart routing */}
      <div style={styles.item}>
        <span style={{ fontSize: '11px', color: '#7986cb' }}>Smart Routing:</span>
        <span style={{ fontWeight: 600, color: smartRouting ? '#00b894' : '#d63031' }}>
          {smartRouting ? 'ON' : 'OFF'}
        </span>
      </div>

      {/* Alerts */}
      {alertCount > 0 && (
        <div style={styles.item}>
          <span style={{ color: '#fdcb6e' }}>⚠ {alertCount} alert{alertCount !== 1 ? 's' : ''}</span>
        </div>
      )}

      <div style={{ marginLeft: 'auto', fontSize: '10px', color: '#5c6bc0' }}>
        SDN-QKD Secure Platform v1.0
      </div>
    </div>
  );
}

const styles = {
  bar: {
    display: 'flex', alignItems: 'center', gap: '16px',
    padding: '4px 16px', fontSize: '11px', color: '#e8eaf6',
    background: '#08081e', borderTop: '1px solid rgba(80,100,220,0.15)',
    minHeight: '28px', flexShrink: 0,
  },
  item: { display: 'flex', alignItems: 'center', gap: '5px' },
  dot: { width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0 },
};
