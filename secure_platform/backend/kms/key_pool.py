"""
key_pool.py — Thread-safe in-memory key pool with DB persistence.
Stores QKD-generated keys for each user pair, tracks lifecycle, prevents reuse.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Tuple

from models import KeyInfo, KeyStatus, KeyPoolStatus


class KeyEntry:
    """Internal key record."""
    __slots__ = (
        "key_id", "user_pair", "key_bits_list", "key_hex",
        "key_bits", "status", "qber", "encryption_method",
        "sha256", "created_at", "used_at", "session_id",
    )

    def __init__(
        self,
        key_id: str,
        user_pair: str,
        key_bits_list: List[int],
        qber: float = 0.0,
        encryption_method: str = "otp",
        session_id: str = "",
    ):
        self.key_id = key_id
        self.user_pair = user_pair
        self.key_bits_list = key_bits_list
        self.key_hex = self._bits_to_hex(key_bits_list)
        self.key_bits = len(key_bits_list)
        self.status: KeyStatus = KeyStatus.ACTIVE
        self.qber = qber
        self.encryption_method = encryption_method
        self.sha256 = hashlib.sha256(bytes.fromhex(self.key_hex)).hexdigest()
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.used_at: Optional[str] = None
        self.session_id = session_id

    @staticmethod
    def _bits_to_hex(bits: List[int]) -> str:
        padded = bits + [0] * ((-len(bits)) % 8)
        ba = bytearray()
        for i in range(0, len(padded), 8):
            byte = 0
            for b in padded[i:i + 8]:
                byte = (byte << 1) | b
            ba.append(byte)
        return bytes(ba).hex()

    def to_info(self) -> KeyInfo:
        return KeyInfo(
            key_id=self.key_id,
            user_pair=self.user_pair,
            key_bits=self.key_bits,
            key_bytes=self.key_bits // 8,
            status=self.status,
            qber=self.qber,
            created_at=self.created_at,
            used_at=self.used_at,
            encryption_method=self.encryption_method,
            sha256=self.sha256[:20] + "...",
        )


class KeyPool:
    """
    Manages synchronized key pools for user pairs.
    - Stores QKD-generated keys
    - Prevents key reuse
    - Tracks key lifecycle
    - Supports OTP and AES key derivation
    - Invalidates keys when QBER exceeds threshold
    """

    def __init__(self, max_pool_size: int = 50):
        self._lock = Lock()
        self._pools: Dict[str, List[KeyEntry]] = defaultdict(list)
        self._all_keys: Dict[str, KeyEntry] = {}
        self._max_pool_size = max_pool_size
        self._auto_refresh = True
        self._alert_callbacks = []

    # ── Key storage ──────────────────────────────────────────────────── #

    def add_key(
        self,
        user_pair: str,
        key_bits: List[int],
        qber: float = 0.0,
        encryption_method: str = "otp",
        session_id: str = "",
    ) -> KeyEntry:
        """Store a new QKD-generated key in the pool."""
        with self._lock:
            key_id = f"qkd-{secrets.token_hex(8)}"
            entry = KeyEntry(
                key_id=key_id,
                user_pair=user_pair,
                key_bits_list=key_bits,
                qber=qber,
                encryption_method=encryption_method,
                session_id=session_id,
            )
            self._pools[user_pair].append(entry)
            self._all_keys[key_id] = entry

            # Enforce pool size limit (remove oldest used keys first)
            pool = self._pools[user_pair]
            if len(pool) > self._max_pool_size:
                pool[:] = [k for k in pool if k.status == KeyStatus.ACTIVE] + \
                          sorted([k for k in pool if k.status != KeyStatus.ACTIVE],
                                 key=lambda k: k.created_at)[-10:]

            return entry

    def get_active_key(self, user_pair: str) -> Optional[KeyEntry]:
        """Get the next available active key for a user pair."""
        with self._lock:
            pool = self._pools.get(user_pair, [])
            for key in pool:
                if key.status == KeyStatus.ACTIVE:
                    return key
            return None

    def consume_key(self, key_id: str) -> Optional[KeyEntry]:
        """Mark a key as used (consume it). Returns the key entry."""
        with self._lock:
            entry = self._all_keys.get(key_id)
            if entry and entry.status == KeyStatus.ACTIVE:
                entry.status = KeyStatus.USED
                entry.used_at = datetime.now(timezone.utc).isoformat()
                return entry
            return None

    def get_key_hex(self, key_id: str) -> Optional[str]:
        """Get the hex-encoded key material."""
        with self._lock:
            entry = self._all_keys.get(key_id)
            if entry:
                return entry.key_hex
            return None

    def get_key_bits(self, key_id: str) -> Optional[List[int]]:
        """Get the raw key bits."""
        with self._lock:
            entry = self._all_keys.get(key_id)
            if entry:
                return list(entry.key_bits_list)
            return None

    # ── Security operations ──────────────────────────────────────────── #

    def invalidate_compromised(self, qber_threshold: float = 0.11) -> List[str]:
        """Invalidate all keys generated with QBER above threshold."""
        invalidated = []
        with self._lock:
            for key_id, entry in self._all_keys.items():
                if entry.status == KeyStatus.ACTIVE and entry.qber > qber_threshold:
                    entry.status = KeyStatus.COMPROMISED
                    invalidated.append(key_id)
        return invalidated

    def invalidate_key(self, key_id: str) -> bool:
        """Manually invalidate a specific key."""
        with self._lock:
            entry = self._all_keys.get(key_id)
            if entry:
                entry.status = KeyStatus.COMPROMISED
                return True
            return False

    # ── Pool status ──────────────────────────────────────────────────── #

    def get_pool_status(self, user_pair: Optional[str] = None) -> KeyPoolStatus:
        """Get current pool statistics."""
        with self._lock:
            if user_pair:
                keys = self._pools.get(user_pair, [])
            else:
                keys = list(self._all_keys.values())

            return KeyPoolStatus(
                total_keys=len(keys),
                active_keys=sum(1 for k in keys if k.status == KeyStatus.ACTIVE),
                used_keys=sum(1 for k in keys if k.status == KeyStatus.USED),
                compromised_keys=sum(1 for k in keys if k.status == KeyStatus.COMPROMISED),
                pool_capacity=self._max_pool_size,
                auto_refresh=self._auto_refresh,
            )

    def get_all_keys_info(self, user_pair: Optional[str] = None) -> List[KeyInfo]:
        """List all keys with metadata."""
        with self._lock:
            if user_pair:
                keys = self._pools.get(user_pair, [])
            else:
                keys = list(self._all_keys.values())
            return [k.to_info() for k in keys]

    def get_key_info(self, key_id: str) -> Optional[KeyInfo]:
        """Get info for a specific key."""
        with self._lock:
            entry = self._all_keys.get(key_id)
            if entry:
                return entry.to_info()
            return None

    # ── Utilities ────────────────────────────────────────────────────── #

    def clear_pool(self, user_pair: Optional[str] = None):
        """Clear the key pool."""
        with self._lock:
            if user_pair:
                for k in self._pools.get(user_pair, []):
                    self._all_keys.pop(k.key_id, None)
                self._pools[user_pair] = []
            else:
                self._pools.clear()
                self._all_keys.clear()

    @property
    def auto_refresh(self) -> bool:
        return self._auto_refresh

    @auto_refresh.setter
    def auto_refresh(self, val: bool):
        self._auto_refresh = val
