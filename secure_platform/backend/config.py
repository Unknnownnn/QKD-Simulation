"""
config.py — Application configuration.
"""
import os
import secrets

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "qkd_platform.db")

# Auth
SECRET_KEY = os.environ.get("QKD_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# QKD defaults
DEFAULT_KEY_LENGTH = 512
QBER_ABORT_THRESHOLD = 0.11
QBER_WARNING_THRESHOLD = 0.11
QBER_CRITICAL_THRESHOLD = 0.20
KEY_POOL_MAX_SIZE = 50
KEY_REFRESH_INTERVAL = 30  # seconds

# Network
DEFAULT_TOPOLOGY_NODES = [
    {"id": "A",  "label": "Alice",   "role": "alice", "x": 0.05, "y": 0.5},
    {"id": "R1", "label": "Relay-1", "role": "relay", "x": 0.30, "y": 0.2},
    {"id": "R2", "label": "Relay-2", "role": "relay", "x": 0.30, "y": 0.8},
    {"id": "R3", "label": "Relay-3", "role": "relay", "x": 0.60, "y": 0.2},
    {"id": "R4", "label": "Relay-4", "role": "relay", "x": 0.60, "y": 0.8},
    {"id": "B",  "label": "Bob",     "role": "bob",   "x": 0.95, "y": 0.5},
]

DEFAULT_TOPOLOGY_EDGES = [
    ("A", "R1"), ("A", "R2"),
    ("R1", "R3"), ("R1", "R4"),
    ("R2", "R3"), ("R2", "R4"),
    ("R3", "B"), ("R4", "B"),
]

# CORS
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
