"""
sdn_controller.py
=================
Software-Defined Networking (SDN) controller for the QKD network.

Manages:
  - A graph of virtual quantum nodes and links
  - Per-link QBER monitoring
  - Attack detection based on QBER thresholds
  - Adaptive rerouting to avoid compromised links
  - Cross-layer security integration (quantum layer → routing layer)

The controller exposes PyQt6 signals so the UI dashboard can react in
real time without polling.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QObject, pyqtSignal


# ──────────────────────────────────────────────────────────────────────── #
#  Data structures                                                          #
# ──────────────────────────────────────────────────────────────────────── #

@dataclass
class QuantumLink:
    """A directed quantum channel between two nodes."""
    src: str
    dst: str
    qber: float          = 0.0
    key_rate: float      = 1.0     # relative key rate (0..1)
    compromised: bool    = False
    active: bool         = True
    latency_ms: float    = 5.0
    photon_count: int    = 0
    error_count: int     = 0
    attack_type: str     = "none"  # "none" | attack label

    @property
    def link_id(self) -> str:
        return f"{self.src}→{self.dst}"

    def update_qber(self, new_errors: int, new_photons: int) -> None:
        self.error_count  += new_errors
        self.photon_count += new_photons
        if self.photon_count > 0:
            self.qber = self.error_count / self.photon_count

    @property
    def qber_status(self) -> str:
        if self.qber < 0.11:
            return "safe"
        if self.qber < 0.20:
            return "warning"
        return "critical"


@dataclass
class QuantumNode:
    """A virtual quantum endpoint (router, switch, or end-node)."""
    node_id: str
    label: str
    role: str           = "relay"    # "alice" | "bob" | "relay" | "eve"
    active: bool        = True
    compromised: bool   = False
    x: float            = 0.0        # layout position (normalised 0..1)
    y: float            = 0.0


@dataclass
class RouteAlert:
    """An alert emitted when a link crosses a QBER threshold."""
    timestamp: float
    link_id: str
    qber: float
    previous_qber: float
    threshold: str       # "warning" | "critical"
    action_taken: str    = ""
    attack_type: str     = "none"


# ──────────────────────────────────────────────────────────────────────── #
#  SDN Controller                                                           #
# ──────────────────────────────────────────────────────────────────────── #

class SDNController(QObject):
    """
    Manages the virtual QKD network topology and adaptive security routing.

    Signals
    -------
    link_updated(link_id, qber, status)      – fired whenever a link's QBER changes
    alert_raised(RouteAlert)                  – QBER threshold crossed
    route_changed(src, dst, path)             – active route updated
    node_compromised(node_id)                 – node marked as compromised
    network_reset()                           – topology cleared/reset
    """

    link_updated      = pyqtSignal(str, float, str)   # link_id, qber, status
    alert_raised      = pyqtSignal(object)             # RouteAlert
    route_changed     = pyqtSignal(str, str, list)     # src, dst, path
    node_compromised  = pyqtSignal(str)                # node_id
    network_reset     = pyqtSignal()

    QBER_WARNING_THRESHOLD  = 0.11
    QBER_CRITICAL_THRESHOLD = 0.20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: Dict[str, QuantumNode] = {}
        self._links: Dict[str, QuantumLink] = {}
        self._active_routes: Dict[Tuple[str, str], List[str]] = {}
        self._alerts: List[RouteAlert] = []

        # Build a default 6-node mesh topology
        self._build_default_topology()

    # ------------------------------------------------------------------ #
    #  Topology management                                                 #
    # ------------------------------------------------------------------ #

    def _build_default_topology(self) -> None:
        """Create a default 6-node mesh for demonstration."""
        nodes = [
            QuantumNode("A",  "Alice",   role="alice",  x=0.05, y=0.5),
            QuantumNode("R1", "Relay-1", role="relay",  x=0.30, y=0.2),
            QuantumNode("R2", "Relay-2", role="relay",  x=0.30, y=0.8),
            QuantumNode("R3", "Relay-3", role="relay",  x=0.60, y=0.2),
            QuantumNode("R4", "Relay-4", role="relay",  x=0.60, y=0.8),
            QuantumNode("B",  "Bob",     role="bob",    x=0.95, y=0.5),
        ]
        for n in nodes:
            self._nodes[n.node_id] = n

        edges = [
            ("A",  "R1"), ("A",  "R2"),
            ("R1", "R3"), ("R1", "R4"),
            ("R2", "R3"), ("R2", "R4"),
            ("R3", "B"),  ("R4", "B"),
        ]
        for src, dst in edges:
            lk = QuantumLink(src=src, dst=dst, latency_ms=random.uniform(2, 10))
            self._links[lk.link_id] = lk
            # Also add reverse direction
            lk_rev = QuantumLink(src=dst, dst=src, latency_ms=lk.latency_ms)
            self._links[lk_rev.link_id] = lk_rev

        # Compute initial best route A→B
        self._recompute_route("A", "B")

    def add_node(self, node: QuantumNode) -> None:
        self._nodes[node.node_id] = node

    def add_link(self, link: QuantumLink) -> None:
        self._links[link.link_id] = link

    def get_nodes(self) -> List[QuantumNode]:
        return list(self._nodes.values())

    def get_links(self) -> List[QuantumLink]:
        return list(self._links.values())

    def get_link(self, link_id: str) -> Optional[QuantumLink]:
        return self._links.get(link_id)

    def get_active_route(self, src: str = "A", dst: str = "B") -> List[str]:
        return self._active_routes.get((src, dst), [])

    # ------------------------------------------------------------------ #
    #  QBER update — called by simulation after each session               #
    # ------------------------------------------------------------------ #

    def update_link_qber(
        self,
        link_id: str,
        new_qber: float,
        attack_type: str = "none",
    ) -> None:
        """
        Push a new QBER value onto a link.
        Fires alerts and triggers rerouting if thresholds are crossed.
        """
        lk = self._links.get(link_id)
        if lk is None:
            return

        previous_qber   = lk.qber
        lk.qber         = min(1.0, max(0.0, new_qber))
        lk.attack_type  = attack_type

        if lk.qber >= self.QBER_CRITICAL_THRESHOLD:
            lk.compromised = True
            threshold_str  = "critical"
        elif lk.qber >= self.QBER_WARNING_THRESHOLD:
            threshold_str  = "warning"
        else:
            threshold_str  = "safe"
            lk.compromised = False

        self.link_updated.emit(link_id, lk.qber, lk.qber_status)

        # Emit alert when crossing upward into warning/critical
        if (new_qber >= self.QBER_WARNING_THRESHOLD and
                previous_qber < self.QBER_WARNING_THRESHOLD):
            alert = RouteAlert(
                timestamp     = time.time(),
                link_id       = link_id,
                qber          = new_qber,
                previous_qber = previous_qber,
                threshold     = threshold_str,
                attack_type   = attack_type,
            )
            self._alerts.append(alert)

            # Trigger adaptive rerouting
            new_path = self._recompute_route("A", "B")
            alert.action_taken = (
                f"Rerouted via {' → '.join(new_path)}" if new_path else "No alternate path"
            )
            self.alert_raised.emit(alert)

            # Mark the destination node of the compromised link
            if lk.compromised and lk.dst in self._nodes:
                self._nodes[lk.dst].compromised = True
                self.node_compromised.emit(lk.dst)

    def simulate_attack_on_link(
        self,
        link_id: str,
        attack_type: str = "intercept_resend",
    ) -> None:
        """Inject an attack onto the given link — raises QBER accordingly."""
        qber_map = {
            "intercept_resend": 0.25 + random.uniform(-0.02, 0.02),
            "pns":              0.03 + random.uniform(-0.01, 0.01),   # stealthy
            "trojan_horse":     0.02 + random.uniform(-0.01, 0.01),   # stealthy
        }
        injected_qber = qber_map.get(attack_type, random.uniform(0.12, 0.30))
        self.update_link_qber(link_id, injected_qber, attack_type)

    def clear_link_attack(self, link_id: str) -> None:
        """Remove injected attack from a link and reset QBER."""
        lk = self._links.get(link_id)
        if lk:
            lk.compromised  = False
            lk.attack_type  = "none"
            lk.qber         = random.uniform(0.005, 0.04)
            self.link_updated.emit(link_id, lk.qber, lk.qber_status)

    # ------------------------------------------------------------------ #
    #  Adaptive routing                                                    #
    # ------------------------------------------------------------------ #

    def _recompute_route(self, src: str, dst: str) -> List[str]:
        """
        Dijkstra on the link graph, weighted by QBER.
        Compromised links get an infinite penalty.
        Returns the computed path and fires route_changed.
        """
        import heapq

        INF = float('inf')
        dist: Dict[str, float] = {n: INF for n in self._nodes}
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
                cost = INF if lk.compromised else (lk.qber + lk.latency_ms / 100.0)
                nd   = d + cost
                if nd < dist[lk.dst]:
                    dist[lk.dst] = nd
                    prev[lk.dst] = u
                    heapq.heappush(heap, (nd, lk.dst))

        # Reconstruct path
        path: List[str] = []
        cur = dst
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()

        if path and path[0] == src:
            self._active_routes[(src, dst)] = path
            self.route_changed.emit(src, dst, path)
            return path

        # No path found
        self._active_routes[(src, dst)] = []
        self.route_changed.emit(src, dst, [])
        return []

    def force_reroute(self, src: str = "A", dst: str = "B") -> List[str]:
        """Manually trigger a route recomputation."""
        return self._recompute_route(src, dst)

    # ------------------------------------------------------------------ #
    #  Bulk-attack helpers (Route Poisoning mode)                          #
    # ------------------------------------------------------------------ #

    def poison_links(
        self,
        link_ids: List[str],
        attack_type: str = "intercept_resend",
    ) -> None:
        """Attack every link in *link_ids* simultaneously."""
        for lid in link_ids:
            self.simulate_attack_on_link(lid, attack_type)
        self._recompute_route("A", "B")

    def random_poison(
        self,
        n: int = 2,
        attack_type: str = "intercept_resend",
    ) -> List[str]:
        """
        Randomly choose *n* undirected link pairs and inject an attack on
        each one (both directions).  Returns the list of chosen link IDs.
        """
        candidates = [
            lk.link_id for lk in self._links.values() if lk.src < lk.dst
        ]
        chosen = random.sample(candidates, min(n, len(candidates)))
        for lid in chosen:
            # Poison both directions so Dijkstra sees them as blocked
            self.simulate_attack_on_link(lid, attack_type)
            rev = "→".join(reversed(lid.split("→")))
            if rev in self._links:
                lk_rev = self._links[rev]
                lk_rev.compromised = True
                lk_rev.attack_type = attack_type
                lk_rev.qber        = self._links[lid].qber
                self.link_updated.emit(rev, lk_rev.qber, lk_rev.qber_status)
        self._recompute_route("A", "B")
        return chosen

    def clear_all_attacks(self) -> None:
        """Remove all injected attacks and restore healthy QBER values."""
        for lk in self._links.values():
            if lk.compromised or lk.attack_type != "none":
                lk.compromised = False
                lk.attack_type = "none"
                lk.qber        = random.uniform(0.005, 0.04)
                self.link_updated.emit(lk.link_id, lk.qber, lk.qber_status)
        # Also clear compromised flag from nodes
        for node in self._nodes.values():
            node.compromised = False
        self._recompute_route("A", "B")

    def get_all_simple_paths(
        self, src: str = "A", dst: str = "B", max_depth: int = 10
    ) -> List[List[str]]:
        """DFS enumeration of every simple (cycle-free) path from src to dst."""
        result: List[List[str]] = []

        def dfs(cur: str, path: List[str], visited: Set[str]) -> None:
            if cur == dst:
                result.append(list(path))
                return
            if len(path) >= max_depth:
                return
            for lk in self._links.values():
                if lk.src == cur and lk.dst not in visited:
                    visited.add(lk.dst)
                    path.append(lk.dst)
                    dfs(lk.dst, path, visited)
                    path.pop()
                    visited.discard(lk.dst)

        dfs(src, [src], {src})
        return result

    def can_route_safely(self, src: str = "A", dst: str = "B") -> bool:
        """True if at least one path from src→dst has no compromised links."""
        for path in self.get_all_simple_paths(src, dst):
            if all(
                not (self._links.get(f"{path[i]}→{path[i+1]}") or
                     type("_", (), {"compromised": True})()).compromised
                for i in range(len(path) - 1)
                if (lk := self._links.get(f"{path[i]}→{path[i+1]}")) is not None
            ):
                # Re-check cleanly in one pass
                ok = True
                for i in range(len(path) - 1):
                    lk = self._links.get(f"{path[i]}→{path[i+1]}")
                    if lk and lk.compromised:
                        ok = False
                        break
                if ok:
                    return True
        return False

    def get_undirected_link_ids(self) -> List[str]:
        """Return link IDs for each undirected edge (src < dst)."""
        return [lk.link_id for lk in self._links.values() if lk.src < lk.dst]

    # ------------------------------------------------------------------ #
    #  Analytics helpers                                                   #
    # ------------------------------------------------------------------ #

    def get_alerts(self) -> List[RouteAlert]:
        return list(self._alerts)

    def clear_alerts(self) -> None:
        self._alerts.clear()

    def network_health(self) -> Dict[str, object]:
        """Return a snapshot dict for the dashboard."""
        links = list(self._links.values())
        compromised = [lk for lk in links if lk.compromised]
        safe        = [lk for lk in links if not lk.compromised]
        avg_qber    = (sum(lk.qber for lk in links) / len(links)) if links else 0.0
        return {
            "total_links":       len(links),
            "compromised_links": len(compromised),
            "safe_links":        len(safe),
            "average_qber":      avg_qber,
            "total_alerts":      len(self._alerts),
        }

    def reset(self) -> None:
        self._nodes.clear()
        self._links.clear()
        self._active_routes.clear()
        self._alerts.clear()
        self._build_default_topology()
        self.network_reset.emit()
