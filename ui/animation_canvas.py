"""
AnimationCanvas
===============
A QGraphicsView / QGraphicsScene that shows:
  - Alice node (left)
  - Bob node (right)
  - Optional Eve node (centre, shown in red when active)
  - Quantum channel line
  - Animated photon particles flying left-to-right
  - Annotations showing basis, bit, and measurement result

Key design decisions
--------------------
* ALL scene-item Python references are nulled before scene.clear() is called
  to prevent 'wrapped C/C++ object has been deleted' RuntimeErrors.
* resizeEvent only rebuilds the scene when no animation is running; otherwise
  it simply rescales the view to fit the existing scene.
* photon_done signal is emitted after each photon animation completes so the
  main window can dispatch the next event in a fully sequential manner.
"""
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsTextItem, QGraphicsLineItem, QSizePolicy,
)

from controller.simulation_controller import PhotonEvent


# ── Geometry constants ──────────────────────────────────────────────────
_NODE_W   = 90
_NODE_H   = 56
_PHOTON_R = 10
_ANIM_FPS = 60
_ANIM_MS  = 1000 // _ANIM_FPS

# ── Node colours ────────────────────────────────────────────────────────
_ALICE_COL = "#2980b9"
_BOB_COL   = "#27ae60"
_EVE_COL   = "#c0392b"


class _NodeItem(QGraphicsItem):
    """A rounded-rectangle node with a label."""

    def __init__(self, label: str, colour: str, width: int = _NODE_W, height: int = _NODE_H):
        super().__init__()
        self._label  = label
        self._colour = QColor(colour)
        self._w = width
        self._h = height

    def boundingRect(self) -> QRectF:
        return QRectF(-self._w / 2, -self._h / 2, self._w, self._h)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()

        grad = QRadialGradient(0, 0, self._w * 0.7)
        grad.setColorAt(0.0, self._colour.lighter(155))
        grad.setColorAt(1.0, self._colour.darker(130))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(self._colour.lighter(180), 1.5))
        painter.drawRoundedRect(rect, 10, 10)

        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._label)


class _PhotonItem(QGraphicsItem):
    """Animated photon circle."""

    def __init__(self, colour: str, symbol: str, radius: int = _PHOTON_R):
        super().__init__()
        self._colour   = QColor(colour)
        self._symbol   = symbol
        self._r        = radius
        self._opacity  = 1.0
        self._alive    = True   # set False before scene.clear() to suppress stale access

    def boundingRect(self) -> QRectF:
        return QRectF(-self._r, -self._r, self._r * 2, self._r * 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        if not self._alive:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        grad = QRadialGradient(0, 0, self._r)
        grad.setColorAt(0.0, self._colour.lighter(180))
        grad.setColorAt(0.5, self._colour)
        grad.setColorAt(1.0, self._colour.darker(160))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(self._colour.lighter(210), 1.5))
        painter.drawEllipse(self.boundingRect())

        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, self._symbol)

    def set_opacity(self, v: float) -> None:
        self._opacity = max(0.0, min(1.0, v))
        self.update()


class AnimationCanvas(QGraphicsView):
    """Main animation canvas widget."""

    # Emitted when a photon animation finishes — MainWindow uses this
    # to dispatch the next photon in a fully sequential, non-overlapping way.
    photon_done = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#050508")))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Scene node references — MUST be set None before every scene.clear()
        self._alice_node:   Optional[_NodeItem]        = None
        self._bob_node:     Optional[_NodeItem]        = None
        self._eve_node:     Optional[_NodeItem]        = None
        self._channel_line: Optional[QGraphicsLineItem] = None
        self._ann_alice:    Optional[QGraphicsTextItem] = None
        self._ann_eve:      Optional[QGraphicsTextItem] = None
        self._ann_bob:      Optional[QGraphicsTextItem] = None
        self._ann_status:   Optional[QGraphicsTextItem] = None

        # Photon item — separate from the static scene nodes
        self._photon_item: Optional[_PhotonItem] = None

        # Animation timer
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(_ANIM_MS)
        self._anim_timer.timeout.connect(self._tick)

        # Animation state
        self._dst_x:           float = 0.0
        self._cur_x:           float = 0.0
        self._chan_y:           float = 0.0
        self._speed:           float = 10.0   # pixels per tick at 1x
        self._base_speed:      float = 10.0   # reference, scaled by multiplier
        self._eve_active:      bool  = False
        self._at_eve:          bool  = False
        self._eve_pause_ticks: int   = 0
        self._current_event:   Optional[PhotonEvent] = None

        # Geometry cache — set by _build_scene()
        self._alice_x: float = 0.0
        self._bob_x:   float = 0.0
        self._eve_x:   float = 0.0

        self._build_scene()

    # ------------------------------------------------------------------ #
    #  Scene construction                                                  #
    # ------------------------------------------------------------------ #
    def _clear_scene_refs(self) -> None:
        """
        Mark all Python-held scene-item references as dead and null them.
        MUST be called before every self._scene.clear() call.
        """
        for ref_name in (
            '_alice_node', '_bob_node', '_eve_node',
            '_channel_line',
            '_ann_alice', '_ann_eve', '_ann_bob', '_ann_status',
        ):
            obj = getattr(self, ref_name, None)
            if obj is not None:
                setattr(self, ref_name, None)

        # The photon item is separate — mark alive=False so paint() becomes a no-op
        if self._photon_item is not None:
            try:
                self._photon_item._alive = False
            except RuntimeError:
                pass
            self._photon_item = None

    def _build_scene(self) -> None:
        """Rebuild the static scene from scratch."""
        # 1. Stop animation first
        self._anim_timer.stop()
        # 2. Null all Python refs so clear() cannot leave dangling pointers
        self._clear_scene_refs()
        # 3. Safe to clear
        self._scene.clear()

        w = max(self.width(),  640)
        h = max(self.height(), 220)
        self._scene.setSceneRect(0, 0, w, h)

        cy = h / 2
        alice_x = 90
        bob_x   = w - 90
        eve_x   = w / 2
        margin  = _NODE_W // 2 + 4

        # Channel line
        pen = QPen(QColor("#1e3a5f"), 2, Qt.PenStyle.DashLine)
        self._channel_line = self._scene.addLine(alice_x, cy, bob_x, cy, pen)

        # Nodes
        self._alice_node = _NodeItem("ALICE", _ALICE_COL)
        self._alice_node.setPos(alice_x, cy)
        self._scene.addItem(self._alice_node)

        self._bob_node = _NodeItem("BOB", _BOB_COL)
        self._bob_node.setPos(bob_x, cy)
        self._scene.addItem(self._bob_node)

        self._eve_node = _NodeItem("EVE", _EVE_COL)
        self._eve_node.setPos(eve_x, cy)
        self._eve_node.setVisible(False)
        self._scene.addItem(self._eve_node)

        # Annotations
        self._ann_alice  = self._make_ann(alice_x,  cy + 44)
        self._ann_eve    = self._make_ann(eve_x,    cy + 44)
        self._ann_bob    = self._make_ann(bob_x,    cy + 44)
        self._ann_status = self._make_ann(w / 2,    22, size=11, colour="#74b9ff")

        # Cache geometry
        self._alice_x = alice_x
        self._bob_x   = bob_x
        self._eve_x   = eve_x
        self._chan_y  = cy

    def _make_ann(self, x: float, y: float, size: int = 10,
                  colour: str = "#7f8c8d") -> QGraphicsTextItem:
        item = QGraphicsTextItem("")
        item.setDefaultTextColor(QColor(colour))
        item.setFont(QFont("Consolas", size))
        item.setPos(x - 60, y)
        item.setTextWidth(130)
        self._scene.addItem(item)
        return item

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def set_anim_speed(self, multiplier: float) -> None:
        """Scale photon pixels-per-tick so visual speed matches the speed label."""
        self._speed = max(1.0, self._base_speed * multiplier)

    def set_eve_active(self, active: bool) -> None:
        self._eve_active = active
        if self._eve_node is not None:
            try:
                self._eve_node.setVisible(active)
            except RuntimeError:
                pass
        if self._channel_line is not None:
            try:
                colour = "#7b241c" if active else "#1e3a5f"
                self._channel_line.setPen(QPen(QColor(colour), 2, Qt.PenStyle.DashLine))
            except RuntimeError:
                pass

    def launch_photon(self, event: PhotonEvent) -> None:
        """Start animating a photon.  The previous photon is cleanly removed first."""
        self._anim_timer.stop()
        self._remove_photon_item()

        self._current_event = event

        # Update alice annotation
        self._safe_set_text(
            self._ann_alice,
            f"bit={event.alice_bit}  basis={event.alice_basis}\n{event.alice_symbol}"
        )
        self._safe_set_text(self._ann_eve, "")
        self._safe_set_text(self._ann_bob, "")

        if event.lost:
            self._safe_set_text(
                self._ann_status,
                f"[{event.index+1}/{event.total}]  photon lost in channel",
                colour="#7f8c8d",
            )
            # Emit done immediately so the queue keeps moving
            self.photon_done.emit()
            return

        status = (
            f"[{event.index+1}/{event.total}]  "
            f"{'Eve intercepting' if event.eve_active else 'photon in flight'}"
        )
        self._safe_set_text(self._ann_status, status, colour="#74b9ff")
        self._centre_status()

        # Create photon item and add to scene
        self._photon_item = _PhotonItem(event.alice_colour, event.alice_symbol)
        self._photon_item.setPos(self._alice_x + _NODE_W / 2, self._chan_y)
        self._scene.addItem(self._photon_item)

        self._cur_x         = self._alice_x + _NODE_W / 2
        self._dst_x         = self._eve_x if self._eve_active else self._bob_x - _NODE_W / 2
        self._at_eve        = False
        self._eve_pause_ticks = 0

        self._anim_timer.start()

    def reset(self) -> None:
        """Full reset: stop animation and rebuild scene."""
        # _build_scene() stops the timer and clears refs internally
        self._build_scene()
        if self._eve_active:
            self.set_eve_active(True)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    def _remove_photon_item(self) -> None:
        """Safely remove the current photon item from the scene."""
        if self._photon_item is None:
            return
        try:
            self._photon_item._alive = False
            self._scene.removeItem(self._photon_item)
        except RuntimeError:
            pass
        self._photon_item = None

    def _safe_set_text(self, item: Optional[QGraphicsTextItem],
                       text: str, colour: Optional[str] = None) -> None:
        if item is None:
            return
        try:
            if colour:
                item.setDefaultTextColor(QColor(colour))
            item.setPlainText(text)
        except RuntimeError:
            pass

    def _centre_status(self) -> None:
        if self._ann_status is None:
            return
        try:
            self._ann_status.setPos(
                (self._scene.width() - 130) / 2, 14
            )
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ #
    #  Animation tick                                                      #
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        # Guard: if item was deleted externally, bail out cleanly
        if self._photon_item is None:
            self._anim_timer.stop()
            return

        try:
            self._tick_inner()
        except RuntimeError:
            # C++ object was deleted (e.g. scene rebuilt during animation)
            self._anim_timer.stop()
            self._photon_item = None

    def _tick_inner(self) -> None:
        event = self._current_event
        if event is None:
            self._anim_timer.stop()
            return

        if self._at_eve:
            self._eve_pause_ticks += 1
            if self._eve_pause_ticks >= 14:
                self._at_eve = False
                self._dst_x  = self._bob_x - _NODE_W / 2
                # Re-encode photon with Eve's re-emitted state
                if event.eve_bit is not None:
                    from simulation.qubit import Qubit, POLARIZATION_COLOURS, POLARIZATION_SYMBOLS
                    eve_pol = Qubit._compute_polarization(
                        event.eve_bit, event.eve_basis or '+'
                    )
                    self._photon_item._colour = QColor(
                        POLARIZATION_COLOURS.get(eve_pol, "#ffffff")
                    )
                    self._photon_item._symbol = POLARIZATION_SYMBOLS.get(eve_pol, "?")
                    self._photon_item.update()
                self._safe_set_text(
                    self._ann_eve,
                    f"basis={event.eve_basis}  bit={event.eve_bit}",
                    colour="#e17055",
                )
            return

        # Move photon
        step = min(self._speed, abs(self._dst_x - self._cur_x))
        self._cur_x += step
        self._photon_item.setPos(self._cur_x, self._chan_y)

        # Check arrival
        if self._cur_x >= self._dst_x - 1:
            if self._eve_active and not self._at_eve and self._dst_x == self._eve_x:
                self._at_eve = True
                self._eve_pause_ticks = 0
                self._safe_set_text(self._ann_eve, "intercepting...", colour="#e17055")
            else:
                self._anim_timer.stop()
                self._on_arrived_at_bob(event)

    def _on_arrived_at_bob(self, event: PhotonEvent) -> None:
        if event.bob_bit is not None:
            match_tag = "match" if event.bases_match else "mismatch"
            self._safe_set_text(
                self._ann_bob,
                f"basis={event.bob_basis}  bit={event.bob_bit}  [{match_tag}]",
                colour="#55efc4" if event.bases_match else "#fdcb6e",
            )
        qber_pct = event.rolling_qber * 100
        colour = "#00b894" if qber_pct < 10 else ("#fdcb6e" if qber_pct < 20 else "#d63031")
        self._safe_set_text(
            self._ann_status,
            f"[{event.index+1}/{event.total}]   QBER {qber_pct:.1f}%   sifted={event.sifted_count}",
            colour=colour,
        )
        self._centre_status()
        # Fade the photon so it does not linger visually
        if self._photon_item is not None:
            try:
                self._photon_item.set_opacity(0.25)
            except RuntimeError:
                pass
        # Signal the main window that this photon is done
        self.photon_done.emit()

    # ------------------------------------------------------------------ #
    #  Resize                                                              #
    # ------------------------------------------------------------------ #
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._anim_timer.isActive():
            # Simulation running — just rescale the view, don't destroy the scene
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)
        else:
            self._build_scene()
            if self._eve_active:
                self.set_eve_active(True)
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)
