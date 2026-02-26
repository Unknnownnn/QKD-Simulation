/*
  Header.jsx — App header with title, user info, and notifications.
*/
import React, { useState } from 'react';
import { FiShield, FiBell, FiUser, FiWifi, FiWifiOff, FiLogOut } from 'react-icons/fi';

export default function Header({ user, connected, notifications, onDismissNotification, onLogout }) {
  const [showNotifs, setShowNotifs] = useState(false);
  const isEve = user && user.username === 'eve';

  return (
    <div className="app-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {isEve
          ? <span style={{ fontSize: '18px' }}>⚡</span>
          : <FiShield size={20} color="#74b9ff" />}
        <h1>
          {isEve ? "Eve's Intercept Node" : 'QKD Secure Platform'}
        </h1>
        <span className="subtitle">
          {isEve ? 'Quantum Eavesdropper Console · Intercept Mode' : 'Quantum Key Distribution · SDN Security'}
        </span>
        {isEve && (
          <span style={{
            fontSize: '10px', padding: '2px 8px',
            background: 'rgba(74,114,196,0.2)', border: '1px solid #74b9ff',
            borderRadius: '3px', color: '#74b9ff', letterSpacing: '1px',
            fontFamily: 'monospace',
          }}>
            EVE MODE
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Connection status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}>
          {connected ? (
            <><FiWifi size={14} color="#00b894" /> <span style={{ color: '#00b894' }}>Connected</span></>
          ) : (
            <><FiWifiOff size={14} color="#d63031" /> <span style={{ color: '#d63031' }}>Disconnected</span></>
          )}
        </div>

        {/* Notifications */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowNotifs(!showNotifs)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative' }}
          >
            <FiBell size={18} color="#7986cb" />
            {notifications.length > 0 && (
              <span style={{
                position: 'absolute', top: '-4px', right: '-4px',
                background: '#d63031', color: '#fff', fontSize: '9px',
                width: '16px', height: '16px', borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700,
              }}>
                {notifications.length}
              </span>
            )}
          </button>

          {showNotifs && (
            <div style={styles.notifDropdown}>
              <div style={styles.notifHeader}>Notifications</div>
              {notifications.length === 0 ? (
                <div style={styles.notifEmpty}>No notifications</div>
              ) : (
                notifications.slice(0, 10).map(n => (
                  <div key={n.id} style={styles.notifItem} onClick={() => onDismissNotification(n.id)}>
                    <span style={{ color: n.type === 'critical' ? '#d63031' : '#fdcb6e' }}>⚠</span>
                    <span style={{ flex: 1, fontSize: '12px' }}>{n.message}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* User + Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#e8eaf6' }}>
          <FiUser size={14} />
          {user.display_name || user.username}
        </div>
        {onLogout && (
          <button
            onClick={onLogout}
            title="Switch user"
            style={{
              display: 'flex', alignItems: 'center', gap: '4px',
              background: 'none', border: '1px solid rgba(80,100,220,0.3)',
              borderRadius: '6px', padding: '4px 10px',
              color: '#7986cb', fontSize: '11px', cursor: 'pointer',
            }}
          >
            <FiLogOut size={12} /> Switch
          </button>
        )}
      </div>
    </div>
  );
}

const styles = {
  notifDropdown: {
    position: 'absolute', right: 0, top: '100%', marginTop: '8px',
    width: '320px', background: '#111130',
    border: '1px solid rgba(80,100,220,0.3)',
    borderRadius: '8px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
    zIndex: 999, overflow: 'hidden',
  },
  notifHeader: {
    padding: '10px 14px', borderBottom: '1px solid rgba(80,100,220,0.2)',
    fontSize: '13px', fontWeight: 600, color: '#e8eaf6',
  },
  notifEmpty: { padding: '20px', textAlign: 'center', color: '#7986cb', fontSize: '12px' },
  notifItem: {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '10px 14px', borderBottom: '1px solid rgba(80,100,220,0.1)',
    cursor: 'pointer', color: '#e8eaf6',
  },
};
