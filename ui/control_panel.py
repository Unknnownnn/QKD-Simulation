"""
ControlPanel
============
Floating left-hand settings panel with:
  - Smoothly animated collapsible section cards
  - 0.25x - 2x animation-speed multiplier
  - Eve toggle with eye-candy pulse animation
  - Noise sliders, key-length spinner, stage dots
  - Run / Pause / Step / Reset buttons
"""
from __future__ import annotations

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QPainterPath, QBrush
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QSpinBox, QWidget,
    QSizePolicy, QScrollArea,
)


# ──────────────────────────────────────────────────────────────────────────── #
#  Animated eye-candy Eve toggle                                               #
# ──────────────────────────────────────────────────────────────────────────── #

class _EveToggle(QWidget):
    """
    An animated pill-shaped toggle that pulses red when Eve is active.
    The thumb slides smooth from left (off) to right (on) via
    QPropertyAnimation on a custom '_offset' property.
    """
    toggled = pyqtSignal(bool)

    _DURATION = 260      # ms
    _PULSE_MS  = 40      # ms – glow pulse repaint interval
    _WIDTH  = 52
    _HEIGHT = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked: bool = False
        self._offset: float = 0.0          # 0.0 = off, 1.0 = on
        self._pulse_t: float = 0.0         # 0..2pi for glow cycle

        self.setFixedSize(self._WIDTH, self._HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Slide animation
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(self._DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Glow pulse timer (only ticks when active)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(self._PULSE_MS)
        self._pulse_timer.timeout.connect(self._tick_pulse)

    # --- Qt property so QPropertyAnimation can drive it ---------
    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, v: float) -> None:
        self._offset = v
        self.update()

    offset = pyqtProperty(float, _get_offset, _set_offset)

    def _tick_pulse(self) -> None:
        import math
        self._pulse_t = (self._pulse_t + 0.18) % (2 * math.pi)
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool) -> None:
        if val == self._checked:
            return
        self._checked = val
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if val else 0.0)
        self._anim.start()
        if val:
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()

    def mousePressEvent(self, _event) -> None:
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    def paintEvent(self, _event) -> None:
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self._WIDTH, self._HEIGHT
        r = h / 2

        # Track colour
        if self._checked:
            pulse = 0.5 + 0.5 * math.sin(self._pulse_t)
            red   = int(180 + 20 * pulse)
            alpha = int(180 + 40 * pulse)
            track_col = QColor(red, 30, 50, alpha)
        else:
            track_col = QColor(30, 30, 60, 200)

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)
        p.fillPath(path, QBrush(track_col))

        # Border
        border = QColor(220, 50, 80, 200) if self._checked \
            else QColor(80, 100, 220, 120)
        p.setPen(QPen(border, 1.5))
        p.drawPath(path)

        # Thumb
        margin = 3
        travel = w - h
        thumb_x = margin + self._offset * travel
        thumb_y = margin
        thumb_d = h - 2 * margin

        if self._checked:
            pulse = 0.5 + 0.5 * math.sin(self._pulse_t)
            tr = int(220 + 20 * pulse)
            thumb_col = QColor(tr, 60, 80)
        else:
            thumb_col = QColor(110, 120, 200)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(thumb_col))
        p.drawEllipse(int(thumb_x), int(thumb_y), int(thumb_d), int(thumb_d))
        p.end()


# ──────────────────────────────────────────────────────────────────────────── #
#  Collapsible section card                                                    #
# ──────────────────────────────────────────────────────────────────────────── #

class _CollapsibleSection(QWidget):
    """
    Card widget with a clickable header that smoothly expands / collapses
    its body using a QPropertyAnimation on maximumHeight.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("cardPanel")
        self._title   = title
        self._expanded = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header button
        self._header = QPushButton(f"  {title}  \u25be")
        self._header.setObjectName("sectionHeader")
        self._header.setCheckable(False)
        self._header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._header.clicked.connect(self._toggle)
        outer.addWidget(self._header)

        # Body container
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(10, 6, 10, 10)
        self._body_layout.setSpacing(8)
        outer.addWidget(self._body)

        # Expand / collapse animation on body.maximumHeight
        self._anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def addWidget(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def addLayout(self, layout) -> None:
        self._body_layout.addLayout(layout)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        arrow = "\u25be" if self._expanded else "\u25b8"
        self._header.setText(f"  {self._title}  {arrow}")

        if self._expanded:
            # Reveal: run from 0 to natural height
            self._body.setMaximumHeight(0)
            self._body.show()
            natural = max(self._body.sizeHint().height(), 60)
            self._anim.stop()
            self._anim.setStartValue(0)
            self._anim.setEndValue(natural)
            self._anim.start()
        else:
            # Hide: shrink to zero
            self._anim.stop()
            self._anim.setStartValue(self._body.height())
            self._anim.setEndValue(0)
            self._anim.start()


# ──────────────────────────────────────────────────────────────────────────── #
#  Speed multiplier row (0.25x – 2x)                                          #
# ──────────────────────────────────────────────────────────────────────────── #

class _SpeedRow(QWidget):
    """
    Discrete speed slider mapping 8 positions to speed multipliers
    0.25, 0.33, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0.
    Emits speed_changed(int) with the calculated ms_per_step.
    """
    speed_changed = pyqtSignal(int)

    _STEPS = [
        ("0.25x", 0.25),
        ("0.33x", 0.33),
        ("0.5x",  0.50),
        ("0.75x", 0.75),
        ("1x",    1.00),
        ("1.5x",  1.50),
        ("2x",    2.00),
        ("3x",    3.00),
        ("4x",    4.00),
    ]
    _BASE_MS = 400   # ms at 1.0x  (4x → 100 ms, 0.25x → 1600 ms)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        top = QHBoxLayout()
        lbl = QLabel("Animation Speed")
        lbl.setStyleSheet("color: #90caf9; font-size: 12px;")
        self._val_lbl = QLabel("1x")
        self._val_lbl.setFixedWidth(44)
        self._val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._val_lbl.setStyleSheet(
            "color: #82b1ff; font-weight: bold; font-size: 12px;"
        )
        top.addWidget(lbl)
        top.addStretch()
        top.addWidget(self._val_lbl)
        col.addLayout(top)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(len(self._STEPS) - 1)
        self._slider.setValue(4)   # default = 1x
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.valueChanged.connect(self._on_change)
        col.addWidget(self._slider)

        ends = QHBoxLayout()
        slow_l = QLabel("Slow")
        slow_l.setStyleSheet("color: rgba(150,160,200,140); font-size: 10px;")
        fast_l = QLabel("Fast")
        fast_l.setStyleSheet("color: rgba(150,160,200,140); font-size: 10px;")
        ends.addWidget(slow_l)
        ends.addStretch()
        ends.addWidget(fast_l)
        col.addLayout(ends)

    def _on_change(self, idx: int) -> None:
        label, mult = self._STEPS[idx]
        self._val_lbl.setText(label)
        self.speed_changed.emit(max(50, int(self._BASE_MS / mult)))

    @property
    def speed_ms(self) -> int:
        _, mult = self._STEPS[self._slider.value()]
        return max(50, int(self._BASE_MS / mult))


# ──────────────────────────────────────────────────────────────────────────── #
#  Generic labelled slider                                                     #
# ──────────────────────────────────────────────────────────────────────────── #

class _SliderRow(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, label: str, min_val: float, max_val: float,
                 initial: float, scale: float = 100.0, suffix: str = "%",
                 parent=None):
        super().__init__(parent)
        self._scale  = scale
        self._suffix = suffix
        self.setStyleSheet("background: transparent;")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFixedWidth(114)
        lbl.setStyleSheet("color: #90caf9; font-size: 12px;")

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(int(min_val * scale))
        self._slider.setMaximum(int(max_val * scale))
        self._slider.setValue(int(initial * scale))

        self._val_lbl = QLabel(self._format(initial))
        self._val_lbl.setFixedWidth(46)
        self._val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._val_lbl.setStyleSheet(
            "color: #82b1ff; font-weight: bold; font-size: 12px;"
        )

        self._slider.valueChanged.connect(self._on_change)

        row.addWidget(lbl)
        row.addWidget(self._slider)
        row.addWidget(self._val_lbl)

    def _format(self, v: float) -> str:
        if self._suffix == "%":
            return f"{v*100:.1f}%"
        return f"{v:.3f}"

    def _on_change(self, raw: int) -> None:
        v = raw / self._scale
        self._val_lbl.setText(self._format(v))
        self.valueChanged.emit(v)

    @property
    def value(self) -> float:
        return self._slider.value() / self._scale

    def set_enabled(self, enabled: bool) -> None:
        self._slider.setEnabled(enabled)


# ──────────────────────────────────────────────────────────────────────────── #
#  Main ControlPanel                                                           #
# ──────────────────────────────────────────────────────────────────────────── #

class ControlPanel(QFrame):
    """Floating settings panel with animated collapsible cards."""

    run_clicked   = pyqtSignal()
    pause_clicked = pyqtSignal()
    step_clicked  = pyqtSignal()
    reset_clicked = pyqtSignal()

    key_length_changed  = pyqtSignal(int)
    speed_changed       = pyqtSignal(int)
    depol_changed       = pyqtSignal(float)
    loss_changed        = pyqtSignal(float)
    eve_toggled         = pyqtSignal(bool)
    eve_rate_changed    = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlPanel")
        self.setFixedWidth(285)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 8, 6, 8)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(inner_widget)
        inner.setContentsMargins(2, 2, 2, 2)
        inner.setSpacing(6)

        self._sec_sim   = _CollapsibleSection("Simulation Settings")
        self._build_sim_settings(self._sec_sim)
        inner.addWidget(self._sec_sim)

        self._sec_noise = _CollapsibleSection("Noise Parameters")
        self._build_noise_settings(self._sec_noise)
        inner.addWidget(self._sec_noise)

        self._sec_eve   = _CollapsibleSection("Eavesdropper  (Eve)")
        self._build_eve_settings(self._sec_eve)
        inner.addWidget(self._sec_eve)

        self._sec_ctrl  = _CollapsibleSection("Controls")
        self._build_buttons(self._sec_ctrl)
        inner.addWidget(self._sec_ctrl)

        self._sec_stage = _CollapsibleSection("Protocol Stage")
        self._build_stage_indicator(self._sec_stage)
        inner.addWidget(self._sec_stage)

        inner.addStretch()
        scroll.setWidget(inner_widget)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------ #
    #  Section builders                                                    #
    # ------------------------------------------------------------------ #

    def _build_sim_settings(self, sec: _CollapsibleSection) -> None:
        row = QHBoxLayout()
        lbl = QLabel("Key Length")
        lbl.setStyleSheet("color: #90caf9; font-size: 12px;")
        self._spin_key = QSpinBox()
        self._spin_key.setRange(10, 2000)
        self._spin_key.setValue(100)
        self._spin_key.setSingleStep(10)
        self._spin_key.setSuffix(" qubits")
        self._spin_key.valueChanged.connect(self.key_length_changed)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self._spin_key)
        sec.addLayout(row)

        self._speed_row = _SpeedRow()
        self._speed_row.speed_changed.connect(self.speed_changed)
        sec.addWidget(self._speed_row)

    def _build_noise_settings(self, sec: _CollapsibleSection) -> None:
        self._depol_row = _SliderRow("Depolarization", 0.0, 0.20, 0.02)
        self._depol_row.valueChanged.connect(self.depol_changed)
        sec.addWidget(self._depol_row)

        self._loss_row = _SliderRow("Photon Loss", 0.0, 0.30, 0.05)
        self._loss_row.valueChanged.connect(self.loss_changed)
        sec.addWidget(self._loss_row)

    def _build_eve_settings(self, sec: _CollapsibleSection) -> None:
        # Toggle row
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(10)

        self._eve_lbl = QLabel("Enable Eve")
        self._eve_lbl.setStyleSheet(
            "color: #ef9a9a; font-weight: bold; font-size: 13px;"
        )
        self._eve_toggle = _EveToggle()
        self._eve_toggle.toggled.connect(self._on_eve_toggled)

        self._eve_status_lbl = QLabel("Inactive")
        self._eve_status_lbl.setStyleSheet(
            "color: rgba(150,160,200,160); font-size: 11px; font-style: italic;"
        )

        toggle_row.addWidget(self._eve_lbl)
        toggle_row.addStretch()
        toggle_row.addWidget(self._eve_status_lbl)
        toggle_row.addWidget(self._eve_toggle)
        sec.addLayout(toggle_row)

        # Intercept rate – slides in/out
        self._eve_rate_container = QWidget()
        self._eve_rate_container.setStyleSheet("background: transparent;")
        rc_layout = QVBoxLayout(self._eve_rate_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        self._eve_rate_row = _SliderRow("Intercept Rate", 0.0, 1.0, 1.0)
        self._eve_rate_row.valueChanged.connect(self.eve_rate_changed)
        self._eve_rate_row.set_enabled(False)
        rc_layout.addWidget(self._eve_rate_row)
        self._eve_rate_container.setMaximumHeight(0)
        sec.addWidget(self._eve_rate_container)

        self._eve_rate_anim = QPropertyAnimation(
            self._eve_rate_container, b"maximumHeight", self
        )
        self._eve_rate_anim.setDuration(300)
        self._eve_rate_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _build_buttons(self, sec: _CollapsibleSection) -> None:
        row1 = QHBoxLayout()
        self._btn_run   = QPushButton("Run")
        self._btn_pause = QPushButton("Pause")
        self._btn_run.setObjectName("btnRun")
        self._btn_pause.setObjectName("btnPause")
        self._btn_pause.setEnabled(False)
        self._btn_run.clicked.connect(self.run_clicked)
        self._btn_pause.clicked.connect(self.pause_clicked)
        row1.addWidget(self._btn_run)
        row1.addWidget(self._btn_pause)
        sec.addLayout(row1)

        row2 = QHBoxLayout()
        self._btn_step  = QPushButton("Step")
        self._btn_reset = QPushButton("Reset")
        self._btn_reset.setObjectName("btnReset")
        self._btn_step.clicked.connect(self.step_clicked)
        self._btn_reset.clicked.connect(self.reset_clicked)
        row2.addWidget(self._btn_step)
        row2.addWidget(self._btn_reset)
        sec.addLayout(row2)

    def _build_stage_indicator(self, sec: _CollapsibleSection) -> None:
        names = ["Prepare", "Transmit", "Measure", "Sift", "QBER", "Key"]
        row = QHBoxLayout()
        row.setSpacing(0)
        self._stage_dots: list[QLabel] = []
        for name in names:
            col = QVBoxLayout()
            col.setSpacing(2)
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet("color: rgba(60,70,120,200); font-size: 16px;")
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: rgba(100,110,170,160); font-size: 9px;")
            col.addWidget(dot)
            col.addWidget(lbl)
            self._stage_dots.append(dot)
            row.addLayout(col)
        sec.addLayout(row)

    # ------------------------------------------------------------------ #
    #  Slots                                                               #
    # ------------------------------------------------------------------ #

    def _on_eve_toggled(self, checked: bool) -> None:
        self._eve_rate_row.set_enabled(checked)
        self._eve_rate_anim.stop()
        if checked:
            target_h = self._eve_rate_container.sizeHint().height() + 10
            self._eve_rate_anim.setStartValue(0)
            self._eve_rate_anim.setEndValue(max(target_h, 44))
            self._eve_status_lbl.setText("ACTIVE")
            self._eve_status_lbl.setStyleSheet(
                "color: #ef5350; font-size: 11px; font-weight: bold;"
            )
        else:
            self._eve_rate_anim.setStartValue(self._eve_rate_container.height())
            self._eve_rate_anim.setEndValue(0)
            self._eve_status_lbl.setText("Inactive")
            self._eve_status_lbl.setStyleSheet(
                "color: rgba(150,160,200,160); font-size: 11px; font-style: italic;"
            )
        self._eve_rate_anim.start()
        self.eve_toggled.emit(checked)

    # ------------------------------------------------------------------ #
    #  State helpers (called by MainWindow)                                #
    # ------------------------------------------------------------------ #

    def set_running(self, running: bool) -> None:
        self._btn_run.setEnabled(not running)
        self._btn_pause.setEnabled(running)
        self._btn_step.setEnabled(not running)
        self._spin_key.setEnabled(not running)

    def set_eve_active(self, active: bool) -> None:
        """Programmatically enable/disable Eve (called by MainWindow for cross-layer sync).
        Animates the toggle and emits eve_toggled so the controller/canvas also update.
        """
        if self._eve_toggle.isChecked() == active:
            return  # already in the right state — nothing to do
        self._eve_toggle.setChecked(active)   # slides the toggle thumb (no signal emitted)
        self._on_eve_toggled(active)           # update label, emit eve_toggled

    def set_stage(self, stage: int) -> None:
        for i, dot in enumerate(self._stage_dots):
            if i < stage:
                dot.setStyleSheet("color: rgba(100,150,255,220); font-size: 16px;")
            elif i == stage:
                dot.setStyleSheet("color: #ef5350; font-size: 16px;")
            else:
                dot.setStyleSheet("color: rgba(60,70,120,200); font-size: 16px;")

    # ------------------------------------------------------------------ #
    #  Getters                                                             #
    # ------------------------------------------------------------------ #

    @property
    def key_length(self) -> int:
        return self._spin_key.value()

    @property
    def speed_ms(self) -> int:
        return self._speed_row.speed_ms

    @property
    def depol(self) -> float:
        return self._depol_row.value

    @property
    def loss(self) -> float:
        return self._loss_row.value

    @property
    def eve_active(self) -> bool:
        return self._eve_toggle.isChecked()

    @property
    def eve_rate(self) -> float:
        return self._eve_rate_row.value
