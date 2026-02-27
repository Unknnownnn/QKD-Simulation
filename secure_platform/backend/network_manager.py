"""
network_manager.py — SDN network topology & routing manager (non-Qt version).
Wraps the existing SDN logic for use inside FastAPI.
"""
from __future__ import annotations

import heapq
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import uuid
from models import (
    NetworkNode, NetworkLink, NetworkTopology,
    RouteAlertResponse, AttackType, AttackResult,
    EveConfig, EveStatus, SecurityAlert,
    InterceptedQubit, InterceptedMessage, EveIntercepts,
)
from config import (
    DEFAULT_TOPOLOGY_NODES, DEFAULT_TOPOLOGY_EDGES,
    QBER_WARNING_THRESHOLD, QBER_CRITICAL_THRESHOLD,
)


@dataclass
class _Link:
    src: str
    dst: str
    qber: float = 0.0
    compromised: bool = False
    active: bool = True
    attack_type: str = "none"
    latency_ms: float = 5.0

    @property
    def link_id(self) -> str:
        return f"{self.src}→{self.dst}"

    @property
    def status(self) -> str:
        if self.qber < QBER_WARNING_THRESHOLD:
            return "safe"
        if self.qber < QBER_CRITICAL_THRESHOLD:
            return "warning"
        return "critical"


@dataclass
class _Node:
    id: str
    label: str
    role: str = "relay"
    x: float = 0.0
    y: float = 0.0
    active: bool = True
    compromised: bool = False


class NetworkManager:
    """
    Manages the virtual QKD network topology, adaptive routing, and attack simulation.
    Non-Qt version suitable for FastAPI.
    """

    def __init__(self):
        self._nodes: Dict[str, _Node] = {}
        self._links: Dict[str, _Link] = {}
        self._active_routes: Dict[Tuple[str, str], List[str]] = {}
        self._alerts: List[RouteAlertResponse] = []
        self._eve: EveStatus = EveStatus()
        self._smart_routing: bool = True
        self._event_callbacks: List[Callable] = []
        # Eve intercept logs (Charlie's view)
        self._intercept_qubits: List[InterceptedQubit] = []
        self._intercept_messages: List[InterceptedMessage] = []
        self._qubit_counter: int = 0

        self._build_default_topology()

    # ── Topology ─────────────────────────────────────────────────────── #

    def _build_default_topology(self):
        for nd in DEFAULT_TOPOLOGY_NODES:
            self._nodes[nd["id"]] = _Node(
                id=nd["id"], label=nd["label"], role=nd["role"],
                x=nd["x"], y=nd["y"],
            )

        for src, dst in DEFAULT_TOPOLOGY_EDGES:
            lat = random.uniform(2, 10)
            self._links[f"{src}→{dst}"] = _Link(src=src, dst=dst, latency_ms=lat)
            self._links[f"{dst}→{src}"] = _Link(src=dst, dst=src, latency_ms=lat)

        self._recompute_route("A", "B")

    def get_topology(self) -> NetworkTopology:
        nodes = [
            NetworkNode(id=n.id, label=n.label, role=n.role,
                        x=n.x, y=n.y, active=n.active, compromised=n.compromised)
            for n in self._nodes.values()
        ]
        links = [
            NetworkLink(src=l.src, dst=l.dst, qber=l.qber, status=l.status,
                        compromised=l.compromised, active=l.active,
                        attack_type=l.attack_type, latency_ms=l.latency_ms)
            for l in self._links.values()
        ]
        route = self._active_routes.get(("A", "B"), [])
        return NetworkTopology(
            nodes=nodes, links=links, active_route=route,
            smart_routing_enabled=self._smart_routing,
        )

    # ── QBER & Attack ────────────────────────────────────────────────── #

    def update_link_qber(self, link_id: str, new_qber: float, attack_type: str = "none") -> Optional[RouteAlertResponse]:
        lk = self._links.get(link_id)
        if not lk:
            return None

        prev_qber = lk.qber
        lk.qber = max(0.0, min(1.0, new_qber))
        lk.attack_type = attack_type

        if lk.qber >= QBER_CRITICAL_THRESHOLD:
            lk.compromised = True
        elif lk.qber < QBER_WARNING_THRESHOLD:
            lk.compromised = False

        alert = None
        if new_qber >= QBER_WARNING_THRESHOLD and prev_qber < QBER_WARNING_THRESHOLD:
            threshold = "critical" if new_qber >= QBER_CRITICAL_THRESHOLD else "warning"
            new_path = self._recompute_route("A", "B") if self._smart_routing else []
            alert = RouteAlertResponse(
                timestamp=time.time(),
                link_id=link_id,
                qber=new_qber,
                previous_qber=prev_qber,
                threshold=threshold,
                action_taken=f"Rerouted via {' → '.join(new_path)}" if new_path else "No reroute (smart routing disabled)",
                attack_type=attack_type,
            )
            self._alerts.append(alert)

            if lk.compromised and lk.dst in self._nodes:
                self._nodes[lk.dst].compromised = True

        return alert

    def simulate_attack(self, link_ids: List[str], attack_type: str = "intercept_resend") -> AttackResult:
        if not link_ids:
            raise ValueError("No links specified")

        qber_before = 0.0
        max_qber = 0.0
        alert_raised = False
        qber_map = {
            "intercept_resend": lambda: 0.25 + random.uniform(-0.02, 0.02),
            "pns":              lambda: 0.03 + random.uniform(-0.01, 0.01),
            "trojan_horse":     lambda: 0.02 + random.uniform(-0.01, 0.01),
            "noise_injection":  lambda: 0.18 + random.uniform(-0.03, 0.05),
        }

        for link_id in link_ids:
            lk = self._links.get(link_id)
            if not lk:
                continue
            qber_before = max(qber_before, lk.qber)

            # Generate qubit batch per link
            batch = self._generate_qubit_batch(attack_type=attack_type, n=max(32, 64 // len(link_ids)))
            self._intercept_qubits.extend(batch)
            if len(self._intercept_qubits) > 500:
                self._intercept_qubits = self._intercept_qubits[-500:]

            new_qber = qber_map.get(attack_type, lambda: random.uniform(0.12, 0.30))()
            max_qber = max(max_qber, new_qber)
            alert = self.update_link_qber(link_id, new_qber, attack_type)
            if alert:
                alert_raised = True

        # Update Eve status
        self._eve = EveStatus(
            active=True,
            attack_type=attack_type,
            target_links=link_ids,
            intercepted_count=self._eve.intercepted_count + 1,
            qber_impact=max_qber,
        )

        new_route = self._active_routes.get(("A", "B"), [])
        return AttackResult(
            attack_type=attack_type,
            target_link=link_ids[0] if link_ids else "",
            target_links=link_ids,
            qber_before=qber_before,
            qber_after=max_qber,
            key_impact="compromised" if max_qber >= QBER_WARNING_THRESHOLD else "minimal",
            alert_raised=alert_raised,
            rerouted=alert_raised and self._smart_routing,
            new_route=new_route,
        )

    def clear_attack(self, link_id: str):
        lk = self._links.get(link_id)
        if lk:
            lk.compromised = False
            lk.attack_type = "none"
            lk.qber = random.uniform(0.005, 0.04)
            if lk.dst in self._nodes:
                self._nodes[lk.dst].compromised = False
            self._recompute_route("A", "B")
        # Remove this link from Eve's active target list
        remaining = [l for l in self._eve.target_links if l != link_id]
        if remaining:
            self._eve = EveStatus(
                active=True,
                attack_type=self._eve.attack_type,
                target_links=remaining,
                intercepted_count=self._eve.intercepted_count,
                qber_impact=self._eve.qber_impact,
            )
        else:
            self._eve = EveStatus()  # All links cleared

    def clear_all_attacks(self):
        for lk in self._links.values():
            lk.compromised = False
            lk.attack_type = "none"
            lk.qber = random.uniform(0.005, 0.04)
        for nd in self._nodes.values():
            nd.compromised = False
        self._eve = EveStatus()
        self._recompute_route("A", "B")
        # Keep intercept history for review

    # ── Intercept Logging (Eve / Charlie) ───────────────────────────── #

    def _generate_qubit_batch(
        self, attack_type: str = "intercept_resend", n: int = 64
    ) -> List[InterceptedQubit]:
        """Generate a batch of synthetic qubit-intercept records."""
        bases = ["+", "x"]
        batch: List[InterceptedQubit] = []
        t = time.time()
        for i in range(n):
            alice_basis = random.choice(bases)
            alice_bit = random.randint(0, 1)

            if attack_type == "intercept_resend":
                eve_basis = random.choice(bases)
                basis_match = eve_basis == alice_basis
                if basis_match:
                    eve_measured = alice_bit
                    actual = alice_bit
                    disturbed = False
                else:
                    eve_measured = random.randint(0, 1)
                    actual = None          # Unknown — wrong basis
                    disturbed = (eve_measured != alice_bit)

            elif attack_type == "pns":
                # Photon-Number Splitting: Eve only captures multi-photon pulses (~15%)
                if random.random() < 0.15:
                    eve_basis = alice_basis        # PNS gives correct clone
                    basis_match = True
                    eve_measured = alice_bit
                    actual = alice_bit
                    disturbed = False
                else:
                    eve_basis = random.choice(bases)
                    basis_match = False
                    eve_measured = random.randint(0, 1)
                    actual = None
                    disturbed = False      # PNS doesn't disturb single-photon channel

            elif attack_type == "trojan_horse":
                # Trojan Horse: Eve learns Alice's basis/bit with ~70% fidelity
                eve_basis = alice_basis if random.random() < 0.70 else random.choice(bases)
                basis_match = eve_basis == alice_basis
                eve_measured = alice_bit if basis_match else random.randint(0, 1)
                actual = alice_bit if basis_match else None
                disturbed = False

            else:  # noise_injection or unknown
                eve_basis = random.choice(bases)
                basis_match = eve_basis == alice_basis
                eve_measured = random.randint(0, 1)   # Noisy — random output
                actual = alice_bit if basis_match and random.random() < 0.6 else None
                disturbed = random.random() < 0.18

            self._qubit_counter += 1
            batch.append(InterceptedQubit(
                qubit_id=self._qubit_counter,
                timestamp=t + i * 0.0002,
                alice_basis=alice_basis,
                eve_basis=eve_basis,
                eve_measured=eve_measured,
                alice_bit=actual,
                basis_match=basis_match,
                disturbed=disturbed,
            ))
        return batch

    def log_intercepted_message(
        self,
        sender: str,
        channel: str,
        ciphertext_hex: str,
        key_id: Optional[str] = None,
        plaintext_len: int = 0,
        plaintext: Optional[str] = None,
    ):
        """Record a message that Eve intercepted on the wire."""
        if not self._eve.active:
            return
        entry = InterceptedMessage(
            msg_id=uuid.uuid4().hex[:10],
            timestamp=time.time(),
            channel=channel,
            sender=sender,
            ciphertext_hex=ciphertext_hex,
            key_id=key_id,
            plaintext=plaintext,
            plaintext_len=plaintext_len,
            decrypted=plaintext is not None,
        )
        self._intercept_messages.append(entry)
        if len(self._intercept_messages) > 200:
            self._intercept_messages = self._intercept_messages[-200:]

    def get_intercepts(self, qubit_limit: int = 128, msg_limit: int = 50,
                        stolen_key_ids: Optional[List[str]] = None) -> EveIntercepts:
        """Return current intercept state for Eve's console."""
        qubits = self._intercept_qubits[-qubit_limit:]
        msgs = self._intercept_messages[-msg_limit:]
        matched = sum(1 for q in self._intercept_qubits if q.basis_match)
        exposed = sum(1 for q in self._intercept_qubits if q.alice_bit is not None)
        return EveIntercepts(
            active=self._eve.active,
            attack_type=self._eve.attack_type,
            target_links=self._eve.target_links,
            qubits_total=len(self._intercept_qubits),
            qubits_matched=matched,
            key_bits_exposed=exposed,
            messages_captured=len(self._intercept_messages),
            qubits=qubits,
            messages=msgs,
            stolen_key_ids=stolen_key_ids or [],
        )

    # ── Smart Routing ────────────────────────────────────────────────── #

    @property
    def smart_routing_enabled(self) -> bool:
        return self._smart_routing

    @smart_routing_enabled.setter
    def smart_routing_enabled(self, val: bool):
        self._smart_routing = val
        if val:
            self._recompute_route("A", "B")

    def _recompute_route(self, src: str, dst: str) -> List[str]:
        INF = float('inf')
        dist = {n: INF for n in self._nodes}
        prev: Dict[str, Optional[str]] = {n: None for n in self._nodes}
        dist[src] = 0.0
        heap = [(0.0, src)]

        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for lk in self._links.values():
                if lk.src != u or not lk.active:
                    continue
                if self._smart_routing:
                    cost = INF if lk.compromised else (lk.qber + lk.latency_ms / 100.0)
                else:
                    cost = lk.latency_ms / 100.0  # ignore QBER when smart routing off
                nd = d + cost
                if nd < dist[lk.dst]:
                    dist[lk.dst] = nd
                    prev[lk.dst] = u
                    heapq.heappush(heap, (nd, lk.dst))

        path: List[str] = []
        cur: Optional[str] = dst
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()

        if path and path[0] == src:
            self._active_routes[(src, dst)] = path
            return path
        return []

    def get_active_route(self, src: str = "A", dst: str = "B") -> List[str]:
        return self._active_routes.get((src, dst), [])

    # ── Status ───────────────────────────────────────────────────────── #

    def get_eve_status(self) -> EveStatus:
        return self._eve

    def is_route_compromised(self, src: str = "A", dst: str = "B") -> bool:
        """
        Return True if the active route from src→dst passes through any
        compromised link (i.e. Eve is watching that segment).

        When smart routing is on, Dijkstra avoids compromised links entirely,
        so this returns False — meaning messages travel on a safe path and
        Eve cannot intercept them.  When smart routing is off (or all paths
        are compromised), this returns True.
        """
        route = self._active_routes.get((src, dst), [])
        for i in range(len(route) - 1):
            link_id = f"{route[i]}→{route[i + 1]}"
            lk = self._links.get(link_id)
            if lk and lk.compromised:
                return True
        return False

    def get_alerts(self, limit: int = 50) -> List[RouteAlertResponse]:
        return list(reversed(self._alerts[-limit:]))

    def get_link_ids(self) -> List[str]:
        return [lid for lid in self._links.keys() if "→" in lid]

    def push_session_qber(self, qber: float):
        """Push a session QBER to a random link on the active route (for demo)."""
        route = self.get_active_route()
        if len(route) >= 2:
            i = random.randint(0, len(route) - 2)
            link_id = f"{route[i]}→{route[i+1]}"
            self.update_link_qber(link_id, qber)
