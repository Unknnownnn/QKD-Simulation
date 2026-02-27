"""
main.py — FastAPI application entry point.
Full-stack QKD Secure Communication Platform backend.

Provides REST + WebSocket APIs for:
  - User auth & presence
  - Real-time encrypted chat
  - QKD key management (generate, distribute, consume)
  - Network topology & SDN routing
  - Attack (Eve) simulation
  - Guided demo mode
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import CORS_ORIGINS
from database import init_db, seed_demo_users, get_db
from auth import create_access_token, get_current_user
from models import (
    UserCreate, UserResponse, TokenResponse,
    ChatMessage, MessageType,
    KeyGenerationConfig, KeyRequest, KeyInfo, KeyPoolStatus,
    QKDSessionResult,
    NetworkTopology, NetworkNode, NetworkLink,
    EveConfig, EveStatus, AttackResult, AttackType,
    RouteAlertResponse, SecurityAlert,
    DemoState, DemoStep, WSMessage,
    EveIntercepts,
)
from kms.key_manager import KeyManager
from network_manager import NetworkManager
from websocket_manager import ConnectionManager
from demo_manager import DemoManager


# ── Global state ─────────────────────────────────────────────────────── #

key_manager = KeyManager(pool_size=50)
network_mgr = NetworkManager()
ws_manager = ConnectionManager()
demo_mgr = DemoManager()


# ── Lifespan ─────────────────────────────────────────────────────────── #

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_demo_users()
    yield

app = FastAPI(
    title="QKD Secure Communication Platform",
    description="Full-stack secure messaging with Quantum Key Distribution",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================================================================== #
#  AUTH ROUTES                                                            #
# ===================================================================== #

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(body: UserCreate):
    """Login or auto-register a user."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT user_id, username, display_name, created_at FROM users WHERE username=?",
            (body.username,),
        )
        if row:
            user_id, username, dname, created = row[0]
        else:
            cursor = await db.execute(
                "INSERT INTO users (username, display_name) VALUES (?, ?)",
                (body.username, body.display_name or body.username.title()),
            )
            await db.commit()
            user_id = cursor.lastrowid
            username = body.username
            dname = body.display_name or body.username.title()
            created = datetime.now(timezone.utc).isoformat()

        await db.execute("UPDATE users SET online=1 WHERE user_id=?", (user_id,))
        await db.commit()

        token = create_access_token({"sub": str(user_id), "username": username})
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                user_id=user_id,
                username=username,
                display_name=dname,
                online=True,
                created_at=str(created),
            ),
        )
    finally:
        await db.close()


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT user_id, username, display_name, online, created_at FROM users WHERE user_id=?",
            (int(current_user["sub"]),),
        )
        if not rows:
            raise HTTPException(404, "User not found")
        r = rows[0]
        return UserResponse(user_id=r[0], username=r[1], display_name=r[2],
                            online=bool(r[3]), created_at=str(r[4]))
    finally:
        await db.close()


@app.get("/api/users", response_model=List[UserResponse])
async def list_users():
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT user_id, username, display_name, online, created_at FROM users"
        )
        result = []
        for r in rows:
            result.append(UserResponse(
                user_id=r[0], username=r[1], display_name=r[2],
                online=ws_manager.is_online(r[0]), created_at=str(r[4]),
            ))
        return result
    finally:
        await db.close()


# ===================================================================== #
#  CHAT ROUTES                                                            #
# ===================================================================== #

@app.delete("/api/messages")
async def clear_messages(current_user: dict = Depends(get_current_user)):
    """Clear all messages from the database."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM messages")
        await db.commit()
    finally:
        await db.close()
    await ws_manager.broadcast(ws_manager.make_event("messages_cleared", {}))
    return {"status": "ok"}


@app.get("/api/messages", response_model=List[ChatMessage])
async def get_messages(channel: str = "general", limit: int = 100):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT m.message_id, m.sender_id, u.username, m.channel_name,
                      m.recipient_id, m.message_type, m.plaintext, m.ciphertext,
                      m.encryption_method, m.key_id, m.timestamp, m.metadata
               FROM messages m JOIN users u ON m.sender_id = u.user_id
               WHERE m.channel_name=?
               ORDER BY m.message_id DESC LIMIT ?""",
            (channel, limit),
        )
        msgs = []
        for r in rows:
            msgs.append(ChatMessage(
                id=r[0], sender_id=r[1], sender_name=r[2], channel=r[3],
                recipient_id=r[4], message_type=r[5], plaintext=r[6],
                ciphertext=r[7], encryption_method=r[8], key_id=r[9],
                timestamp=str(r[10]), metadata=json.loads(r[11]) if r[11] else {},
            ))
        msgs.reverse()
        return msgs
    finally:
        await db.close()


class SendMessageRequest(BaseModel):
    plaintext: str
    channel: str = "general"
    encryption_method: str = "otp"
    recipient_id: Optional[int] = None

@app.post("/api/messages/send", response_model=ChatMessage)
async def send_message(body: SendMessageRequest, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])

    # Always fetch fresh identity from DB — prevents stale JWT issues
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT username, display_name FROM users WHERE user_id=?", (user_id,)
        )
        if not rows:
            raise HTTPException(404, "User not found")
        username = rows[0][0]       # raw username for key lookup
        display_name = rows[0][1]   # human-readable name shown in chat
    finally:
        await db.close()

    # Encrypt if key available
    ciphertext = None
    key_id = None
    method = "none"

    active_key = key_manager.get_session_key("alice:bob")
    if active_key and body.encryption_method != "none":
        try:
            result = key_manager.encrypt_message(
                body.plaintext, active_key.key_id, body.encryption_method,
            )
            ciphertext = result["ciphertext"]
            key_id = active_key.key_id
            method = body.encryption_method
        except Exception:
            pass

    # Store in DB
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO messages (sender_id, channel_name, recipient_id, message_type,
                                    plaintext, ciphertext, encryption_method, key_id, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, body.channel, body.recipient_id, "text",
             body.plaintext, ciphertext, method, key_id, "{}"),
        )
        await db.commit()
        msg_id = cursor.lastrowid

        ts_rows = await db.execute_fetchall(
            "SELECT timestamp FROM messages WHERE message_id=?", (msg_id,)
        )
        ts = str(ts_rows[0][0]) if ts_rows else datetime.now(timezone.utc).isoformat()
    finally:
        await db.close()

    msg = ChatMessage(
        id=msg_id, sender_id=user_id, sender_name=display_name,
        channel=body.channel, recipient_id=body.recipient_id,
        message_type=MessageType.TEXT, plaintext=body.plaintext,
        ciphertext=ciphertext, encryption_method=method,
        key_id=key_id, timestamp=ts,
    )

    # Broadcast via WebSocket
    await ws_manager.broadcast(ws_manager.make_event("new_message", msg.model_dump()))

    # ── Eve interception ─────────────────────────────────────────────── #
    eve = network_mgr.get_eve_status()
    has_stolen_keys = bool(key_manager.get_stolen_key_ids())

    # Eve can see this message if EITHER:
    # A) Her QBER-raising network attack is active AND the current SDN route
    #    passes through her compromised link (smart routing may divert around her).
    # B) She has stolen key material — this implies a physical side-channel tap
    #    (hardware trojan, insider leak, compromised key generation) that is
    #    independent of SDN routing and does NOT raise QBER.  She sees ALL
    #    traffic on the wire regardless of which logical route was chosen.
    route_tapped = eve.active and network_mgr.is_route_compromised()
    if route_tapped or has_stolen_keys:
        # Determine what Eve can read:
        # 1. Unencrypted message — trivially readable.
        # 2. She stole a copy of this key (side-channel) — full decrypt.
        # 3. Stealthy QBER attack (PNS / Trojan Horse) on active route — she
        #    captured enough key bits to decrypt.
        # 4. Intercept-resend on active route — QBER spiked, key was
        #    invalidated, she holds ciphertext she cannot open.
        stealthy = route_tapped and eve.attack_type in ("pns", "trojan_horse")
        unencrypted = ciphertext is None

        if unencrypted:
            plaintext_for_eve = body.plaintext      # trivially readable
        elif key_manager.eve_can_decrypt(key_id):  # stolen key!
            try:
                plaintext_for_eve = key_manager.decrypt_with_stolen_key(
                    ciphertext, key_id, method
                )
            except Exception:
                plaintext_for_eve = None
        elif stealthy:
            plaintext_for_eve = body.plaintext      # partial key sufficient
        else:
            plaintext_for_eve = None                # intercept-resend: key gone

        network_mgr.log_intercepted_message(
            sender=display_name,
            channel=body.channel,
            ciphertext_hex=ciphertext if ciphertext else f"[PLAINTEXT] {body.plaintext}",
            key_id=key_id,
            plaintext_len=len(body.plaintext),
            plaintext=plaintext_for_eve,
        )
        await ws_manager.broadcast(ws_manager.make_event(
            "intercept_update",
            network_mgr.get_intercepts(
                stolen_key_ids=key_manager.get_stolen_key_ids()
            ).model_dump(),
        ))

    return msg


class DecryptRequest(BaseModel):
    ciphertext: str
    key_id: str
    method: str = "otp"
    nonce: Optional[str] = None

@app.post("/api/messages/decrypt")
async def decrypt_message(body: DecryptRequest):
    try:
        plaintext = key_manager.decrypt_message(
            body.ciphertext, body.key_id, body.method, body.nonce,
        )
        return {"plaintext": plaintext, "success": True}
    except Exception as e:
        return {"plaintext": "", "success": False, "error": str(e)}


# ===================================================================== #
#  KEY MANAGEMENT ROUTES                                                  #
# ===================================================================== #

@app.post("/api/keys/generate", response_model=QKDSessionResult)
async def generate_key(config: KeyGenerationConfig):
    """Run BB84 QKD and store the result.

    Key insight: QKD uses the *same physical route* as the messages.
    - If smart routing has diverted traffic AROUND Eve's link, the BB84
      photons also travel on the safe path → Eve is not in the loop →
      key generation succeeds even though Eve is "active" elsewhere.
    - If the current route PASSES THROUGH Eve's compromised link, we
      inject Eve into the BB84 simulation.  Intercept-resend yields
      QBER ≈ 25 % which is above the 11 % threshold → session aborted,
      no key stored.  Stealthy attacks may sneak through at lower QBER.
    """
    eve = network_mgr.get_eve_status()
    if eve.active:
        if network_mgr.is_route_compromised():
            # QKD photons traverse Eve's tap — force Eve into simulation
            config.eve_active = True
            config.eve_intercept_rate = min(0.9, max(0.4, eve.qber_impact or 0.9))
        else:
            # Smart routing has taken us around Eve — photons are safe
            config.eve_active = False

    session_result, key_info = key_manager.generate_key("alice:bob", config)

    # Push QBER to network
    network_mgr.push_session_qber(session_result.qber)

    # Broadcast key event
    await ws_manager.broadcast(ws_manager.make_event("key_generated", {
        "session": session_result.model_dump(),
        "key": key_info.model_dump() if key_info else None,
    }))

    return session_result


@app.get("/api/keys/pool", response_model=KeyPoolStatus)
async def get_key_pool_status(user_pair: str = "alice:bob"):
    return key_manager.get_pool_status(user_pair)


@app.get("/api/keys/list", response_model=List[KeyInfo])
async def list_keys(user_pair: str = "alice:bob"):
    return key_manager.get_all_keys(user_pair)


@app.get("/api/keys/{key_id}", response_model=KeyInfo)
async def get_key(key_id: str):
    info = key_manager.get_key_info(key_id)
    if not info:
        raise HTTPException(404, "Key not found")
    return info


@app.post("/api/keys/request")
async def request_session_key(body: KeyRequest):
    """Get an active key for a user pair, or generate one if empty."""
    key_info = key_manager.get_session_key(body.user_pair)
    if not key_info:
        # Auto-generate
        config = KeyGenerationConfig(key_length=body.key_length)
        session_result, key_info = key_manager.generate_key(body.user_pair, config)
        if not key_info:
            raise HTTPException(503, "Key generation failed (possibly Eve detected)")
    return {"key": key_info.model_dump(), "needs_refresh": False}


@app.post("/api/keys/{key_id}/consume")
async def consume_key(key_id: str):
    hex_key = key_manager.consume_session_key(key_id)
    if not hex_key:
        raise HTTPException(404, "Key not available or already consumed")
    return {"consumed": True, "key_id": key_id}


@app.delete("/api/keys/pool")
async def clear_key_pool(user_pair: Optional[str] = None):
    key_manager.clear_pool(user_pair)
    return {"cleared": True}


@app.get("/api/keys/sessions/list", response_model=List[QKDSessionResult])
async def list_sessions():
    return key_manager.get_all_sessions()


# ===================================================================== #
#  NETWORK / SDN ROUTES                                                   #
# ===================================================================== #

@app.get("/api/network/topology", response_model=NetworkTopology)
async def get_topology():
    return network_mgr.get_topology()


@app.get("/api/network/route")
async def get_route(src: str = "A", dst: str = "B"):
    route = network_mgr.get_active_route(src, dst)
    return {"route": route, "smart_routing": network_mgr.smart_routing_enabled}


@app.post("/api/network/smart-routing")
async def toggle_smart_routing(enabled: bool = True):
    network_mgr.smart_routing_enabled = enabled
    topo = network_mgr.get_topology()
    await ws_manager.broadcast(ws_manager.make_event("topology_update", topo.model_dump()))
    return {"smart_routing": enabled, "route": topo.active_route}


@app.get("/api/network/links")
async def list_links():
    return {"links": network_mgr.get_link_ids()}


@app.get("/api/network/alerts", response_model=List[RouteAlertResponse])
async def get_network_alerts(limit: int = 50):
    return network_mgr.get_alerts(limit)


# ===================================================================== #
#  ATTACK / EVE ROUTES                                                    #
# ===================================================================== #

@app.get("/api/eve/status", response_model=EveStatus)
async def get_eve_status():
    return network_mgr.get_eve_status()


@app.post("/api/eve/activate", response_model=AttackResult)
async def activate_eve(config: EveConfig):
    result = network_mgr.simulate_attack(config.target_links, config.attack_type.value)

    # If QBER spiked, invalidate compromised keys
    if result.qber_after > 0.11:
        first_link = config.target_links[0] if config.target_links else ""
        invalidated = key_manager.handle_qber_alert(result.qber_after, first_link)
        result.key_impact = f"Invalidated {len(invalidated)} key(s)" if invalidated else "No keys compromised"

    # Broadcast attack event
    topo = network_mgr.get_topology()
    await ws_manager.broadcast(ws_manager.make_event("attack_detected", {
        "result": result.model_dump(),
        "topology": topo.model_dump(),
        "eve": network_mgr.get_eve_status().model_dump(),
    }))

    # Also push fresh intercept data so Charlie's console updates immediately
    await ws_manager.broadcast(ws_manager.make_event(
        "intercept_update",
        network_mgr.get_intercepts(
            stolen_key_ids=key_manager.get_stolen_key_ids()
        ).model_dump(),
    ))

    return result


@app.post("/api/eve/deactivate")
async def deactivate_eve(link_id: Optional[str] = None):
    if link_id:
        network_mgr.clear_attack(link_id)
    else:
        network_mgr.clear_all_attacks()
        # Clear Eve's stolen keys when she's fully deactivated
        key_manager.clear_stolen_keys()

    topo = network_mgr.get_topology()
    await ws_manager.broadcast(ws_manager.make_event("attack_cleared", {
        "topology": topo.model_dump(),
        "eve": network_mgr.get_eve_status().model_dump(),
    }))
    return {"cleared": True}


@app.get("/api/eve/intercepts", response_model=EveIntercepts)
async def get_eve_intercepts(qubit_limit: int = 128, msg_limit: int = 50):
    """Return Eve's intercept log — for Charlie's attacker dashboard."""
    return network_mgr.get_intercepts(
        qubit_limit=qubit_limit,
        msg_limit=msg_limit,
        stolen_key_ids=key_manager.get_stolen_key_ids(),
    )


# ===================================================================== #
#  EVE KEY THEFT / COMPROMISED KEY GENERATION                            #
# ===================================================================== #

@app.post("/api/eve/steal-key")
async def eve_steal_key():
    """
    Eve grabs a covert copy of whatever key Alice & Bob are currently using.
    This simulates a perfect side-channel theft (hardware trojan, insider
    threat, etc.) — the key itself is NOT invalidated for Alice & Bob;
    they remain unaware.  Eve can now decrypt any message encrypted with
    that key.
    """
    key_id = key_manager.steal_active_key("alice:bob")
    if not key_id:
        raise HTTPException(404, "No active key found for alice:bob to steal")
    await ws_manager.broadcast(ws_manager.make_event(
        "intercept_update",
        network_mgr.get_intercepts(
            stolen_key_ids=key_manager.get_stolen_key_ids()
        ).model_dump(),
    ))
    return {"stolen": True, "key_id": key_id, "stolen_count": len(key_manager.get_stolen_key_ids())}


class CompromisedKeyConfig(BaseModel):
    key_length: int = 512
    noise_depol: float = 0.01
    noise_loss: float = 0.02


@app.post("/api/keys/generate-compromised", response_model=QKDSessionResult)
async def generate_compromised_key(config: CompromisedKeyConfig):
    """
    Generate a fresh QKD key for Alice & Bob AND secretly hand Eve a copy.

    This models the scenario where Eve's eavesdropping is undetected —
    e.g. a near-perfect PNS or Trojan Horse attack that keeps QBER below
    the detection threshold.  The key is stored in Alice & Bob's pool
    normally, AND registered in Eve's stolen-key store.  When Alice or Bob
    subsequently encrypt a message with this key, Eve sees the plaintext.
    """
    kconf = KeyGenerationConfig(
        key_length=config.key_length,
        noise_depol=config.noise_depol,
        noise_loss=config.noise_loss,
        eve_active=False,    # don't spike QBER — Eve is covert here
    )
    session_result, key_info = key_manager.generate_key("alice:bob", kconf)

    if not key_info:
        raise HTTPException(
            503,
            "Key generation failed — the simulated session produced no usable key. "
            "Try again with lower noise parameters."
        )

    # Eve silently copies the key material
    key_material = key_manager.get_key_material(key_info.key_id)
    if key_material:
        key_manager.register_stolen_key(key_info.key_id, key_material)

    # Push QBER to network so the dashboard updates
    network_mgr.push_session_qber(session_result.qber)

    await ws_manager.broadcast(ws_manager.make_event("key_generated", {
        "session": session_result.model_dump(),
        "key": key_info.model_dump(),
    }))
    await ws_manager.broadcast(ws_manager.make_event(
        "intercept_update",
        network_mgr.get_intercepts(
            stolen_key_ids=key_manager.get_stolen_key_ids()
        ).model_dump(),
    ))
    return session_result


@app.delete("/api/eve/stolen-keys")
async def clear_stolen_keys():
    """Clear all of Eve's stolen keys (e.g. after she's deactivated)."""
    key_manager.clear_stolen_keys()
    return {"cleared": True}


# ===================================================================== #
#  SECURITY ALERTS                                                        #
# ===================================================================== #

@app.get("/api/alerts", response_model=List[SecurityAlert])
async def get_security_alerts(limit: int = 50):
    return key_manager.get_alerts(limit)


@app.delete("/api/alerts")
async def clear_alerts():
    key_manager.clear_alerts()
    return {"cleared": True}


# ===================================================================== #
#  DEMO MODE                                                              #
# ===================================================================== #

@app.get("/api/demo/state", response_model=DemoState)
async def get_demo_state():
    return demo_mgr.state


@app.post("/api/demo/start", response_model=DemoState)
async def start_demo():
    state = demo_mgr.start()
    await ws_manager.broadcast(ws_manager.make_event("demo_started", state.model_dump()))
    return state


@app.post("/api/demo/advance")
async def advance_demo():
    step = demo_mgr.advance()
    if not step:
        return {"done": True, "state": demo_mgr.state.model_dump()}

    result_data: Dict[str, Any] = {"step": step.model_dump()}

    # Execute the demo action
    if step.action == "normal_chat":
        # Generate a key
        config = KeyGenerationConfig(key_length=256, noise_depol=0.01, noise_loss=0.02)
        session, key_info = key_manager.generate_key("alice:bob", config)
        result_data["session"] = session.model_dump()
        result_data["key"] = key_info.model_dump() if key_info else None
        demo_mgr.complete_step(step.step, {"session_id": session.session_id})

    elif step.action == "activate_eve":
        attack = network_mgr.simulate_attack(["A→R1"], "intercept_resend")
        result_data["attack"] = attack.model_dump()
        demo_mgr.complete_step(step.step, {"attack": attack.model_dump()})

    elif step.action == "observe_qber":
        # Generate key with Eve active to show QBER spike
        config = KeyGenerationConfig(
            key_length=256, eve_active=True, eve_intercept_rate=1.0,
        )
        session, key_info = key_manager.generate_key("alice:bob", config)
        result_data["session"] = session.model_dump()
        result_data["qber"] = session.qber
        result_data["eve_detected"] = session.eve_detected
        demo_mgr.complete_step(step.step, {"qber": session.qber})

    elif step.action == "smart_routing":
        network_mgr.smart_routing_enabled = True
        topo = network_mgr.get_topology()
        result_data["topology"] = topo.model_dump()
        result_data["new_route"] = topo.active_route
        demo_mgr.complete_step(step.step, {"route": topo.active_route})

    elif step.action == "maintain_comms":
        result_data["message"] = "Communication maintained on secure alternate route"
        demo_mgr.complete_step(step.step)

    elif step.action == "regen_keys":
        network_mgr.clear_all_attacks()
        config = KeyGenerationConfig(key_length=512, noise_depol=0.01, noise_loss=0.02)
        session, key_info = key_manager.generate_key("alice:bob", config)
        result_data["session"] = session.model_dump()
        result_data["key"] = key_info.model_dump() if key_info else None
        demo_mgr.complete_step(step.step, {"session_id": session.session_id})

    await ws_manager.broadcast(ws_manager.make_event("demo_step", result_data))
    return result_data


@app.post("/api/demo/reset", response_model=DemoState)
async def reset_demo():
    network_mgr.clear_all_attacks()
    state = demo_mgr.reset()
    await ws_manager.broadcast(ws_manager.make_event("demo_reset", state.model_dump()))
    return state


# ===================================================================== #
#  WEBSOCKET                                                              #
# ===================================================================== #

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(websocket, user_id)
    ws_manager.join_channel(user_id, "general")

    # Notify others
    await ws_manager.broadcast(
        ws_manager.make_event("user_online", {"user_id": user_id}),
        exclude=user_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "chat_message":
                payload = data.get("data", {})
                # Store in DB
                db = await get_db()
                try:
                    # Fetch display_name for human-readable sender identification
                    u_rows = await db.execute_fetchall(
                        "SELECT username, display_name FROM users WHERE user_id=?", (user_id,)
                    )
                    _ws_username = u_rows[0][0] if u_rows else "unknown"
                    sender_name = (u_rows[0][1] or _ws_username) if u_rows else "unknown"

                    plaintext = payload.get("plaintext", "")
                    channel = payload.get("channel", "general")
                    enc_method = payload.get("encryption_method", "none")

                    # Encrypt if possible
                    ciphertext = None
                    key_id = None
                    active_key = key_manager.get_session_key("alice:bob")
                    if active_key and enc_method != "none":
                        try:
                            result = key_manager.encrypt_message(
                                plaintext, active_key.key_id, enc_method,
                            )
                            ciphertext = result["ciphertext"]
                            key_id = active_key.key_id
                        except Exception:
                            enc_method = "none"

                    cursor = await db.execute(
                        """INSERT INTO messages (sender_id, channel_name, message_type,
                                                plaintext, ciphertext, encryption_method, key_id)
                           VALUES (?, ?, 'text', ?, ?, ?, ?)""",
                        (user_id, channel, plaintext, ciphertext, enc_method, key_id),
                    )
                    await db.commit()
                    msg_id = cursor.lastrowid
                    ts_rows = await db.execute_fetchall(
                        "SELECT timestamp FROM messages WHERE message_id=?", (msg_id,)
                    )
                    ts = str(ts_rows[0][0]) if ts_rows else ""
                finally:
                    await db.close()

                msg = {
                    "id": msg_id,
                    "sender_id": user_id,
                    "sender_name": sender_name,
                    "channel": channel,
                    "message_type": "text",
                    "plaintext": plaintext,
                    "ciphertext": ciphertext,
                    "encryption_method": enc_method,
                    "key_id": key_id,
                    "timestamp": ts,
                }
                await ws_manager.broadcast(ws_manager.make_event("new_message", msg))

            elif msg_type == "typing":
                await ws_manager.broadcast(
                    ws_manager.make_event("typing", {"user_id": user_id}),
                    exclude=user_id,
                )

            elif msg_type == "join_channel":
                ch = data.get("data", {}).get("channel", "general")
                ws_manager.join_channel(user_id, ch)

            elif msg_type == "ping":
                await ws_manager.send_personal(user_id, ws_manager.make_event("pong"))

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
        # Mark offline
        db = await get_db()
        try:
            await db.execute("UPDATE users SET online=0 WHERE user_id=?", (user_id,))
            await db.commit()
        finally:
            await db.close()
        await ws_manager.broadcast(
            ws_manager.make_event("user_offline", {"user_id": user_id}),
        )


# ===================================================================== #
#  HEALTH                                                                 #
# ===================================================================== #

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "online_users": len(ws_manager.get_online_users()),
        "key_pool": key_manager.get_pool_status().model_dump(),
        "smart_routing": network_mgr.smart_routing_enabled,
    }


# ===================================================================== #
#  RUN                                                                    #
# ===================================================================== #

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
