"""
network_dashboard.py
=====================
Dynamic QBER Monitoring + SDN Network Topology Dashboard.

Panels:
  1. Network Topology Map   – live node/link graph with QBER colours
  2. Link QBER Monitor      – per-link QBER bars and status badges
  3. Attack Detection Alerts – scrolling alert feed
  4. Active Route Display    – current best A→B path highlight
  5. Attack Injection Controls – inject/clear attacks per link

Cross-layer integration: QBER changes from the quantum layer automatically
update node colours and trigger rerouting via the SDN controller.
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QLinearGradient,
    QPainterPath, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QScrollArea, QGroupBox, QSizePolicy, QComboBox,
    QProgressBar, QSplitter, QListWidget, QListWidgetItem,
    QSpinBox, QTabWidget, QAbstractItemView,
)

from controller.sdn_controller import SDNController, QuantumNode, QuantumLink, RouteAlert


# ──────────────────────────────────────────────────────────────────────── #
#  Topology Canvas                                                          #
# ──────────────────────────────────────────────────────────────────────── #

class _TopologyCanvas(QWidget):
    """
    Custom widget that draws the quantum network topology.
    Nodes are coloured by health status; links by QBER level.
    The active route is highlighted in bright cyan.
    """

    _NODE_R   = 22
    _FONT_SZ  = 9

    # Status colours
    _SAFE_LINK     = QColor(0,  184, 148, 180)   # green
    _WARN_LINK     = QColor(253, 203, 110, 200)  # amber
    _CRIT_LINK     = QColor(214, 48,  49, 220)   # red
    _INACTIVE_LINK = QColor(60,  60,  80, 80)

    _SAFE_NODE     = QColor(0,  184, 148)
    _CRIT_NODE     = QColor(214, 48,  49)
    _RELAY_NODE    = QColor(99,  110, 200)
    _ACTIVE_ROUTE  = QColor(116, 185, 255, 240)  # cyan route highlight

    def __init__(self, sdn: SDNController, parent=None):
        super().__init__(parent)
        self._sdn = sdn
        self._active_path: List[str] = []
        self.setMinimumSize(340, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")

        # Pre-create fonts to avoid QFont::setPointSize(-1) warnings
        self._font_link = QFont("Segoe UI")
        self._font_link.setPixelSize(11)
        self._font_node = QFont("Segoe UI")
        self._font_node.setPixelSize(12)
        self._font_node.setWeight(QFont.Weight.Bold)

        # Blink timer for compromised nodes
        self._blink = False
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._on_blink)
        self._blink_timer.start()

    def set_active_path(self, path: List[str]) -> None:
        self._active_path = path
        self.update()

    def _on_blink(self) -> None:
        self._blink = not self._blink
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()

        def node_pos(node: QuantumNode) -> QPointF:
            margin = self._NODE_R + 12
            return QPointF(
                margin + node.x * (W - 2 * margin),
                margin + node.y * (H - 2 * margin),
            )

        nodes = {n.node_id: n for n in self._sdn.get_nodes()}
        positions = {nid: node_pos(n) for nid, n in nodes.items()}

        # Draw edges
        for lk in self._sdn.get_links():
            if lk.src not in positions or lk.dst not in positions:
                continue
            # Only draw each undirected pair once
            if lk.src > lk.dst:
                continue

            p1 = positions[lk.src]
            p2 = positions[lk.dst]
            in_route = (
                lk.src in self._active_path and lk.dst in self._active_path and
                abs(self._active_path.index(lk.src) - self._active_path.index(lk.dst)) == 1
            )
            if in_route:
                color = self._ACTIVE_ROUTE
                width = 3.5
            elif lk.compromised:
                color = self._CRIT_LINK
                width = 2.5
            elif lk.qber >= 0.11:
                color = self._WARN_LINK
                width = 2.0
            else:
                color = self._SAFE_LINK
                width = 1.5

            pen = QPen(color, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(p1, p2)

            # QBER label at midpoint
            mx = (p1.x() + p2.x()) / 2
            my = (p1.y() + p2.y()) / 2
            p.setPen(QPen(color.lighter(130), 1))
            p.setFont(self._font_link)
            p.drawText(QRectF(mx - 20, my - 8, 40, 14),
                       Qt.AlignmentFlag.AlignCenter,
                       f"{lk.qber*100:.0f}%")

        # Draw nodes
        for nid, node in nodes.items():
            pos = positions[nid]
            r   = self._NODE_R

            if node.role == "alice":
                base_color = QColor(116, 185, 255)
            elif node.role == "bob":
                base_color = QColor(0, 184, 148)
            elif node.compromised:
                base_color = self._CRIT_NODE if not self._blink else QColor(255, 100, 100)
            else:
                base_color = self._RELAY_NODE

            # Glow for active route nodes
            if nid in self._active_path:
                glow = QRadialGradient(pos, r * 1.6)
                glow.setColorAt(0.0, base_color.lighter(140))
                glow.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(pos, r * 1.6, r * 1.6)

            # Node circle
            p.setBrush(QBrush(base_color))
            border_col = QColor(255, 60, 60) if node.compromised else base_color.lighter(160)
            p.setPen(QPen(border_col, 1.5))
            p.drawEllipse(pos, r, r)

            # Node label
            p.setPen(QPen(QColor(230, 234, 246), 1))
            p.setFont(self._font_node)
            p.drawText(
                QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r),
                Qt.AlignmentFlag.AlignCenter,
                node.label,
            )

        p.end()


# ──────────────────────────────────────────────────────────────────────── #
#  Per-link QBER bar row                                                    #
# ──────────────────────────────────────────────────────────────────────── #

class _LinkRow(QWidget):
    def __init__(self, link_id: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.link_id = link_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self._lbl_id = QLabel(link_id)
        self._lbl_id.setFixedWidth(90)
        self._lbl_id.setStyleSheet("color: #90caf9; font-size: 11px; background: transparent;")

        self._bar = QProgressBar()
        self._bar.setRange(0, 40)
        self._bar.setValue(0)
        self._bar.setFixedHeight(14)
        self._bar.setFormat("")
        self._bar.setStyleSheet(
            "QProgressBar { background: rgba(20,20,40,180); border-radius: 5px; border: none; }"
            "QProgressBar::chunk { background: #00b894; border-radius: 5px; }"
        )

        self._lbl_val = QLabel("0.0%")
        self._lbl_val.setFixedWidth(48)
        self._lbl_val.setStyleSheet("color: #00b894; font-size: 11px; font-weight: bold; background: transparent;")

        self._badge = QLabel("SAFE")
        self._badge.setFixedWidth(60)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            "background: rgba(0,184,148,60); color: #00b894; font-size: 9px;"
            " font-weight: bold; border-radius: 3px; padding: 1px 3px;"
        )

        layout.addWidget(self._lbl_id)
        layout.addWidget(self._bar, stretch=1)
        layout.addWidget(self._lbl_val)
        layout.addWidget(self._badge)

    def set_qber(self, qber: float, status: str) -> None:
        pct = int(qber * 100)
        self._bar.setValue(min(pct, 40))
        self._lbl_val.setText(f"{qber*100:.1f}%")

        if status == "safe":
            color = "#00b894"
            badge_bg = "rgba(0,184,148,60)"
            badge_txt = "SAFE"
            chunk_style = "#00b894"
        elif status == "warning":
            color = "#fdcb6e"
            badge_bg = "rgba(253,203,110,60)"
            badge_txt = "WARN"
            chunk_style = "#fdcb6e"
        else:
            color = "#d63031"
            badge_bg = "rgba(214,48,49,60)"
            badge_txt = "CRIT"
            chunk_style = "#d63031"

        self._lbl_val.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self._badge.setText(badge_txt)
        self._badge.setStyleSheet(
            f"background: {badge_bg}; color: {color}; font-size: 9px;"
            " font-weight: bold; border-radius: 3px; padding: 1px 3px;"
        )
        self._bar.setStyleSheet(
            "QProgressBar { background: rgba(20,20,40,180); border-radius: 5px; border: none; }"
            f"QProgressBar::chunk {{ background: {chunk_style}; border-radius: 5px; }}"
        )


# ──────────────────────────────────────────────────────────────────────── #
#  Network Dashboard                                                        #
# ──────────────────────────────────────────────────────────────────────── #

class NetworkDashboard(QFrame):
    """
    The full network monitoring and attack management panel.
    """
    # Emitted whenever the poisoning/attack state changes.
    # True  → at least one link is now under attack  (Eve should be active in BB84)
    # False → all links are clear                    (Eve should be off)
    poisoning_changed = pyqtSignal(bool)

    def __init__(self, sdn: Optional[SDNController] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("networkDashboard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._sdn: SDNController = sdn or SDNController()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("SDN-QKD Network Dashboard")
        title.setStyleSheet(
            "color: #90caf9; font-size: 14px; font-weight: bold; background: transparent;"
        )
        self._btn_net_reset = QPushButton("↺  Reset Network")
        self._btn_net_reset.setFixedWidth(130)
        self._btn_net_reset.setToolTip("Reset all links, clear alerts and restore default topology")
        self._btn_net_reset.setStyleSheet(
            "QPushButton { background: rgba(74,114,196,60); color: #74b9ff;"
            " border: 1px solid rgba(74,114,196,130); border-radius: 6px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background: rgba(74,114,196,120); }"
        )
        self._btn_net_reset.clicked.connect(self._reset_network)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self._btn_net_reset)
        root.addLayout(title_row)

        # Top row: topology + link monitor
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._topology_canvas = _TopologyCanvas(self._sdn)
        top_splitter.addWidget(self._wrap_group("Network Topology", self._topology_canvas))

        link_monitor = self._build_link_monitor()
        top_splitter.addWidget(self._wrap_group("Per-Link QBER Monitor", link_monitor))
        top_splitter.setSizes([360, 300])
        root.addWidget(top_splitter, stretch=3)

        # Bottom row: alerts + attack controls
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(self._build_alerts_panel())
        bottom_splitter.addWidget(self._build_attack_controls())
        bottom_splitter.setSizes([360, 300])
        root.addWidget(bottom_splitter, stretch=2)

        # Connect SDN signals
        self._sdn.link_updated.connect(self._on_link_updated)
        self._sdn.alert_raised.connect(self._on_alert)
        self._sdn.route_changed.connect(self._on_route_changed)
        self._sdn.node_compromised.connect(self._on_node_compromised)
        self._sdn.network_reset.connect(self._on_reset)

        # Initial paint
        self._populate_link_rows()
        route = self._sdn.get_active_route("A", "B")
        self._topology_canvas.set_active_path(route)
        self._update_poison_status()

    # ------------------------------------------------------------------ #
    #  UI builders                                                         #
    # ------------------------------------------------------------------ #

    def _wrap_group(self, title: str, widget: QWidget) -> QGroupBox:
        grp = QGroupBox(title)
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.addWidget(widget)
        return grp

    def _build_link_monitor(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._link_rows: Dict[str, _LinkRow] = {}

        self._link_container = QWidget()
        self._link_container.setStyleSheet("background: transparent;")
        self._link_layout = QVBoxLayout(self._link_container)
        self._link_layout.setContentsMargins(0, 0, 0, 0)
        self._link_layout.setSpacing(2)

        scroll = QScrollArea()
        scroll.setWidget(self._link_container)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(240)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: rgba(20,20,40,150); width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: rgba(80,100,220,180); border-radius: 3px; }"
        )

        # Health summary
        health_row = QHBoxLayout()
        self._health_lbl = QLabel("Network healthy")
        self._health_lbl.setStyleSheet("color: #00b894; font-size: 11px; background: transparent;")
        health_row.addWidget(self._health_lbl)
        health_row.addStretch()

        layout.addLayout(health_row)
        layout.addWidget(scroll)
        return container

    def _build_alerts_panel(self) -> QGroupBox:
        grp = QGroupBox("Attack Detection Alerts")

        layout = QVBoxLayout(grp)
        layout.setContentsMargins(4, 6, 4, 4)

        btn_row = QHBoxLayout()
        self._btn_clear_alerts = QPushButton("Clear")
        self._btn_clear_alerts.setFixedWidth(60)
        self._btn_clear_alerts.clicked.connect(self._clear_alerts)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_clear_alerts)
        layout.addLayout(btn_row)

        self._alert_container = QWidget()
        self._alert_container.setStyleSheet("background: transparent;")
        self._alert_layout = QVBoxLayout(self._alert_container)
        self._alert_layout.setContentsMargins(2, 2, 2, 2)
        self._alert_layout.setSpacing(3)
        self._alert_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._alert_container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: rgba(20,20,40,150); width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: rgba(80,100,220,180); border-radius: 3px; }"
        )
        self._alert_scroll = scroll
        layout.addWidget(scroll)

        self._alert_widgets: List[QWidget] = []
        return grp

    # ── shared stylesheet snippet ────────────────────────────────────── #
    _COMBO_SS = (
        "QComboBox { background: rgba(20,20,50,200); color: #e8eaf6;"
        " border: 1px solid rgba(80,100,220,100); border-radius: 5px; padding: 3px 6px; }"
        "QComboBox::drop-down { border: none; }"
        "QComboBox QAbstractItemView { background: #0e0e1a; color: #e8eaf6;"
        " selection-background-color: rgba(80,100,220,120); }"
    )
    _BTN_RED = (
        "QPushButton { background: rgba(214,48,49,80); color: #ff7675;"
        " border: 1px solid rgba(214,48,49,150); border-radius: 6px; padding: 5px 10px; font-size: 11px;}"
        "QPushButton:hover { background: rgba(214,48,49,140); }"
    )
    _BTN_GREEN = (
        "QPushButton { background: rgba(0,184,148,50); color: #00b894;"
        " border: 1px solid rgba(0,184,148,120); border-radius: 6px; padding: 5px 10px; font-size: 11px;}"
        "QPushButton:hover { background: rgba(0,184,148,100); }"
    )
    _BTN_BLUE = (
        "QPushButton { background: rgba(74,114,196,80); color: #74b9ff;"
        " border: 1px solid rgba(74,114,196,150); border-radius: 6px; padding: 5px 10px; font-size: 11px;}"
        "QPushButton:hover { background: rgba(74,114,196,140); }"
    )

    def _build_attack_controls(self) -> QWidget:
        """Returns a QTabWidget with Single-Attack and Route-Poisoning tabs."""
        self._route_lbl = QLabel("Route: ?")
        self._route_lbl.setStyleSheet(
            "color: #74b9ff; font-size: 11px; background: transparent;"
        )
        self._route_lbl.setWordWrap(True)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid rgba(80,100,220,60);"
            " border-radius: 4px; background: rgba(10,10,28,180); }"
            "QTabBar::tab { background: rgba(14,14,26,200); color: #90caf9;"
            " padding: 5px 10px; border-radius: 3px; margin-right: 2px;"
            " font-size: 11px;}"
            "QTabBar::tab:selected { background: rgba(40,50,140,200); color: #e8eaf6; }"
            "QTabBar::tab:hover   { background: rgba(30,30,80,220); }"
        )
        tabs.addTab(self._build_single_attack_tab(), "Single Attack")
        tabs.addTab(self._build_route_poisoning_tab(), "Route Poisoning")
        return tabs

    def _build_single_attack_tab(self) -> QWidget:
        """Original single-link attack controls."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        # Link selector
        link_row = QHBoxLayout()
        link_row.addWidget(QLabel("Target Link:"))
        self._combo_link = QComboBox()
        self._combo_link.setStyleSheet(self._COMBO_SS)
        link_row.addWidget(self._combo_link, stretch=1)
        layout.addLayout(link_row)

        # Attack type
        atk_row = QHBoxLayout()
        atk_row.addWidget(QLabel("Attack Type:"))
        self._combo_attack = QComboBox()
        self._combo_attack.addItems([
            "Intercept-Resend",
            "Photon Number Splitting",
            "Trojan Horse",
        ])
        self._combo_attack.setStyleSheet(self._COMBO_SS)
        atk_row.addWidget(self._combo_attack, stretch=1)
        layout.addLayout(atk_row)

        # Description
        self._atk_desc = QLabel("")
        self._atk_desc.setWordWrap(True)
        self._atk_desc.setStyleSheet(
            "color: #7986cb; font-size: 10px; background: transparent; padding: 2px;"
        )
        self._combo_attack.currentIndexChanged.connect(self._update_atk_desc)
        self._update_atk_desc(0)
        layout.addWidget(self._atk_desc)

        # Inject / Clear
        btn_row = QHBoxLayout()
        self._btn_inject = QPushButton("⚡ Inject")
        self._btn_inject.clicked.connect(self._inject_attack)
        self._btn_inject.setStyleSheet(self._BTN_RED)
        self._btn_clear = QPushButton("✓ Clear")
        self._btn_clear.clicked.connect(self._clear_attack)
        self._btn_clear.setStyleSheet(self._BTN_GREEN)
        btn_row.addWidget(self._btn_inject)
        btn_row.addWidget(self._btn_clear)
        layout.addLayout(btn_row)

        # Force reroute
        self._btn_reroute = QPushButton("↺ Force Reroute A→B")
        self._btn_reroute.clicked.connect(self._force_reroute)
        self._btn_reroute.setStyleSheet(self._BTN_BLUE)
        layout.addWidget(self._btn_reroute)

        layout.addWidget(self._route_lbl)
        layout.addStretch()
        self._refresh_link_combo()
        return w

    def _build_route_poisoning_tab(self) -> QWidget:
        """
        Route-Poisoning mode: select multiple links to compromise simultaneously.
        The SDN controller auto-reroutes around poisoned links.
        If ALL paths are blocked it still transmits, flagging the high QBER.
        """
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Attack type (shared for all poisoned links)
        atk_row = QHBoxLayout()
        atk_row.addWidget(QLabel("Attack on poisoned links:"))
        self._combo_poison_attack = QComboBox()
        self._combo_poison_attack.addItems([
            "Intercept-Resend  (~25% QBER)",
            "Photon-Number-Splitting  (~3% QBER)",
            "Trojan Horse  (~2% QBER)",
        ])
        self._combo_poison_attack.setStyleSheet(self._COMBO_SS)
        atk_row.addWidget(self._combo_poison_attack, stretch=1)
        layout.addLayout(atk_row)

        # Link checklist
        layout.addWidget(QLabel("Select links to poison:"))
        self._poison_list = QListWidget()
        self._poison_list.setFixedHeight(130)
        self._poison_list.setStyleSheet(
            "QListWidget { background: rgba(10,10,30,180); color: #e8eaf6;"
            " border: 1px solid rgba(80,100,220,80); border-radius: 5px; font-size: 11px; }"
            "QListWidget::item { padding: 3px 6px; }"
            "QListWidget::item:selected { background: rgba(80,100,220,100); }"
            "QListWidget::indicator:unchecked { border: 1px solid #7986cb;"
            " background: transparent; border-radius: 2px; }"
            "QListWidget::indicator:checked { background: #d63031;"
            " border: 1px solid #d63031; border-radius: 2px; }"
        )
        self._poison_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        layout.addWidget(self._poison_list)
        self._populate_poison_list()

        # Poison selected / Clear all
        b1 = QHBoxLayout()
        self._btn_poison_sel = QPushButton("🕺 Poison Selected")
        self._btn_poison_sel.clicked.connect(self._poison_selected)
        self._btn_poison_sel.setStyleSheet(self._BTN_RED)
        self._btn_clear_all = QPushButton("✔ Clear All Attacks")
        self._btn_clear_all.clicked.connect(self._clear_all_attacks)
        self._btn_clear_all.setStyleSheet(self._BTN_GREEN)
        b1.addWidget(self._btn_poison_sel)
        b1.addWidget(self._btn_clear_all)
        layout.addLayout(b1)

        # Random poison row
        rand_row = QHBoxLayout()
        rand_row.addWidget(QLabel("Random poison:"))
        self._spin_rand = QSpinBox()
        self._spin_rand.setRange(1, 8)
        self._spin_rand.setValue(2)
        self._spin_rand.setFixedWidth(52)
        self._spin_rand.setStyleSheet(
            "QSpinBox { background: rgba(20,20,50,200); color: #e8eaf6;"
            " border: 1px solid rgba(80,100,220,100); border-radius: 4px; padding: 2px 4px; }"
        )
        self._btn_rand_poison = QPushButton("🎲 Randomize!")
        self._btn_rand_poison.clicked.connect(self._random_poison)
        self._btn_rand_poison.setStyleSheet(self._BTN_RED)
        rand_row.addWidget(self._spin_rand)
        rand_row.addWidget(QLabel("links"))
        rand_row.addWidget(self._btn_rand_poison)
        rand_row.addStretch()
        layout.addLayout(rand_row)

        # Status panel: safe/all-blocked
        self._poison_status_lbl = QLabel("")
        self._poison_status_lbl.setWordWrap(True)
        self._poison_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poison_status_lbl.setStyleSheet(
            "color: #00b894; font-size: 10px; font-weight: bold;"
            " background: transparent; padding: 3px;"
        )
        layout.addWidget(self._poison_status_lbl)

        layout.addWidget(self._route_lbl)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _populate_link_rows(self) -> None:
        for lk in self._sdn.get_links():
            if lk.src < lk.dst:   # show each pair once
                row = _LinkRow(lk.link_id)
                row.set_qber(lk.qber, lk.qber_status)
                self._link_rows[lk.link_id] = row
                self._link_layout.addWidget(row)
        self._link_layout.addStretch()

    def _refresh_link_combo(self) -> None:
        self._combo_link.clear()
        for lk in self._sdn.get_links():
            if lk.src < lk.dst:
                self._combo_link.addItem(lk.link_id)

    def _update_atk_desc(self, idx: int) -> None:
        descs = [
            "Measures each photon and re-emits. Causes ~25% QBER spike. Detectable.",
            "Splits multi-photon pulses. Near-zero QBER impact. Detected via key-rate drop.",
            "Probes Alice's optical device. Zero QBER impact. Blocked by optical isolators.",
        ]
        self._atk_desc.setText(descs[idx] if idx < len(descs) else "")

    def _inject_attack(self) -> None:
        link_id = self._combo_link.currentText()
        atk_idx = self._combo_attack.currentIndex()
        atk_map = ["intercept_resend", "pns", "trojan_horse"]
        attack  = atk_map[atk_idx] if atk_idx < len(atk_map) else "intercept_resend"
        if link_id:
            self._sdn.simulate_attack_on_link(link_id, attack)
            self.poisoning_changed.emit(True)

    def _clear_attack(self) -> None:
        link_id = self._combo_link.currentText()
        if link_id:
            self._sdn.clear_link_attack(link_id)
            # Emit based on whether any links are still compromised
            still_attacked = self._sdn.network_health()["compromised_links"] > 0
            self.poisoning_changed.emit(still_attacked)

    def _force_reroute(self) -> None:
        self._sdn.force_reroute("A", "B")

    def _populate_poison_list(self) -> None:
        """Fill the checklist with all undirected link IDs."""
        self._poison_list.clear()
        for lid in self._sdn.get_undirected_link_ids():
            item = QListWidgetItem(lid)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            # Mark already-compromised links as pre-checked
            lk = self._sdn.get_link(lid)
            if lk and lk.compromised:
                item.setCheckState(Qt.CheckState.Checked)
            self._poison_list.addItem(item)

    def _get_poison_attack_type(self) -> str:
        idx = self._combo_poison_attack.currentIndex()
        return ["intercept_resend", "pns", "trojan_horse"][max(0, idx)]

    def _poison_selected(self) -> None:
        chosen = []
        for i in range(self._poison_list.count()):
            item = self._poison_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                chosen.append(item.text())
        if chosen:
            self._sdn.poison_links(chosen, self._get_poison_attack_type())
        self._update_poison_status()
        # Notify other tabs: Eve should be active if any links are now attacked
        has_attack = self._sdn.network_health()["compromised_links"] > 0
        self.poisoning_changed.emit(has_attack)

    def _random_poison(self) -> None:
        atk = self._get_poison_attack_type()
        chosen = self._sdn.random_poison(self._spin_rand.value(), atk)
        # Reflect new state in checklist
        for i in range(self._poison_list.count()):
            item = self._poison_list.item(i)
            lk = self._sdn.get_link(item.text())
            item.setCheckState(
                Qt.CheckState.Checked if (lk and lk.compromised)
                else Qt.CheckState.Unchecked
            )
        self._update_poison_status()
        # Random poison always adds attacks
        if chosen:
            self.poisoning_changed.emit(True)

    def _clear_all_attacks(self) -> None:
        self._sdn.clear_all_attacks()
        for i in range(self._poison_list.count()):
            self._poison_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self._update_poison_status()
        self.poisoning_changed.emit(False)

    def _update_poison_status(self) -> None:
        """Refresh the status label below the checklist."""
        health = self._sdn.network_health()
        n_crit = health["compromised_links"]
        if n_crit == 0:
            self._poison_status_lbl.setText("All routes clear.")
            self._poison_status_lbl.setStyleSheet(
                "color: #00b894; font-size: 10px; font-weight: bold;"
                " background: transparent; padding: 3px;"
            )
        elif self._sdn.can_route_safely():
            active = self._sdn.get_active_route("A", "B")
            self._poison_status_lbl.setText(
                f"⚠ {n_crit} link(s) poisoned  —  safe re-route found:\n"
                f"{' → '.join(active)}"
            )
            self._poison_status_lbl.setStyleSheet(
                "color: #fdcb6e; font-size: 10px; font-weight: bold;"
                " background: transparent; padding: 3px;"
            )
        else:
            self._poison_status_lbl.setText(
                "🚨 ALL PATHS COMPROMISED\n"
                "Transmission will continue but QBER will be very high.\n"
                "Eve interception IS detectable."
            )
            self._poison_status_lbl.setStyleSheet(
                "color: #d63031; font-size: 10px; font-weight: bold;"
                " background: rgba(80,10,10,100);"
                " border: 1px solid rgba(214,48,49,120);"
                " border-radius: 4px; padding: 4px;"
            )

    def _clear_alerts(self) -> None:
        for w in self._alert_widgets:
            w.setParent(None)
        self._alert_widgets.clear()
        self._sdn.clear_alerts()

    def _reset_network(self) -> None:
        """Full network reset: restore topology, clear all attacks and alerts."""
        self._clear_alerts()
        self._sdn.reset()   # fires network_reset → _on_reset re-populates rows
        self._route_lbl.setText("Route: ?")
        route = self._sdn.get_active_route("A", "B")
        self._topology_canvas.set_active_path(route)
        self._health_lbl.setText("Network healthy")
        self._health_lbl.setStyleSheet(
            "color: #00b894; font-size: 11px; background: transparent;"
        )
        self._update_poison_status()
        self.poisoning_changed.emit(False)

    # ------------------------------------------------------------------ #
    #  SDN signal slots                                                    #
    # ------------------------------------------------------------------ #

    def _on_link_updated(self, link_id: str, qber: float, status: str) -> None:
        # Forward link — try both directions
        rev_id = "→".join(reversed(link_id.split("→")))
        row = self._link_rows.get(link_id) or self._link_rows.get(rev_id)
        if row:
            row.set_qber(qber, status)

        health = self._sdn.network_health()
        n_crit = health["compromised_links"]
        if n_crit == 0:
            self._health_lbl.setText("Network healthy")
            self._health_lbl.setStyleSheet("color: #00b894; font-size: 11px; background: transparent;")
        else:
            self._health_lbl.setText(f"⚠ {n_crit} compromised link(s)")
            self._health_lbl.setStyleSheet("color: #d63031; font-size: 11px; background: transparent;")

        self._topology_canvas.update()

    def _on_alert(self, alert: RouteAlert) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime(alert.timestamp))
        color = "#d63031" if alert.threshold == "critical" else "#fdcb6e"
        msg = (
            f"[{ts}] {alert.link_id}  QBER={alert.qber*100:.1f}%  "
            f"({alert.threshold.upper()})  "
            f"Attack: {alert.attack_type or 'unknown'}  |  {alert.action_taken}"
        )
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; background: rgba(40,10,10,120);"
            " border: 1px solid rgba(214,48,49,80); border-radius: 4px; padding: 4px;"
        )
        # Insert before the stretch at the bottom
        count = self._alert_layout.count()
        self._alert_layout.insertWidget(count - 1, lbl)
        self._alert_widgets.append(lbl)

        # Auto-scroll
        QTimer.singleShot(30, lambda: self._alert_scroll.verticalScrollBar().setValue(
            self._alert_scroll.verticalScrollBar().maximum()
        ))

    def _on_route_changed(self, src: str, dst: str, path: List[str]) -> None:
        self._topology_canvas.set_active_path(path)
        self._route_lbl.setText(
            f"Route: {' → '.join(path)}" if path else "Route: No path found"
        )

    def _on_node_compromised(self, node_id: str) -> None:
        self._topology_canvas.update()

    def _on_reset(self) -> None:
        for row in list(self._link_rows.values()):
            row.setParent(None)
        self._link_rows.clear()
        self._populate_link_rows()
        self._refresh_link_combo()
        self._populate_poison_list()
        self._update_poison_status()
        self._topology_canvas.update()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def push_session_qber(self, qber: float, link_id: str = "A→R1") -> None:
        """
        Called from outside (e.g. MainWindow) to push the latest session QBER
        onto the primary link — cross-layer integration hook.
        """
        self._sdn.update_link_qber(link_id, qber)

    def get_sdn(self) -> SDNController:
        return self._sdn
