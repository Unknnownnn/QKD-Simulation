"""
key_manager.py — High-level Key Management Service.
Orchestrates QKD key generation, distribution, and lifecycle management.
Integrates QBER alerts and attack awareness.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# Add project root so we can import existing simulation
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation.bb84 import BB84Protocol
from simulation.quantum_channel import NoiseModel
from simulation.session_result import SessionResult

from models import (
    KeyInfo, KeyStatus, KeyPoolStatus, QKDSessionResult,
    KeyGenerationConfig, SecurityAlert,
)
from kms.key_pool import KeyPool, KeyEntry


def _bits_to_bytes(bits: List[int]) -> bytes:
    padded = bits + [0] * ((-len(bits)) % 8)
    ba = bytearray()
    for i in range(0, len(padded), 8):
        byte = 0
        for b in padded[i:i + 8]:
            byte = (byte << 1) | b
        ba.append(byte)
    return bytes(ba)


def _xor_encrypt(message: bytes, key_hex: str) -> bytes:
    key_bytes = bytes.fromhex(key_hex)
    extended = (key_bytes * ((len(message) // len(key_bytes)) + 1))[:len(message)]
    return bytes(a ^ b for a, b in zip(message, extended))


def _aes_encrypt(message: bytes, key_hex: str) -> Tuple[bytes, bytes]:
    """AES-256-GCM encryption. Returns (nonce, ciphertext+tag)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    # Derive 32 bytes for AES-256
    key_bytes = bytes.fromhex(key_hex)
    derived = hashlib.sha256(key_bytes).digest()
    aesgcm = AESGCM(derived)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, message, None)
    return nonce, ct


def _aes_decrypt(nonce: bytes, ciphertext: bytes, key_hex: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key_bytes = bytes.fromhex(key_hex)
    derived = hashlib.sha256(key_bytes).digest()
    aesgcm = AESGCM(derived)
    return aesgcm.decrypt(nonce, ciphertext, None)


class KeyManager:
    """
    Central Key Management Service.

    Responsibilities:
    - Generate QKD keys via BB84 protocol
    - Manage key pools for user pairs
    - Distribute session keys securely
    - Encrypt/decrypt messages
    - Monitor QBER and invalidate compromised keys
    - Auto-refresh keys when pool runs low
    """

    def __init__(self, pool_size: int = 50):
        self._pool = KeyPool(max_pool_size=pool_size)
        self._sessions: Dict[str, QKDSessionResult] = {}
        self._alerts: List[SecurityAlert] = []
        self._alert_id = 0
        self._qber_threshold = 0.11
        # Eve's covertly-stolen key material: key_id → key_hex
        # Populated when a compromised key-generation is performed or Eve
        # explicitly steals the current key.  Alice & Bob remain unaware.
        self._eve_stolen_keys: Dict[str, str] = {}

    # ── QKD Key Generation ───────────────────────────────────────────── #

    def generate_key(
        self,
        user_pair: str = "alice:bob",
        config: Optional[KeyGenerationConfig] = None,
    ) -> Tuple[QKDSessionResult, Optional[KeyInfo]]:
        """
        Run a BB84 QKD session and store the resulting key in the pool.
        Returns (session_result, key_info_or_None).
        """
        cfg = config or KeyGenerationConfig()

        noise = NoiseModel(
            depolarization=cfg.noise_depol,
            photon_loss=cfg.noise_loss,
        )

        protocol = BB84Protocol(
            key_length=cfg.key_length,
            noise_model=noise,
            eve_active=cfg.eve_active,
            eve_intercept_rate=cfg.eve_intercept_rate,
        )

        start = time.time()
        result: SessionResult = protocol.full_run()
        duration_ms = (time.time() - start) * 1000

        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        n_sifted = len(result.sifted_key_alice)
        n_final = len(result.final_key)

        session_result = QKDSessionResult(
            session_id=session_id,
            key_length_requested=cfg.key_length,
            raw_count=result.raw_count,
            lost_count=result.lost_count,
            sifted_count=n_sifted,
            qber=result.qber,
            eve_detected=result.eve_detected,
            final_key_bits=n_final,
            final_key_bytes=n_final // 8,
            key_sha256=hashlib.sha256(_bits_to_bytes(result.final_key)).hexdigest()[:20] + "..." if result.final_key else "",
            duration_ms=duration_ms,
            qber_history=list(result.qber_history),
            noise_depol=cfg.noise_depol,
            noise_loss=cfg.noise_loss,
            eve_active=cfg.eve_active,
        )
        self._sessions[session_id] = session_result

        # Store key in pool if session successful
        key_info = None
        if result.final_key and not result.eve_detected:
            entry = self._pool.add_key(
                user_pair=user_pair,
                key_bits=result.final_key,
                qber=result.qber,
                encryption_method=cfg.encryption_method if hasattr(cfg, 'encryption_method') else "otp",
                session_id=session_id,
            )
            key_info = entry.to_info()
        elif result.eve_detected:
            self._raise_alert(
                "critical",
                f"Eve detected during key generation! QBER={result.qber*100:.1f}%. Session {session_id} aborted.",
                qber=result.qber,
            )

        return session_result, key_info

    # ── Key Distribution ─────────────────────────────────────────────── #

    def get_session_key(self, user_pair: str = "alice:bob") -> Optional[KeyInfo]:
        """Get an active session key for a user pair."""
        entry = self._pool.get_active_key(user_pair)
        if entry:
            return entry.to_info()
        return None

    def consume_session_key(self, key_id: str) -> Optional[str]:
        """Consume a key and return the hex material."""
        entry = self._pool.consume_key(key_id)
        if entry:
            return entry.key_hex
        return None

    def get_key_material(self, key_id: str) -> Optional[str]:
        """Get key hex without consuming it."""
        return self._pool.get_key_hex(key_id)

    # ── Encryption / Decryption ──────────────────────────────────────── #

    def encrypt_message(
        self,
        plaintext: str,
        key_id: str,
        method: str = "otp",
    ) -> Dict[str, Any]:
        """
        Encrypt a message using a QKD key.
        Returns dict with ciphertext, method, key_id, etc.
        """
        key_hex = self._pool.get_key_hex(key_id)
        if not key_hex:
            raise ValueError(f"Key {key_id} not found")

        plain_bytes = plaintext.encode("utf-8")

        if method == "aes":
            nonce, ct = _aes_encrypt(plain_bytes, key_hex)
            return {
                "ciphertext": ct.hex(),
                "nonce": nonce.hex(),
                "method": "aes",
                "key_id": key_id,
                "plaintext_len": len(plaintext),
            }
        else:
            ct = _xor_encrypt(plain_bytes, key_hex)
            return {
                "ciphertext": ct.hex(),
                "method": "otp",
                "key_id": key_id,
                "plaintext_len": len(plaintext),
            }

    def decrypt_message(
        self,
        ciphertext_hex: str,
        key_id: str,
        method: str = "otp",
        nonce_hex: Optional[str] = None,
    ) -> str:
        """Decrypt a message using a QKD key."""
        key_hex = self._pool.get_key_hex(key_id)
        if not key_hex:
            raise ValueError(f"Key {key_id} not found")

        ct = bytes.fromhex(ciphertext_hex)

        if method == "aes":
            if not nonce_hex:
                raise ValueError("AES decryption requires nonce")
            nonce = bytes.fromhex(nonce_hex)
            plain_bytes = _aes_decrypt(nonce, ct, key_hex)
        else:
            plain_bytes = _xor_encrypt(ct, key_hex)  # XOR is self-inverse

        return plain_bytes.decode("utf-8")

    # ── QBER & Security Awareness ────────────────────────────────────── #

    def handle_qber_alert(self, qber: float, link_id: str = "") -> List[str]:
        """Check QBER and invalidate compromised keys if necessary."""
        if qber > self._qber_threshold:
            invalidated = self._pool.invalidate_compromised(self._qber_threshold)
            if invalidated:
                self._raise_alert(
                    "critical",
                    f"QBER spike ({qber*100:.1f}%) detected on {link_id}. "
                    f"Invalidated {len(invalidated)} compromised key(s).",
                    link_id=link_id,
                    qber=qber,
                )
            return invalidated
        return []

    def needs_key_refresh(self, user_pair: str = "alice:bob") -> bool:
        """Check if the key pool needs refreshing."""
        status = self._pool.get_pool_status(user_pair)
        return status.active_keys == 0

    # ── Pool Status ──────────────────────────────────────────────────── #

    def get_pool_status(self, user_pair: Optional[str] = None) -> KeyPoolStatus:
        return self._pool.get_pool_status(user_pair)

    def get_all_keys(self, user_pair: Optional[str] = None) -> List[KeyInfo]:
        return self._pool.get_all_keys_info(user_pair)

    def get_key_info(self, key_id: str) -> Optional[KeyInfo]:
        return self._pool.get_key_info(key_id)

    def get_session(self, session_id: str) -> Optional[QKDSessionResult]:
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> List[QKDSessionResult]:
        return list(self._sessions.values())

    def clear_pool(self, user_pair: Optional[str] = None):
        self._pool.clear_pool(user_pair)

    # ── Eve Key Theft ─────────────────────────────────────────────────── #

    def register_stolen_key(self, key_id: str, key_hex: str) -> None:
        """Record that Eve has a covert copy of key_id."""
        self._eve_stolen_keys[key_id] = key_hex

    def steal_active_key(self, user_pair: str = "alice:bob") -> Optional[str]:
        """
        Eve grabs what Alice & Bob currently consider their active key.
        Returns the key_id that was stolen, or None if no key is available.
        """
        entry = self._pool.get_active_key(user_pair)
        if entry:
            self._eve_stolen_keys[entry.key_id] = entry.key_hex
            return entry.key_id
        return None

    def eve_can_decrypt(self, key_id: Optional[str]) -> bool:
        """True when Eve holds a stolen copy of the given key."""
        return bool(key_id and key_id in self._eve_stolen_keys)

    def decrypt_with_stolen_key(
        self,
        ciphertext_hex: str,
        key_id: str,
        method: str = "otp",
        nonce_hex: Optional[str] = None,
    ) -> str:
        """Eve decrypts a message using her stolen key material."""
        key_hex = self._eve_stolen_keys.get(key_id)
        if not key_hex:
            raise ValueError(f"Eve has no stolen copy of key {key_id}")
        ct = bytes.fromhex(ciphertext_hex)
        if method == "aes":
            if not nonce_hex:
                raise ValueError("AES requires nonce")
            return _aes_decrypt(bytes.fromhex(nonce_hex), ct, key_hex).decode("utf-8")
        return _xor_encrypt(ct, key_hex).decode("utf-8")  # XOR is self-inverse

    def get_stolen_key_ids(self) -> List[str]:
        return list(self._eve_stolen_keys.keys())

    def clear_stolen_keys(self) -> None:
        self._eve_stolen_keys.clear()

    # ── Alerts ───────────────────────────────────────────────────────── #

    def _raise_alert(
        self, severity: str, message: str,
        link_id: Optional[str] = None, qber: Optional[float] = None,
    ):
        from datetime import datetime, timezone
        self._alert_id += 1
        alert = SecurityAlert(
            id=self._alert_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            message=message,
            link_id=link_id,
            qber=qber,
        )
        self._alerts.append(alert)

    def get_alerts(self, limit: int = 50) -> List[SecurityAlert]:
        return list(reversed(self._alerts[-limit:]))

    def clear_alerts(self):
        self._alerts.clear()
