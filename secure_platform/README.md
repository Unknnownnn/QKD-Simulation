# SDN-QKD Secure Communication Platform

A full-stack, production-style secure communication platform integrating with a Software-Defined Networking Quantum Key Distribution (SDN-QKD) simulation system.

## Architecture

```
secure_platform/
├── backend/               FastAPI + Python
│   ├── main.py            Application entry point (all routes)
│   ├── config.py          Central configuration
│   ├── models.py          Pydantic v2 schemas
│   ├── database.py        SQLite via aiosqlite
│   ├── auth.py            JWT authentication
│   ├── network_manager.py SDN controller (non-Qt)
│   ├── websocket_manager.py  Real-time broadcast
│   ├── demo_manager.py    Guided demo controller
│   └── kms/
│       ├── key_pool.py    Thread-safe key pool
│       └── key_manager.py QKD key generation & encryption
│
└── frontend/              React 18 + Vite 5
    └── src/
        ├── App.jsx         Main app with routing & state
        ├── api.js          Complete API client
        ├── hooks/          useWebSocket hook
        ├── styles/         CSS variables, dark theme
        └── components/
            ├── LoginScreen.jsx     Auth UI
            ├── Header.jsx          Top bar + notifications
            ├── TabNav.jsx          Tab navigation
            ├── ChatPanel.jsx       Encrypted messaging
            ├── KeyManagement.jsx   QKD key generation & QBER charts
            ├── NetworkView.jsx     Canvas topology + smart routing
            ├── EveDashboard.jsx    Attack simulation dashboard
            ├── DemoMode.jsx        6-step guided demo
            └── StatusBar.jsx       System status bar
```

## Features

| Feature | Description |
|---------|-------------|
| **BB84 QKD Simulation** | Full BB84 protocol with configurable noise, key lengths, and Eve parameters |
| **Key Management Service** | Generate, store, consume keys; OTP (XOR) and AES-256-GCM encryption |
| **Encrypted Chat** | Real-time WebSocket messaging with quantum-generated encryption keys |
| **Eve Attack Simulation** | Intercept-resend, PNS, Trojan Horse, and noise injection attacks |
| **Smart Routing (SDN)** | Dijkstra-based adaptive routing that avoids compromised links |
| **QBER Monitoring** | Live Quantum Bit Error Rate visualization with warning/critical thresholds |
| **Network Topology** | Canvas-rendered 6-node mesh with real-time link health indicators |
| **Guided Demo Mode** | 6-step walkthrough: normal chat → Eve → QBER spike → routing → regen |

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- The parent project's `simulation/` package (BB84, attacks, quantum channel)

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
# Runs on http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173 (proxied to backend)
```

### Usage

1. Open `http://localhost:5173`
2. Quick-login as **alice**, **bob**, or **charlie**
3. Navigate tabs: Secure Chat → Key Management → Network → Eve Dashboard → Demo Mode

### Demo Walkthrough

1. **Normal Chat** — Generate a QKD key, send an encrypted message
2. **Activate Eve** — Deploy intercept-resend attack on a link
3. **Observe QBER** — Watch the error rate spike above 11%
4. **Smart Routing** — SDN controller reroutes around compromised links
5. **Maintain Comms** — Verify messages still decrypt correctly
6. **Regen Keys** — Deactivate Eve, generate fresh keys, confirm QBER drops

## API Endpoints

| Group | Endpoint | Method | Description |
|-------|----------|--------|-------------|
| Auth  | `/api/auth/login` | POST | Login (auto-creates user) |
| Chat  | `/api/messages/send` | POST | Send encrypted message |
| Keys  | `/api/keys/generate` | POST | Run BB84 & generate key |
| Keys  | `/api/keys/pool` | GET | Key pool status |
| Network | `/api/network/topology` | GET | Full topology with QBER |
| Network | `/api/network/smart-routing` | POST | Toggle smart routing |
| Eve   | `/api/eve/activate` | POST | Start eavesdropping |
| Eve   | `/api/eve/deactivate` | POST | Stop eavesdropping |
| Demo  | `/api/demo/start` | POST | Begin guided demo |
| WS    | `/ws/{user_id}` | WebSocket | Real-time events |

## Tech Stack

- **Backend:** FastAPI, aiosqlite, python-jose (JWT), cryptography (AES-GCM)
- **Frontend:** React 18, Vite 5, Recharts, Framer Motion, React Icons
- **Simulation:** BB84 protocol, NoiseModel, 4 attack types, 6-node mesh SDN
