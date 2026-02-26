/*
  LoginScreen.jsx — User login / registration screen.
*/
import React, { useState } from 'react';
import { FiShield, FiUser, FiArrowRight } from 'react-icons/fi';

export default function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const quickLogin = async (name) => {
    setLoading(true);
    setError('');
    try { await onLogin(name); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (username.trim()) quickLogin(username.trim().toLowerCase());
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <FiShield size={48} color="#74b9ff" />
        </div>
        <h1 style={styles.title}>QKD Secure Platform</h1>
        <p style={styles.subtitle}>
          Quantum Key Distribution · Secure Communication
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputGroup}>
            <FiUser style={styles.inputIcon} />
            <input
              style={styles.input}
              type="text"
              placeholder="Enter username..."
              value={username}
              onChange={e => setUsername(e.target.value)}
              disabled={loading}
              autoFocus
            />
          </div>
          <button style={styles.loginBtn} type="submit" disabled={loading || !username.trim()}>
            {loading ? 'Connecting...' : 'Login'} <FiArrowRight />
          </button>
        </form>

        {error && <p style={styles.error}>{error}</p>}

        <div style={styles.divider}>
          <span>Quick Login</span>
        </div>

        <div style={styles.quickBtns}>
          {[
            { name: 'alice', icon: '🧑', label: 'Alice' },
            { name: 'bob',   icon: '👤', label: 'Bob' },
            { name: 'eve', icon: '👁️', label: 'Eve', eve: true },
          ].map(({ name, icon, label, eve }) => (
            <button
              key={name}
              style={eve ? { ...styles.quickBtn, ...styles.eveBtn } : styles.quickBtn}
              onClick={() => quickLogin(name)}
              disabled={loading}
            >
              {icon} {label}
            </button>
          ))}
        </div>

        <p style={styles.footer}>
          Powered by BB84 Quantum Key Distribution Protocol
        </p>
      </div>
    </div>
  );
}

const styles = {
  container: {
    height: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'radial-gradient(ellipse at center, #0e0e2a 0%, #0a0a1a 70%)',
  },
  card: {
    background: 'rgba(17, 17, 48, 0.95)',
    border: '1px solid rgba(80, 100, 220, 0.2)',
    borderRadius: '16px',
    padding: '40px',
    width: '400px',
    textAlign: 'center',
    boxShadow: '0 8px 40px rgba(0, 0, 0, 0.5)',
  },
  logo: { marginBottom: '16px' },
  title: {
    fontSize: '22px',
    fontWeight: 700,
    background: 'linear-gradient(135deg, #74b9ff, #a29bfe)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    marginBottom: '8px',
  },
  subtitle: { fontSize: '12px', color: '#7986cb', marginBottom: '28px' },
  form: { marginBottom: '16px' },
  inputGroup: { position: 'relative', marginBottom: '12px' },
  inputIcon: {
    position: 'absolute', left: '12px', top: '50%',
    transform: 'translateY(-50%)', color: '#7986cb',
  },
  input: {
    width: '100%', padding: '12px 12px 12px 38px',
    background: 'rgba(12, 12, 36, 0.8)',
    border: '1px solid rgba(80, 100, 220, 0.3)',
    borderRadius: '8px', color: '#e8eaf6', fontSize: '14px',
    outline: 'none', boxSizing: 'border-box',
  },
  loginBtn: {
    width: '100%', padding: '12px',
    background: 'rgba(74, 114, 196, 0.3)',
    border: '1px solid rgba(74, 114, 196, 0.5)',
    borderRadius: '8px', color: '#74b9ff',
    fontSize: '14px', fontWeight: 600, cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
  },
  error: { color: '#d63031', fontSize: '12px', marginTop: '8px' },
  divider: {
    display: 'flex', alignItems: 'center', margin: '20px 0',
    color: '#5c6bc0', fontSize: '11px',
    gap: '12px',
  },
  quickBtns: { display: 'flex', gap: '8px', justifyContent: 'center', marginBottom: '20px' },
  quickBtn: {
    padding: '8px 16px',
    background: 'rgba(17, 17, 48, 0.8)',
    border: '1px solid rgba(80, 100, 220, 0.2)',
    borderRadius: '8px', color: '#e8eaf6',
    fontSize: '13px', cursor: 'pointer',
  },
  eveBtn: {
    background: 'rgba(40, 0, 0, 0.8)',
    border: '1px solid rgba(200, 0, 0, 0.4)',
    color: '#ff9090',
  },
  footer: { fontSize: '10px', color: '#5c6bc0', marginTop: '8px' },
};
