/*
  DemoMode.jsx — Guided 6-step demonstration of the QKD secure communication platform.
  Walks users through normal chat → Eve attack → QBER detection → smart routing → key regen.
*/
import React, { useState, useEffect } from 'react';
import { FiPlay, FiChevronRight, FiRotateCcw, FiCheckCircle } from 'react-icons/fi';
import { motion, AnimatePresence } from 'framer-motion';
import { getDemoState, startDemo, advanceDemo, resetDemo } from '../api';

const STEP_META = {
  normal_chat: {
    icon: '💬', title: 'Normal Secure Chat',
    detail: 'Establish a QKD session between Alice and Bob. Generate encryption keys via the BB84 protocol and exchange encrypted messages. Observe the low QBER indicating a clean quantum channel.',
    actions: ['Generate a QKD key pair', 'Send an encrypted message', 'Verify decryption succeeds'],
  },
  activate_eve: {
    icon: '🕵️', title: 'Activate Eavesdropper',
    detail: 'Deploy Eve on a quantum link using an intercept-resend attack. Eve will attempt to measure qubits in transit, which unavoidably disturbs the quantum states per the no-cloning theorem.',
    actions: ['Go to Eve Dashboard', 'Select intercept-resend attack', 'Activate Eve on alice→relay_1'],
  },
  observe_qber: {
    icon: '📊', title: 'Observe QBER Spike',
    detail: 'Generate new keys and watch the Quantum Bit Error Rate spike above the 11% warning threshold. This demonstrates how quantum mechanics makes eavesdropping fundamentally detectable.',
    actions: ['Generate a new QKD key', 'Check QBER in Key Management', 'Note the security alert'],
  },
  smart_routing: {
    icon: '🔀', title: 'Smart Routing Activates',
    detail: 'The SDN controller detects the compromised link and dynamically reroutes traffic through secure alternative paths using Dijkstra\'s algorithm with security-weighted edge costs.',
    actions: ['Open Network view', 'Observe route change around compromised link', 'Verify smart routing is enabled'],
  },
  maintain_comms: {
    icon: '🔒', title: 'Maintain Secure Comms',
    detail: 'Even with Eve on the network, the system maintains secure communications by routing around compromised links. Messages continue to be encrypted with fresh, uncompromised keys.',
    actions: ['Send another encrypted message', 'Verify it routes around Eve', 'Check message decrypts correctly'],
  },
  regen_keys: {
    icon: '🔑', title: 'Regenerate Keys',
    detail: 'Deactivate Eve and regenerate keys over the now-clean channel. Observe the QBER returning to normal levels, confirming the channel is no longer being eavesdropped.',
    actions: ['Deactivate Eve', 'Generate fresh QKD keys', 'Confirm QBER is back to normal'],
  },
};

const STEP_ORDER = ['normal_chat', 'activate_eve', 'observe_qber', 'smart_routing', 'maintain_comms', 'regen_keys'];

export default function DemoMode() {
  const [demo, setDemo] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchDemo = async () => {
    try {
      const d = await getDemoState();
      setDemo(d);
    } catch {}
  };

  useEffect(() => { fetchDemo(); }, []);

  const handleStart = async () => {
    setLoading(true);
    try { const d = await startDemo(); setDemo(d); } finally { setLoading(false); }
  };
  const handleAdvance = async () => {
    setLoading(true);
    try { const d = await advanceDemo(); setDemo(d); } finally { setLoading(false); }
  };
  const handleReset = async () => {
    setLoading(true);
    try { const d = await resetDemo(); setDemo(d); } finally { setLoading(false); }
  };

  const isActive = demo?.active ?? false;
  const currentStep = demo?.current_step ?? 0;

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>🎓 Guided Demo Mode</h2>
          <p style={{ fontSize: '12px', color: '#7986cb', margin: 0 }}>
            Walk through a complete QKD security scenario step-by-step
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {!isActive ? (
            <button className="btn btn-primary" onClick={handleStart} disabled={loading}>
              <FiPlay size={14} /> Start Demo
            </button>
          ) : (
            <>
              <button className="btn btn-primary" onClick={handleAdvance}
                disabled={loading || currentStep >= STEP_ORDER.length - 1}>
                <FiChevronRight size={14} /> Next Step
              </button>
              <button className="btn btn-sm" onClick={handleReset} disabled={loading}>
                <FiRotateCcw size={14} /> Reset
              </button>
            </>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div style={styles.progressRow}>
        {STEP_ORDER.map((key, i) => {
          const done = isActive && i < currentStep;
          const active = isActive && i === currentStep;
          return (
            <div key={key} style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
              <div style={{
                ...styles.dot,
                background: done ? '#00b894' : active ? '#74b9ff' : '#232350',
                boxShadow: active ? '0 0 10px #74b9ff88' : 'none',
              }}>
                {done ? <FiCheckCircle size={12} /> : i + 1}
              </div>
              {i < STEP_ORDER.length - 1 && (
                <div style={{
                  flex: 1, height: '2px', margin: '0 4px',
                  background: done ? '#00b894' : 'rgba(80,100,220,0.2)',
                }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step cards */}
      <div style={styles.stepsGrid}>
        <AnimatePresence>
          {STEP_ORDER.map((key, i) => {
            const meta = STEP_META[key];
            const done = isActive && i < currentStep;
            const active = isActive && i === currentStep;
            const locked = !isActive || i > currentStep;

            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                style={{
                  ...styles.stepCard,
                  borderColor: active ? '#74b9ff' : done ? '#00b894' : 'rgba(80,100,220,0.15)',
                  opacity: locked ? 0.45 : 1,
                  background: active ? 'rgba(116,185,255,0.06)' :
                              done ? 'rgba(0,184,148,0.04)' : 'rgba(17,17,48,0.6)',
                }}
              >
                {/* Step header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                  <span style={{ fontSize: '24px' }}>{meta.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', color: '#7986cb' }}>Step {i + 1}</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: active ? '#74b9ff' : '#e8eaf6' }}>
                      {meta.title}
                    </div>
                  </div>
                  {done && <span className="badge badge-success">✓ Done</span>}
                  {active && <span className="badge badge-info">▶ Current</span>}
                </div>

                {/* Description */}
                <p style={{ fontSize: '12px', color: '#b0b8d0', lineHeight: 1.6, margin: '0 0 12px' }}>
                  {meta.detail}
                </p>

                {/* Action checklist */}
                {(active || done) && (
                  <div style={styles.checklist}>
                    {meta.actions.map((action, ai) => (
                      <div key={ai} style={styles.checkItem}>
                        <span style={{ color: done ? '#00b894' : '#7986cb' }}>
                          {done ? '✓' : '○'}
                        </span>
                        <span style={{
                          fontSize: '11px',
                          color: done ? '#7986cb' : '#e8eaf6',
                          textDecoration: done ? 'line-through' : 'none',
                        }}>
                          {action}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Info footer */}
      <div style={styles.footer}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px' }}>ℹ️</span>
          <span style={{ fontSize: '11px', color: '#7986cb' }}>
            The demo mode does not modify any external state. All operations are performed within the simulation environment.
            Use the other tabs (Secure Chat, Key Management, Network, Eve Dashboard) to perform the actions described in each step.
          </span>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: { flex: 1, padding: '24px', overflow: 'auto' },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' },
  title: { fontSize: '18px', fontWeight: 700, color: '#e8eaf6', margin: 0 },
  progressRow: {
    display: 'flex', alignItems: 'center', marginBottom: '24px',
    padding: '16px', background: 'rgba(17,17,48,0.6)', borderRadius: '12px',
    border: '1px solid rgba(80,100,220,0.15)',
  },
  dot: {
    width: '26px', height: '26px', borderRadius: '50%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '11px', fontWeight: 700, color: '#e8eaf6', flexShrink: 0,
  },
  stepsGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '12px',
  },
  stepCard: {
    padding: '16px', borderRadius: '10px',
    border: '1px solid rgba(80,100,220,0.15)', transition: 'all 0.2s',
  },
  checklist: {
    padding: '8px 12px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px',
  },
  checkItem: {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0',
  },
  footer: {
    marginTop: '24px', padding: '12px 16px',
    background: 'rgba(17,17,48,0.4)', borderRadius: '8px',
    border: '1px solid rgba(80,100,220,0.1)',
  },
};
