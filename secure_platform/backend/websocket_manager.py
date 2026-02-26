"""
websocket_manager.py — WebSocket connection manager for real-time communication.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self._connections: Dict[int, WebSocket] = {}   # user_id -> ws
        self._channels: Dict[str, Set[int]] = {}        # channel -> {user_ids}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self._connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self._connections.pop(user_id, None)
        for ch_members in self._channels.values():
            ch_members.discard(user_id)

    async def send_personal(self, user_id: int, message: dict):
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(user_id)

    async def broadcast(self, message: dict, exclude: Optional[int] = None):
        disconnected = []
        for uid, ws in self._connections.items():
            if uid == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(uid)
        for uid in disconnected:
            self.disconnect(uid)

    async def broadcast_to_channel(self, channel: str, message: dict, exclude: Optional[int] = None):
        members = self._channels.get(channel, set())
        for uid in members:
            if uid == exclude:
                continue
            await self.send_personal(uid, message)

    def join_channel(self, user_id: int, channel: str):
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(user_id)

    def leave_channel(self, user_id: int, channel: str):
        if channel in self._channels:
            self._channels[channel].discard(user_id)

    def get_online_users(self) -> List[int]:
        return list(self._connections.keys())

    def is_online(self, user_id: int) -> bool:
        return user_id in self._connections

    @staticmethod
    def make_event(event_type: str, data: Any = None) -> dict:
        return {
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
