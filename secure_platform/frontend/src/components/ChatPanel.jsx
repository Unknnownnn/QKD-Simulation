/*
  ChatPanel.jsx — Real-time secure chat with QKD encryption.
*/
import React, { useState, useRef, useEffect } from 'react';
import { FiSend, FiLock, FiUnlock, FiKey, FiShield, FiFile, FiTrash2 } from 'react-icons/fi';
import { sendMessage as apiSendMessage, decryptMessage, clearMessages as apiClearMessages } from '../api';

export default function ChatPanel({ user, users, messages, onSendMessage, keyPool, onRefreshMessages }) {
  const [input, setInput] = useState('');
  const [encMethod, setEncMethod] = useState('otp');
  const [decryptedMap, setDecryptedMap] = useState({});
  const [showEncDetails, setShowEncDetails] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    try {
      await apiSendMessage(input.trim(), 'general', encMethod);
      setInput('');
    } catch (err) {
      console.error('Send error:', err);
    }
  };

  const handleDecrypt = async (msg) => {
    if (!msg.ciphertext || !msg.key_id) return;
    try {
      const result = await decryptMessage(msg.ciphertext, msg.key_id, msg.encryption_method);
      if (result.success) {
        setDecryptedMap(prev => ({ ...prev, [msg.id]: result.plaintext }));
      }
    } catch {}
  };

  const handleClearChats = async () => {
    if (!window.confirm('Clear all messages? This cannot be undone.')) return;
    try {
      await apiClearMessages();
      // Server will broadcast messages_cleared via WebSocket to update state
    } catch (err) {
      console.error('Clear error:', err);
    }
  };

  const hasActiveKey = keyPool && keyPool.active_keys > 0;

  return (
    <div style={styles.container}>
      {/* Sidebar - Users */}
      <div style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <span style={{ fontWeight: 600, fontSize: '13px' }}>Users</span>
          <span className="badge badge-info">{users.length}</span>
        </div>
        {users.map(u => (
          <div key={u.user_id} style={styles.userItem}>
            <span className={`status-dot ${u.online ? 'online' : 'offline'}`}></span>
            <span style={{ fontSize: '13px' }}>{u.display_name || u.username}</span>
            {u.user_id === user?.user_id && (
              <span style={{ fontSize: '10px', color: '#7986cb', marginLeft: 'auto' }}>you</span>
            )}
          </div>
        ))}

        <div style={{ marginTop: 'auto', padding: '12px', borderTop: '1px solid rgba(80,100,220,0.2)' }}>
          <div style={{ fontSize: '11px', color: '#7986cb', marginBottom: '4px' }}>Key Pool</div>
          <div style={{ fontSize: '12px', color: hasActiveKey ? '#00b894' : '#d63031' }}>
            {hasActiveKey ? `🔑 ${keyPool.active_keys} active key(s)` : '⚠ No active keys'}
          </div>
          <div style={{ fontSize: '10px', color: '#5c6bc0', marginTop: '2px' }}>
            {keyPool ? `${keyPool.used_keys} used · ${keyPool.compromised_keys} compromised` : ''}
          </div>
        </div>
      </div>

      {/* Main chat area */}
      <div style={styles.chatMain}>
        {/* Channel header */}
        <div style={styles.channelHeader}>
          <div>
            <span style={{ fontWeight: 600, fontSize: '14px' }}># general</span>
            <span style={{ fontSize: '11px', color: '#7986cb', marginLeft: '8px' }}>
              Quantum-secured channel
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`badge ${hasActiveKey ? 'badge-safe' : 'badge-critical'}`}>
              <FiShield size={10} />
              {hasActiveKey ? 'Encrypted' : 'No Key'}
            </span>
            <button
              onClick={handleClearChats}
              title="Clear all messages"
              style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                background: 'none', border: '1px solid rgba(214,48,49,0.4)',
                borderRadius: '6px', padding: '4px 8px',
                color: '#d63031', fontSize: '11px', cursor: 'pointer',
              }}
            >
              <FiTrash2 size={11} /> Clear Chats
            </button>
          </div>
        </div>

        {/* Messages */}
        <div style={styles.messagesContainer}>
          {messages.length === 0 ? (
            <div style={styles.emptyState}>
              <FiShield size={40} color="#7986cb" />
              <p style={{ color: '#7986cb', fontSize: '14px', marginTop: '12px' }}>
                No messages yet. Generate a QKD key and start chatting securely!
              </p>
            </div>
          ) : (
            messages.map((msg, i) => {
              const isMine = msg.sender_id === user?.user_id;
              const isEncrypted = msg.encryption_method !== 'none' && msg.ciphertext;
              const isDecrypted = decryptedMap[msg.id];
              return (
                <div key={msg.id || i} className="animate-in" style={{
                  ...styles.message,
                  alignSelf: isMine ? 'flex-end' : 'flex-start',
                }}>
                  <div style={styles.msgHeader}>
                    <span style={{ fontWeight: 600, fontSize: '12px', color: isMine ? '#74b9ff' : '#00b894' }}>
                      {msg.sender_name || 'Unknown'}
                    </span>
                    <span style={{ fontSize: '10px', color: '#5c6bc0' }}>
                      {msg.timestamp?.split('T')[1]?.slice(0, 8) || msg.timestamp}
                    </span>
                  </div>
                  <div style={styles.msgBody}>
                    {msg.plaintext}
                  </div>
                  {isEncrypted && (
                    <div style={styles.encInfo}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <FiLock size={10} color="#a29bfe" />
                        <span style={{ fontSize: '10px', color: '#a29bfe' }}>
                          {msg.encryption_method.toUpperCase()} encrypted
                        </span>
                        <button
                          style={styles.detailBtn}
                          onClick={() => setShowEncDetails(showEncDetails === msg.id ? null : msg.id)}
                        >
                          {showEncDetails === msg.id ? 'Hide' : 'Details'}
                        </button>
                      </div>
                      {showEncDetails === msg.id && (
                        <div style={styles.encDetails}>
                          <div style={{ fontSize: '10px', color: '#7986cb' }}>
                            Key: {msg.key_id?.slice(0, 16)}...
                          </div>
                          <div style={{ fontSize: '10px', color: '#fdcb6e', wordBreak: 'break-all' }}>
                            Ciphertext: {msg.ciphertext?.slice(0, 64)}...
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} style={styles.inputArea}>
          <select
            value={encMethod}
            onChange={e => setEncMethod(e.target.value)}
            style={styles.encSelect}
          >
            <option value="otp">🔒 OTP</option>
            <option value="aes">🔐 AES-256</option>
            <option value="none">🔓 None</option>
          </select>
          <input
            type="text"
            placeholder={hasActiveKey ? "Type a secure message..." : "Generate a QKD key first (Key Management tab)"}
            value={input}
            onChange={e => setInput(e.target.value)}
            style={styles.msgInput}
            disabled={!hasActiveKey && encMethod !== 'none'}
          />
          <button type="submit" className="btn btn-primary" disabled={!input.trim()}>
            <FiSend size={14} /> Send
          </button>
        </form>
      </div>
    </div>
  );
}

const styles = {
  container: { display: 'flex', flex: 1, overflow: 'hidden' },
  sidebar: {
    width: '220px', borderRight: '1px solid rgba(80,100,220,0.2)',
    background: 'rgba(14,14,42,0.5)', display: 'flex', flexDirection: 'column',
    overflow: 'auto',
  },
  sidebarHeader: {
    padding: '12px 14px', borderBottom: '1px solid rgba(80,100,220,0.2)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  userItem: {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '8px 14px', fontSize: '13px', cursor: 'pointer',
    borderBottom: '1px solid rgba(80,100,220,0.05)',
  },
  chatMain: { flex: 1, display: 'flex', flexDirection: 'column' },
  channelHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 16px', borderBottom: '1px solid rgba(80,100,220,0.2)',
    background: 'rgba(14,14,42,0.3)',
  },
  messagesContainer: {
    flex: 1, overflow: 'auto', padding: '16px',
    display: 'flex', flexDirection: 'column', gap: '8px',
  },
  emptyState: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
  },
  message: {
    maxWidth: '70%', padding: '10px 14px',
    background: 'rgba(17,17,48,0.8)', border: '1px solid rgba(80,100,220,0.15)',
    borderRadius: '10px',
  },
  msgHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: '4px', gap: '12px',
  },
  msgBody: { fontSize: '13px', lineHeight: '1.5' },
  encInfo: {
    marginTop: '6px', paddingTop: '6px',
    borderTop: '1px solid rgba(80,100,220,0.1)',
  },
  detailBtn: {
    background: 'none', border: 'none', color: '#7986cb',
    fontSize: '10px', cursor: 'pointer', textDecoration: 'underline',
  },
  encDetails: {
    marginTop: '4px', padding: '6px',
    background: 'rgba(0,0,0,0.2)', borderRadius: '4px',
  },
  inputArea: {
    display: 'flex', gap: '8px', padding: '12px 16px',
    borderTop: '1px solid rgba(80,100,220,0.2)',
    background: 'rgba(14,14,42,0.3)',
  },
  encSelect: {
    width: '110px', padding: '8px',
    background: 'rgba(12,12,36,0.8)',
    border: '1px solid rgba(80,100,220,0.3)',
    borderRadius: '8px', color: '#e8eaf6', fontSize: '12px',
  },
  msgInput: {
    flex: 1, padding: '10px 14px',
    background: 'rgba(12,12,36,0.8)',
    border: '1px solid rgba(80,100,220,0.3)',
    borderRadius: '8px', color: '#e8eaf6', fontSize: '13px',
    outline: 'none',
  },
};
