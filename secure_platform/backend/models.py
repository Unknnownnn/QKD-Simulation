"""
models.py — Pydantic schemas for request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────────────────── #

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    display_name: str = Field("", max_length=64)

class UserResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    online: bool = False
    created_at: str = ""

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Chat ─────────────────────────────────────────────────────────────── #

class MessageType(str, Enum):
    TEXT = "text"
    FILE = "file"
    SYSTEM = "system"
    KEY_EVENT = "key_event"

class ChatMessage(BaseModel):
    id: Optional[int] = None
    sender_id: int
    sender_name: str = ""
    recipient_id: Optional[int] = None      # None = group/broadcast
    channel: str = "general"
    message_type: MessageType = MessageType.TEXT
    plaintext: Optional[str] = None
    ciphertext: Optional[str] = None        # hex-encoded
    encryption_method: str = "none"
    key_id: Optional[str] = None
    timestamp: str = ""
    metadata: Dict[str, Any] = {}

class ChannelInfo(BaseModel):
    name: str
    members: List[str] = []
    is_direct: bool = False
    created_at: str = ""


# ── Key Management ───────────────────────────────────────────────────── #

class KeyStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    COMPROMISED = "compromised"

class KeyInfo(BaseModel):
    key_id: str
    user_pair: str                  # "alice:bob"
    key_bits: int
    key_bytes: int
    status: KeyStatus = KeyStatus.ACTIVE
    qber: float = 0.0
    created_at: str = ""
    used_at: Optional[str] = None
    encryption_method: str = "otp"  # "otp" | "aes"
    sha256: str = ""

class KeyPoolStatus(BaseModel):
    total_keys: int = 0
    active_keys: int = 0
    used_keys: int = 0
    compromised_keys: int = 0
    pool_capacity: int = 50
    auto_refresh: bool = True

class KeyRequest(BaseModel):
    user_pair: str
    encryption_method: str = "otp"
    key_length: int = 512

class KeyGenerationConfig(BaseModel):
    key_length: int = 512
    noise_depol: float = 0.02
    noise_loss: float = 0.05
    eve_active: bool = False
    eve_intercept_rate: float = 1.0
    attack_type: str = "intercept_resend"


# ── QKD Session ──────────────────────────────────────────────────────── #

class QKDSessionResult(BaseModel):
    session_id: str
    key_length_requested: int
    raw_count: int = 0
    lost_count: int = 0
    sifted_count: int = 0
    qber: float = 0.0
    eve_detected: bool = False
    final_key_bits: int = 0
    final_key_bytes: int = 0
    key_sha256: str = ""
    duration_ms: float = 0.0
    qber_history: List[float] = []
    noise_depol: float = 0.0
    noise_loss: float = 0.0
    eve_active: bool = False


# ── Network / SDN ────────────────────────────────────────────────────── #

class NetworkNode(BaseModel):
    id: str
    label: str
    role: str = "relay"
    x: float = 0.0
    y: float = 0.0
    active: bool = True
    compromised: bool = False

class NetworkLink(BaseModel):
    src: str
    dst: str
    qber: float = 0.0
    status: str = "safe"
    compromised: bool = False
    active: bool = True
    attack_type: str = "none"
    latency_ms: float = 5.0

class NetworkTopology(BaseModel):
    nodes: List[NetworkNode] = []
    links: List[NetworkLink] = []
    active_route: List[str] = []
    smart_routing_enabled: bool = True

class RouteAlertResponse(BaseModel):
    timestamp: float
    link_id: str
    qber: float
    previous_qber: float
    threshold: str
    action_taken: str = ""
    attack_type: str = "none"


# ── Attack / Eve ─────────────────────────────────────────────────────── #

class AttackType(str, Enum):
    INTERCEPT_RESEND = "intercept_resend"
    PNS = "pns"
    TROJAN_HORSE = "trojan_horse"
    NOISE_INJECTION = "noise_injection"

class EveConfig(BaseModel):
    active: bool = False
    attack_type: AttackType = AttackType.INTERCEPT_RESEND
    target_links: List[str] = ["A\u2192R1"]
    intercept_rate: float = 1.0

class AttackResult(BaseModel):
    attack_type: str
    target_link: str          # first link (kept for compat)
    target_links: List[str] = []
    qber_before: float
    qber_after: float
    key_impact: str = ""
    alert_raised: bool = False
    rerouted: bool = False
    new_route: List[str] = []

class SecurityAlert(BaseModel):
    id: int = 0
    timestamp: str
    severity: str      # "info" | "warning" | "critical"
    message: str
    link_id: Optional[str] = None
    qber: Optional[float] = None
    action: str = ""

class EveStatus(BaseModel):
    active: bool = False
    attack_type: str = "none"
    target_links: List[str] = []
    intercepted_count: int = 0
    qber_impact: float = 0.0


# ── Eve Intercept Data (Charlie's attacker view) ─────────────────────── #

class InterceptedQubit(BaseModel):
    qubit_id: int
    timestamp: float = 0.0
    alice_basis: str          # "+" (rectilinear) or "x" (diagonal)
    eve_basis: str            # Eve's random basis choice
    eve_measured: int         # Bit Eve measured (0 or 1)
    alice_bit: Optional[int] = None   # Actual bit — None if basis mismatch (unknown)
    basis_match: bool         # True if Eve guessed same basis as Alice
    disturbed: bool           # True if this qubit introduced an error downstream


class InterceptedMessage(BaseModel):
    msg_id: str
    timestamp: float = 0.0
    channel: str = "general"
    sender: str = "unknown"
    ciphertext_hex: str = ""
    key_id: Optional[str] = None
    plaintext: Optional[str] = None
    plaintext_len: int = 0
    decrypted: bool = False


class EveIntercepts(BaseModel):
    active: bool = False
    attack_type: str = "none"
    target_links: List[str] = []
    qubits_total: int = 0
    qubits_matched: int = 0
    key_bits_exposed: int = 0
    messages_captured: int = 0
    qubits: List[InterceptedQubit] = []
    messages: List[InterceptedMessage] = []
    stolen_key_ids: List[str] = []   # key IDs Eve has stolen via compromised generation


# ── Demo Mode ────────────────────────────────────────────────────────── #

class DemoStep(BaseModel):
    step: int
    title: str
    description: str
    action: str        # "normal_chat" | "activate_eve" | "observe_qber" | "smart_routing" | "regen_keys"
    status: str = "pending"   # "pending" | "running" | "completed"
    data: Dict[str, Any] = {}

class DemoState(BaseModel):
    running: bool = False
    current_step: int = 0
    total_steps: int = 6
    steps: List[DemoStep] = []
    auto_advance: bool = True


# ── WebSocket Messages ───────────────────────────────────────────────── #

class WSMessage(BaseModel):
    type: str
    data: Dict[str, Any] = {}
    timestamp: str = ""
