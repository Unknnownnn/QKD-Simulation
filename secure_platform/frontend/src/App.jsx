/*
  App.jsx — Main application component with routing and state management.
*/
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { login as apiLogin, getUsers, getMessages, getTopology, getKeyPool, getHealth } from './api';
import useWebSocket from './hooks/useWebSocket';

import LoginScreen from './components/LoginScreen';
import Header from './components/Header';
import TabNav from './components/TabNav';
import ChatPanel from './components/ChatPanel';
import KeyManagement from './components/KeyManagement';
import NetworkView from './components/NetworkView';
import EveDashboard from './components/EveDashboard';
import DemoMode from './components/DemoMode';
import StatusBar from './components/StatusBar';
import EveAttackerView from './components/EveAttackerView';

const TABS = [
  { id: 'chat', label: '💬 Secure Chat', icon: '💬' },
  { id: 'keys', label: '🔑 Key Management', icon: '🔑' },
  { id: 'network', label: '🌐 Network', icon: '🌐' },
  { id: 'eve', label: '🕵️ Eve Dashboard', icon: '🕵️' },
  { id: 'demo', label: '🎯 Demo Mode', icon: '🎯' },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [topology, setTopology] = useState(null);
  const [keyPool, setKeyPool] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const lastNotifId = useRef(0);

  // WebSocket handler
  const handleWsMessage = useCallback((event) => {
    const { type, data } = event;

    if (type === 'new_message') {
      setMessages(prev => [...prev, data]);
    } else if (type === 'messages_cleared') {
      setMessages([]);
    } else if (type === 'user_online' || type === 'user_offline') {
      setUsers(prev => prev.map(u =>
        u.user_id === data.user_id ? { ...u, online: type === 'user_online' } : u
      ));
    } else if (type === 'key_generated') {
      setKeyPool(data.session ? prev => ({ ...prev }) : prev => prev);
      refreshKeyPool();
    } else if (type === 'attack_detected') {
      if (data.topology) setTopology(data.topology);
      const notif = {
        id: ++lastNotifId.current,
        type: 'critical',
        message: `Attack detected on ${data.result?.target_link}! QBER: ${(data.result?.qber_after * 100)?.toFixed(1)}%`,
        ts: Date.now(),
      };
      setNotifications(prev => [notif, ...prev].slice(0, 20));
      setAlerts(prev => [notif, ...prev].slice(0, 50));
    } else if (type === 'attack_cleared') {
      if (data.topology) setTopology(data.topology);
    } else if (type === 'topology_update') {
      setTopology(data);
    } else if (type === 'demo_step' || type === 'demo_started' || type === 'demo_reset') {
      // handled by DemoMode component
    }
  }, []);

  const { connected, send } = useWebSocket(user?.user_id, handleWsMessage);

  // ── Auth ──
  const handleLogin = async (username) => {
    const result = await apiLogin(username, username.charAt(0).toUpperCase() + username.slice(1));
    localStorage.setItem('qkd_token', result.access_token);
    setUser(result.user);
  };

  const handleLogout = () => {
    localStorage.removeItem('qkd_token');
    setUser(null);
    setMessages([]);
    setUsers([]);
    setKeyPool(null);
    setTopology(null);
    setAlerts([]);
    setNotifications([]);
  };

  // ── Data loading ──
  const refreshUsers = async () => { try { setUsers(await getUsers()); } catch {} };
  const refreshMessages = async () => { try { setMessages(await getMessages()); } catch {} };
  const refreshTopology = async () => { try { setTopology(await getTopology()); } catch {} };
  const refreshKeyPool = async () => { try { setKeyPool(await getKeyPool()); } catch {} };

  useEffect(() => {
    if (!user) return;
    refreshUsers();
    refreshMessages();
    refreshTopology();
    refreshKeyPool();

    const interval = setInterval(() => {
      refreshTopology();
      refreshKeyPool();
    }, 5000);
    return () => clearInterval(interval);
  }, [user]);

  // ── Dismiss notifications ──
  const dismissNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  if (!user) return <LoginScreen onLogin={handleLogin} />;

  // ── Eve gets a completely different attacker's console ──
  const isEve = user.username === 'eve';
  if (isEve) {
    return (
      <div className="app-layout">
        <Header user={user} connected={connected} notifications={notifications}
                onDismissNotification={dismissNotification} onLogout={handleLogout} />
        {/* No TabNav — Eve sees only the intercept console */}
        <div className="app-content" style={{ background: '#050505' }}>
          <EveAttackerView />
        </div>
        <StatusBar connected={connected} user={user} keyPool={keyPool} topology={topology} />
      </div>
    );
  }

  return (
    <div className="app-layout">
      <Header user={user} connected={connected} notifications={notifications}
              onDismissNotification={dismissNotification} onLogout={handleLogout} />
      <TabNav tabs={TABS} active={activeTab} onChange={setActiveTab} />
      <div className="app-content">
        {activeTab === 'chat' && (
          <ChatPanel
            user={user} users={users} messages={messages}
            onSendMessage={(text, enc) => {
              send('chat_message', { plaintext: text, channel: 'general', encryption_method: enc });
            }}
            keyPool={keyPool}
            onRefreshMessages={refreshMessages}
          />
        )}
        {activeTab === 'keys' && (
          <KeyManagement
            keyPool={keyPool}
            onRefresh={refreshKeyPool}
          />
        )}
        {activeTab === 'network' && (
          <NetworkView
            topology={topology}
            onRefresh={refreshTopology}
          />
        )}
        {activeTab === 'eve' && (
          <EveDashboard
            topology={topology}
            onRefresh={() => { refreshTopology(); refreshKeyPool(); }}
            alerts={alerts}
          />
        )}
        {activeTab === 'demo' && (
          <DemoMode
            onRefreshAll={() => { refreshTopology(); refreshKeyPool(); refreshMessages(); }}
          />
        )}
      </div>
      <StatusBar connected={connected} user={user} keyPool={keyPool} topology={topology} />
    </div>
  );
}
