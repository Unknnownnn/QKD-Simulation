"""
MainWindow
==========
The top-level application window.  Wires together:
  - ControlPanel  (left)
  - AnimationCanvas (centre)
  - AnalyticsPanel (right)
  - SimulationController
  - _Snackbar   (animated toast notification)
"""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QLabel, QSizePolicy, QFrame, QPushButton,
)

from controller.simulation_controller import SimulationController, PhotonEvent, SessionSummary
from .control_panel import ControlPanel
from .animation_canvas import AnimationCanvas
from .analytics_panel import AnalyticsPanel
from .styles import DARK_STYLESHEET

# Base ms used by _SpeedRow in control_panel — keep in sync
_SPEED_BASE_MS = 400


# ──────────────────────────────────────────────────────────────────────────── #
#  Snackbar toast widget                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

class _Snackbar(QWidget):
    """
    A floating toast bar that slides up from the bottom of its parent.
    - Click the primary text area  →  callback_show() is called
    - Click the dismiss button     →  hides itself
    Auto-hides after `auto_hide_ms` if non-zero.
    """
    _HEIGHT = 52

    def __init__(self, parent: QWidget, callback_show, auto_hide_ms: int = 0):
        super().__init__(parent)
        self._callback_show = callback_show
        self._auto_hide_ms  = auto_hide_ms

        self.setFixedHeight(self._HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Widget)
        self._opacity: float = 0.0

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 12, 8)
        layout.setSpacing(12)

        self._msg_lbl = QLabel("Session complete")
        self._msg_lbl.setStyleSheet(
            "color: #e8eaf6; font-size: 13px; font-weight: bold; background: transparent;"
        )
        self._msg_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._msg_lbl.mousePressEvent = lambda _e: self._on_show_clicked()

        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet(
            "color: #90caf9; font-size: 11px; background: transparent;"
        )
        self._sub_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sub_lbl.mousePressEvent = lambda _e: self._on_show_clicked()

        self._btn_dismiss = QPushButton("Dismiss")
        self._btn_dismiss.setFixedWidth(72)
        self._btn_dismiss.setStyleSheet(
            "QPushButton { background: transparent; color: #82b1ff;"
            " border: 1px solid rgba(100,140,255,120); border-radius: 5px;"
            " font-size: 11px; padding: 3px 8px; }"
            "QPushButton:hover { background: rgba(80,110,220,80); }"
        )
        self._btn_dismiss.clicked.connect(self.hide_animated)

        layout.addWidget(self._msg_lbl)
        layout.addWidget(self._sub_lbl, stretch=1)
        layout.addWidget(self._btn_dismiss)

        # Slide-up animation
        self._anim = QPropertyAnimation(self, b"snack_opacity", self)
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Slide Y animation
        self._y_anim = QPropertyAnimation(self, b"pos", self)
        self._y_anim.setDuration(320)
        self._y_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Auto-hide timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_animated)

        self.hide()

    # Qt property for opacity fade
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float) -> None:
        self._opacity = v
        self.update()

    snack_opacity = pyqtProperty(float, _get_opacity, _set_opacity)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        p.fillPath(path, QBrush(QColor(22, 22, 42, 230)))
        p.setPen(QColor(80, 110, 230, 90))
        p.drawPath(path)
        p.end()

    def show_animated(self, title: str, subtitle: str = "") -> None:
        self._msg_lbl.setText(title)
        self._sub_lbl.setText(subtitle)
        self._reposition()
        self.show()
        self.raise_()

        # Fade in
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

        # Slide up from just below visible area
        p = self.pos()
        from PyQt6.QtCore import QPoint
        start_y = p.y() + 20
        self._y_anim.stop()
        self._y_anim.setStartValue(QPoint(p.x(), start_y))
        self._y_anim.setEndValue(QPoint(p.x(), p.y()))
        self._y_anim.start()

        if self._auto_hide_ms > 0:
            self._hide_timer.start(self._auto_hide_ms)

    def hide_animated(self) -> None:
        self._hide_timer.stop()
        self._anim.stop()
        self._anim.setStartValue(self._opacity)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._on_fade_done)
        self._anim.start()

    def _on_fade_done(self) -> None:
        try:
            self._anim.finished.disconnect(self._on_fade_done)
        except Exception:
            pass
        if self._opacity < 0.05:
            self.hide()

    def _on_show_clicked(self) -> None:
        self.hide_animated()
        self._callback_show()

    def _reposition(self) -> None:
        if self.parent() is None:
            return
        pw = self.parent().width()
        ph = self.parent().height()
        margin = 16
        w = min(540, pw - 2 * margin)
        self.setFixedWidth(w)
        x = (pw - w) // 2
        y = ph - self._HEIGHT - margin
        self.move(x, y)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._reposition()



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QKD Simulation")
        self.resize(1280, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(DARK_STYLESHEET)

        self._controller = SimulationController(self)
        self._photon_queue: list[PhotonEvent] = []
        self._canvas_busy: bool = False
        self._last_summary: SessionSummary | None = None

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        # Title bar
        title = QLabel("Quantum Key Distribution")
        title.setObjectName("labelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._control_panel = ControlPanel()
        self._canvas        = AnimationCanvas()
        self._analytics     = AnalyticsPanel()

        # Centre column: canvas + stage progress
        centre_col = QWidget()
        centre_layout = QVBoxLayout(centre_col)
        centre_layout.setContentsMargins(0, 0, 0, 0)
        centre_layout.setSpacing(4)

        self._stage_label = QLabel("Stage: Idle")
        self._stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stage_label.setStyleSheet(
            "color: #90caf9; font-size: 12px; font-weight: bold;"
        )

        self._progress_label = QLabel("0 / 0")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet("color: #7986cb; font-size: 11px;")

        lbl_row = QHBoxLayout()
        lbl_row.addWidget(self._stage_label)
        lbl_row.addStretch()
        lbl_row.addWidget(self._progress_label)
        centre_layout.addLayout(lbl_row)
        centre_layout.addWidget(self._canvas, stretch=1)

        splitter.addWidget(self._control_panel)
        splitter.addWidget(centre_col)
        splitter.addWidget(self._analytics)
        splitter.setSizes([280, 640, 360])
        self._splitter = splitter

        root.addWidget(splitter, stretch=1)

        # Snackbar — parented to central widget so it floats over everything
        self._snackbar = _Snackbar(central, self._show_analytics_for_snackbar)

        # Status bar
        self.statusBar().setStyleSheet(
            "background-color: rgba(10,10,25,230); color: #7986cb;"
            " border-top: 1px solid rgba(80,100,220,60); font-size: 11px;"
        )
        self.statusBar().showMessage("Ready  —  configure settings and click Run")

    # ------------------------------------------------------------------ #
    #  Signal connections                                                  #
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        cp = self._control_panel
        ctrl = self._controller

        # Control panel → controller settings
        cp.key_length_changed.connect(lambda v: setattr(ctrl, 'key_length', v))
        cp.speed_changed.connect(ctrl.set_speed)
        cp.speed_changed.connect(self._on_speed_changed)
        cp.depol_changed.connect(lambda v: setattr(ctrl, 'noise_depol', v))
        cp.loss_changed.connect(lambda v: setattr(ctrl, 'noise_loss', v))
        cp.eve_toggled.connect(self._on_eve_toggled)
        cp.eve_rate_changed.connect(lambda v: setattr(ctrl, 'eve_intercept_rate', v))

        # Control panel → actions
        cp.run_clicked.connect(self._on_run)
        cp.pause_clicked.connect(self._on_pause)
        cp.step_clicked.connect(self._on_step)
        cp.reset_clicked.connect(self._on_reset)

        # Controller -> UI
        ctrl.photon_processed.connect(self._on_photon_processed)
        ctrl.qber_updated.connect(self._analytics.update_qber)
        ctrl.progress_updated.connect(self._on_progress)
        ctrl.session_complete.connect(self._on_session_complete)
        ctrl.simulation_reset.connect(self._on_reset_ui)
        ctrl.log_message.connect(self._on_log)

        # Canvas signals back when it finishes one photon
        self._canvas.photon_done.connect(self._dispatch_next_photon)

        # Initialise controller with current panel values
        ctrl.key_length        = cp.key_length
        ctrl.speed_ms          = cp.speed_ms
        ctrl.noise_depol       = cp.depol
        ctrl.noise_loss        = cp.loss
        ctrl.eve_active        = cp.eve_active
        ctrl.eve_intercept_rate = cp.eve_rate

    # ------------------------------------------------------------------ #
    #  Control-panel button slots                                          #
    # ------------------------------------------------------------------ #
    def _on_run(self) -> None:
        ctrl = self._controller
        cp   = self._control_panel

        ctrl.key_length         = cp.key_length
        ctrl.speed_ms           = cp.speed_ms
        ctrl.noise_depol        = cp.depol
        ctrl.noise_loss         = cp.loss
        ctrl.eve_active         = cp.eve_active
        ctrl.eve_intercept_rate = cp.eve_rate

        self._photon_queue.clear()
        self._canvas_busy = False
        self._canvas.set_eve_active(cp.eve_active)
        self._snackbar.hide_animated()        # hide any previous toast
        self._stage_label.setText("Stage: Quantum Transmission")
        cp.set_running(True)
        cp.set_stage(1)
        ctrl.start()

    def _on_pause(self) -> None:
        self._controller.pause()
        self._control_panel.set_running(False)
        self._stage_label.setText("Stage: Paused")

    def _on_step(self) -> None:
        self._controller.step_once()

    def _on_reset(self) -> None:
        self._photon_queue.clear()
        self._canvas_busy = False
        self._snackbar.hide_animated()
        self._controller.reset()

    # ------------------------------------------------------------------ #
    #  Controller signal slots                                             #
    # ------------------------------------------------------------------ #
    def _on_speed_changed(self, ms: int) -> None:
        """Translate ms-per-step to a multiplier and send to the canvas."""
        multiplier = _SPEED_BASE_MS / max(ms, 1)
        self._canvas.set_anim_speed(multiplier)

    def _on_eve_toggled(self, active: bool) -> None:
        self._controller.eve_active = active
        self._canvas.set_eve_active(active)

    def _on_photon_processed(self, event: PhotonEvent) -> None:
        """Buffer incoming photon events from the simulation controller."""
        self._photon_queue.append(event)
        # If canvas is idle, kick off the first photon immediately
        if not self._canvas_busy:
            self._dispatch_next_photon()

    def _dispatch_next_photon(self) -> None:
        """
        Pop the next photon and send it to the canvas.
        Called on canvas.photon_done and whenever the queue gets a new item
        while the canvas is idle.
        """
        if not self._photon_queue:
            self._canvas_busy = False
            return
        self._canvas_busy = True
        event = self._photon_queue.pop(0)
        self._canvas.launch_photon(event)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_label.setText(f"{done} / {total}")
        self._analytics.update_stats(raw=done)

        # Stage guess based on progress
        stage = 1
        if done == total:
            stage = 3
        self._control_panel.set_stage(stage)

    def _on_session_complete(self, summary: SessionSummary) -> None:
        # Stop any remaining queued photon animations immediately
        self._photon_queue.clear()
        self._canvas_busy = False
        self._canvas.reset()

        self._last_summary = summary
        self._control_panel.set_running(False)
        self._control_panel.set_stage(5)

        if summary.eve_detected:
            self._stage_label.setText("Eve DETECTED  —  Session ABORTED")
            self._stage_label.setStyleSheet(
                "color: #d63031; font-size: 13px; font-weight: bold;"
            )
            snack_title = "Session aborted  —  Eve detected!"
            snack_sub   = "Click to view statistics"
        else:
            self._stage_label.setText("Secure Key Established")
            self._stage_label.setStyleSheet(
                "color: #00b894; font-size: 13px; font-weight: bold;"
            )
            key_bits = summary.final_key_length
            snack_title = f"Session complete  —  {key_bits} bit key established"
            snack_sub   = "Click to view statistics"

        self._analytics.show_session_summary(summary)
        self._analytics.update_stats(
            raw=summary.raw_count,
            lost=summary.lost_count,
            sifted=summary.sifted_length,
            final=summary.final_key_length,
        )
        eve_status = "Eve detected" if summary.eve_detected else "Secure"
        self.statusBar().showMessage(
            f"Session complete  |  QBER: {summary.qber*100:.1f}%  |  "
            f"Sifted: {summary.sifted_length} bits  |  "
            f"Final key: {summary.final_key_length} bits  |  {eve_status}"
        )

        # Show snackbar over the canvas
        self._snackbar._reposition()
        self._snackbar.show_animated(snack_title, snack_sub)

    def _on_reset_ui(self) -> None:
        self._snackbar.hide_animated()
        self._canvas.reset()
        self._analytics.reset()
        self._stage_label.setText("Stage: Idle")
        self._stage_label.setStyleSheet(
            "color: #90caf9; font-size: 12px; font-weight: bold;"
        )
        self._progress_label.setText("0 / 0")
        self._control_panel.set_stage(-1)
        self.statusBar().showMessage("Ready  —  configure settings and click Run")

    def _show_analytics_for_snackbar(self) -> None:
        """Called when user clicks the snackbar — nothing to do, panel is always visible."""
        pass

    def _on_log(self, message: str) -> None:
        self._analytics.append_log(message)
        self.statusBar().showMessage(message)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if hasattr(self, '_snackbar'):
            self._snackbar._reposition()
