"""
basis_matching_panel.py
========================
Real-time visualisation of the BB84 basis matching and sifting process.

Shows:
  - Key Sifting Visualizer  – animated coloured bit cells:
      Row 0 (Alice): each bit green if bases matched, red if discarded, grey if lost
      Row 1 (Bob):   same colour coding, shows bob_bit value
      Row 2 (Match): ✓ green / ✗ red / — grey for each photon
      Row 3 (Sifted key): only the bits that survived sifting, bright green
  - The last N photons as a scrolling detail table
  - Running sifted-key bit count and discard ratio
  - QBER spike indicator during attacks
"""
from __future__ import annotations

from collections import deque
from typing import Deque, List, Dict, Any

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QScrollArea, QGroupBox, QSizePolicy, QProgressBar,
)

from controller.simulation_controller import PhotonEvent


# ──────────────────────────────────────────────────────────────────────── #
#  Key Sifting Visualizer Canvas                                           #
# ──────────────────────────────────────────────────────────────────────── #

class _SiftingCanvas(QWidget):
    """
    Custom-painted sliding-window view of the last N BB84 photon bits.

    Layout (4 rows):
      Alice  – raw bit, coloured by match/mismatch/lost
      Bob    – raw bit (or ?) with same band colour
      Match  – ✓ green / ✗ red / — grey per photon
      Sifted – growing secure key, only matched bits, bright green
    """

    _CELL_W   = 18        # px width of one bit cell
    _CELL_H   = 22        # px height of one cell
    _GAP      = 2         # px gap between rows and between cells
    _LABEL_W  = 46        # px width of row-label column
    _N_ROWS   = 4

    _COL_MATCH_BG    = QColor(0,   184, 100,  160)
    _COL_MISMATCH_BG = QColor(210,  65,  60,  160)
    _COL_LOST_BG     = QColor( 70,  70,  90,   90)
    _COL_SIFTED_BG   = QColor(  0,  210, 130,  180)
    _COL_TEXT        = QColor(230, 234, 246)
    _COL_DIM_TEXT    = QColor(120, 130, 160)
    _COL_LABEL       = QColor(100, 120, 180)
    _ROW_BGS = [
        QColor(20, 30, 65, 120),   # Alice
        QColor(20, 20, 55, 120),   # Bob
        QColor(12, 22, 45, 120),   # Match
        QColor(10, 35, 25, 120),   # Sifted
    ]
    _ROW_NAMES = ["Alice", "Bob", "Match", "Sifted"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cells: deque[Dict[str, Any]] = deque(maxlen=200)
        self._sifted_bits: deque[int]      = deque(maxlen=200)

        # Flash state for newest arrival
        self._flash_val: float = 0.0
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(25)
        self._flash_timer.timeout.connect(self._tick_flash)

        # Pre-create fonts (use setPixelSize – avoids the QFont point-size warning)
        self._font_cell = QFont("Consolas")
        self._font_cell.setPixelSize(10)
        self._font_cell.setBold(True)
        self._font_label = QFont("Segoe UI")
        self._font_label.setPixelSize(10)

        total_h = self._N_ROWS * (self._CELL_H + self._GAP) + self._GAP + 4
        self.setMinimumHeight(total_h)
        self.setMaximumHeight(total_h + 4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    # ── public API ──────────────────────────────────────────────────── #

    def add_event(self, event: PhotonEvent) -> None:
        cell: Dict[str, Any] = {
            "alice": event.alice_bit,
            "bob":   event.bob_bit,
            "match": event.bases_match,
            "lost":  event.lost,
        }
        self._cells.append(cell)
        if event.bases_match and not event.lost:
            self._sifted_bits.append(event.alice_bit)

        # Kick off entry flash
        self._flash_val = 1.0
        if not self._flash_timer.isActive():
            self._flash_timer.start()
        self.update()

    def reset(self) -> None:
        self._cells.clear()
        self._sifted_bits.clear()
        self._flash_timer.stop()
        self._flash_val = 0.0
        self.update()

    # ── internal ────────────────────────────────────────────────────── #

    def _tick_flash(self) -> None:
        self._flash_val = max(0.0, self._flash_val - 0.07)
        if self._flash_val <= 0.0:
            self._flash_timer.stop()
        self.update()

    def _visible_window(self, max_cells: int) -> tuple[list, int]:
        """Return (visible_cells_list, first_global_index)."""
        cells = list(self._cells)
        n = len(cells)
        if n > max_cells:
            return cells[-max_cells:], n - max_cells
        return cells, 0

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        lw = self._LABEL_W
        avail = W - lw - 8
        max_vis = max(1, avail // (self._CELL_W + self._GAP))
        window, win_offset = self._visible_window(max_vis)
        total_cells = len(self._cells)

        # ── row backgrounds + labels ─────────────────────────────────
        for ri in range(self._N_ROWS):
            y = self._GAP + ri * (self._CELL_H + self._GAP)
            p.setBrush(QBrush(self._ROW_BGS[ri]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, y, W, self._CELL_H), 3, 3)

            p.setPen(QPen(self._COL_LABEL))
            p.setFont(self._font_label)
            p.drawText(
                QRectF(4, y, lw - 4, self._CELL_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._ROW_NAMES[ri],
            )

        # ── draw Alice / Bob / Match cells ───────────────────────────
        for i, cell in enumerate(window):
            global_idx = win_offset + i
            is_newest  = (global_idx == total_cells - 1)
            x = lw + i * (self._CELL_W + self._GAP)

            if cell["lost"]:
                bg = QColor(self._COL_LOST_BG)
            elif cell["match"]:
                bg = QColor(self._COL_MATCH_BG)
            else:
                bg = QColor(self._COL_MISMATCH_BG)

            if is_newest and self._flash_val > 0:
                # brighten toward white
                fv = self._flash_val
                bg = QColor(
                    int(bg.red()   + (255 - bg.red())   * fv * 0.55),
                    int(bg.green() + (255 - bg.green()) * fv * 0.55),
                    int(bg.blue()  + (255 - bg.blue())  * fv * 0.55),
                    min(255, bg.alpha() + int((255 - bg.alpha()) * fv * 0.4)),
                )

            for ri in range(3):    # Alice, Bob, Match
                y = self._GAP + ri * (self._CELL_H + self._GAP)
                cy = y + 2

                p.setBrush(QBrush(bg))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(x, cy, self._CELL_W, self._CELL_H - 4), 3, 3)

                if ri == 0:
                    txt = str(cell["alice"])
                    tcol = self._COL_TEXT
                elif ri == 1:
                    bob = cell["bob"]
                    txt = str(bob) if bob is not None else "?"
                    tcol = self._COL_TEXT if not cell["lost"] else self._COL_DIM_TEXT
                else:   # match marker
                    if cell["lost"]:
                        txt = "—"
                        tcol = self._COL_DIM_TEXT
                    elif cell["match"]:
                        txt = "✓"
                        tcol = QColor(180, 255, 200)
                    else:
                        txt = "✗"
                        tcol = QColor(255, 160, 150)

                p.setPen(QPen(tcol))
                p.setFont(self._font_cell)
                p.drawText(
                    QRectF(x, cy, self._CELL_W, self._CELL_H - 4),
                    Qt.AlignmentFlag.AlignCenter,
                    txt,
                )

        # ── draw Sifted key row (independent sliding window) ─────────
        ri = 3
        y  = self._GAP + ri * (self._CELL_H + self._GAP)
        sifted = list(self._sifted_bits)
        ns = len(sifted)
        sifted_win = sifted[-max_vis:] if ns > max_vis else sifted

        for i, bit in enumerate(sifted_win):
            x  = lw + i * (self._CELL_W + self._GAP)
            cy = y + 2
            is_newest_s = (i == len(sifted_win) - 1)

            bg_s = QColor(self._COL_SIFTED_BG)
            if is_newest_s and self._flash_val > 0:
                fv = self._flash_val
                bg_s = QColor(
                    int(bg_s.red()   + (255 - bg_s.red())   * fv * 0.5),
                    int(bg_s.green() + (255 - bg_s.green()) * fv * 0.5),
                    int(bg_s.blue()  + (255 - bg_s.blue())  * fv * 0.5),
                    min(255, bg_s.alpha() + int((255 - bg_s.alpha()) * fv * 0.3)),
                )

            p.setBrush(QBrush(bg_s))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, cy, self._CELL_W, self._CELL_H - 4), 3, 3)

            p.setPen(QPen(self._COL_TEXT))
            p.setFont(self._font_cell)
            p.drawText(
                QRectF(x, cy, self._CELL_W, self._CELL_H - 4),
                Qt.AlignmentFlag.AlignCenter,
                str(bit),
            )

        p.end()


# ──────────────────────────────────────────────────────────────────────── #
#  Single photon row widget                                                 #
# ──────────────────────────────────────────────────────────────────────── #

class _PhotonRow(QWidget):
    """One row in the scrolling basis-matching table."""

    _BG_MATCH    = QColor(0, 180, 100, 40)
    _BG_MISMATCH = QColor(180, 80, 0, 30)
    _BG_LOST     = QColor(80, 80, 80, 30)
    _BG_DEFAULT  = QColor(14, 14, 26, 0)

    _HEIGHT = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self._HEIGHT)
        self._fade: float = 0.0
        self._match_flash: float = 0.0
        self._bg_color = self._BG_DEFAULT

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        def cell(txt, color, w=55, align=Qt.AlignmentFlag.AlignCenter):
            lbl = QLabel(txt)
            lbl.setFixedWidth(w)
            lbl.setAlignment(align)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
            return lbl

        self._lbl_idx    = cell("#",      "#7986cb", w=36)
        self._lbl_abit   = cell("—",      "#74b9ff", w=28)
        self._lbl_abasis = cell("+",      "#90caf9", w=32)
        self._lbl_bbasis = cell("+",      "#a29bfe", w=32)
        self._lbl_bbit   = cell("—",      "#74b9ff", w=28)
        self._lbl_result = cell("—",      "#ffffff", w=60)
        self._lbl_qber   = cell("—",      "#fdcb6e", w=55)

        for w in [self._lbl_idx, self._lbl_abit, self._lbl_abasis,
                  self._lbl_bbasis, self._lbl_bbit, self._lbl_result,
                  self._lbl_qber]:
            layout.addWidget(w)
        layout.addStretch()

    def populate(self, event: PhotonEvent) -> None:
        self._lbl_idx.setText(str(event.index + 1))
        self._lbl_abit.setText(str(event.alice_bit))
        self._lbl_abasis.setText(event.alice_basis)
        self._lbl_bbasis.setText(event.bob_basis or "?")
        self._lbl_bbit.setText(str(event.bob_bit) if event.bob_bit is not None else "?")

        if event.lost:
            self._lbl_result.setText("LOST")
            self._lbl_result.setStyleSheet(
                "color: #636e72; font-size: 10px; font-weight: bold; background: transparent;"
            )
            self._bg_color = self._BG_LOST
        elif event.bases_match:
            self._lbl_result.setText("✓ SIFTED")
            self._lbl_result.setStyleSheet(
                "color: #00b894; font-size: 10px; font-weight: bold; background: transparent;"
            )
            self._bg_color = self._BG_MATCH
        else:
            self._lbl_result.setText("✗ DISCARD")
            self._lbl_result.setStyleSheet(
                "color: #e17055; font-size: 10px; font-weight: bold; background: transparent;"
            )
            self._bg_color = self._BG_MISMATCH

        qber_pct = event.rolling_qber * 100
        qber_color = (
            "#00b894" if qber_pct < 11 else
            "#fdcb6e" if qber_pct < 20 else
            "#d63031"
        )
        self._lbl_qber.setText(f"{qber_pct:.1f}%")
        self._lbl_qber.setStyleSheet(
            f"color: {qber_color}; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self._bg_color)
        p.end()


# ──────────────────────────────────────────────────────────────────────── #
#  Basis Matching Panel                                                     #
# ──────────────────────────────────────────────────────────────────────── #

class BasisMatchingPanel(QFrame):
    """
    Scrolling live visualisation of basis matching.
    Feed photon events via update_photon().
    """

    _MAX_ROWS = 60        # visible rows before old ones scroll off

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("basisMatchingPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._total       = 0
        self._sifted      = 0
        self._discarded   = 0
        self._lost        = 0
        self._errors      = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── title
        title = QLabel("Basis Matching & Sifting")
        title.setStyleSheet(
            "color: #90caf9; font-size: 13px; font-weight: bold; background: transparent;"
        )
        root.addWidget(title)

        # ── summary bar
        root.addWidget(self._build_summary_bar())

        # ── sifting efficiency bar
        eff_row = QHBoxLayout()
        eff_lbl = QLabel("Sifting Efficiency:")
        eff_lbl.setStyleSheet("color: #7986cb; font-size: 11px; background: transparent;")
        self._eff_bar = QProgressBar()
        self._eff_bar.setRange(0, 100)
        self._eff_bar.setValue(0)
        self._eff_bar.setFixedHeight(12)
        self._eff_bar.setFormat("")
        self._eff_bar.setStyleSheet(
            "QProgressBar { background: rgba(14,14,26,180); border-radius: 5px; border: none; }"
            "QProgressBar::chunk { background: #00b894; border-radius: 5px; }"
        )
        eff_row.addWidget(eff_lbl)
        eff_row.addWidget(self._eff_bar)
        root.addLayout(eff_row)

        # ── Key Sifting Visualizer ──────────────────────────────────
        vis_grp = QGroupBox("Key Sifting Visualizer")
        vis_grp.setStyleSheet(
            "QGroupBox { color: #74b9ff; font-size: 11px; font-weight: bold;"
            " border: 1px solid rgba(80,100,220,80); border-radius: 6px;"
            " margin-top: 8px; padding-top: 4px; background: rgba(10,10,30,80); }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;"
            " left: 8px; padding: 0 4px; }"
        )
        vis_layout = QVBoxLayout(vis_grp)
        vis_layout.setContentsMargins(6, 10, 6, 6)
        vis_layout.setSpacing(4)

        # Canvas
        self._sifting_canvas = _SiftingCanvas()
        vis_layout.addWidget(self._sifting_canvas)

        # Legend + count row
        legend_row = QHBoxLayout()
        legend_row.setSpacing(12)

        def _legend_chip(color: str, text: str) -> QWidget:
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)
            chip = QLabel()
            chip.setFixedSize(12, 12)
            chip.setStyleSheet(
                f"background: {color}; border-radius: 3px;"
            )
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #7986cb; font-size: 10px; background: transparent;")
            hl.addWidget(chip)
            hl.addWidget(lbl)
            return w

        legend_row.addWidget(_legend_chip("#00b864", "Bases matched (sifted)"))
        legend_row.addWidget(_legend_chip("#d23c3c", "Bases mismatched"))
        legend_row.addWidget(_legend_chip("#505060", "Photon lost"))
        legend_row.addWidget(_legend_chip("#00d282", "Sifted key bit"))
        legend_row.addStretch()

        self._sifted_count_lbl = QLabel("Sifted key: 0 bits")
        self._sifted_count_lbl.setStyleSheet(
            "color: #00b894; font-size: 11px; font-weight: bold; background: transparent;"
        )
        legend_row.addWidget(self._sifted_count_lbl)
        vis_layout.addLayout(legend_row)

        root.addWidget(vis_grp)

        # ── column headers
        root.addWidget(self._build_header())

        # ── scrolling table
        self._rows: List[_PhotonRow] = []
        self._row_container = QWidget()
        rc_layout = QVBoxLayout(self._row_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(1)

        scroll = QScrollArea()
        scroll.setWidget(self._row_container)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(180)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: rgba(20,20,40,150); width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: rgba(80,100,220,180); border-radius: 3px; }"
        )
        self._scroll = scroll
        root.addWidget(scroll, stretch=1)

        # ── QBER spike label
        self._spike_lbl = QLabel("")
        self._spike_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spike_lbl.setStyleSheet(
            "color: #d63031; font-size: 11px; font-weight: bold; background: transparent;"
        )
        root.addWidget(self._spike_lbl)
        self._spike_timer = QTimer(self)
        self._spike_timer.setSingleShot(True)
        self._spike_timer.timeout.connect(lambda: self._spike_lbl.setText(""))

    # ------------------------------------------------------------------ #
    #  UI builders                                                         #
    # ------------------------------------------------------------------ #

    def _build_summary_bar(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        def stat(label, init="0"):
            col = QWidget()
            col.setStyleSheet("background: transparent;")
            vl = QVBoxLayout(col)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(1)
            val_lbl = QLabel(init)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #e8eaf6; background: transparent;")
            key_lbl = QLabel(label)
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_lbl.setStyleSheet("font-size: 10px; color: #7986cb; background: transparent;")
            vl.addWidget(val_lbl)
            vl.addWidget(key_lbl)
            layout.addWidget(col)
            return val_lbl

        self._lbl_total    = stat("Total")
        self._lbl_sifted   = stat("Sifted")
        self._lbl_disc     = stat("Discarded")
        self._lbl_lost     = stat("Lost")
        self._lbl_errors   = stat("Errors")
        layout.addStretch()
        return w

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(
            "background: rgba(20,20,50,200); border-radius: 4px;"
        )
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        def hdr(txt, w=55, color="#7986cb"):
            lbl = QLabel(txt)
            lbl.setFixedWidth(w)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold; background: transparent;")
            return lbl

        for lbl in [
            hdr("#", 36), hdr("A-bit", 28), hdr("A-basis", 32),
            hdr("B-basis", 32), hdr("B-bit", 28),
            hdr("Result", 60, "#90caf9"), hdr("QBER", 55, "#fdcb6e"),
        ]:
            layout.addWidget(lbl)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def update_photon(self, event: PhotonEvent) -> None:
        """Add a photon event to the table and update counters."""
        self._total += 1
        if event.lost:
            self._lost += 1
        elif event.bases_match:
            self._sifted += 1
            if event.bob_bit is not None and event.bob_bit != event.alice_bit:
                self._errors += 1
        else:
            self._discarded += 1

        self._update_counters()
        self._add_row(event)

        # Feed the sifting visualizer
        self._sifting_canvas.add_event(event)
        self._sifted_count_lbl.setText(f"Sifted key: {self._sifted} bits")

        # QBER spike detection
        if event.rolling_qber > 0.20 and not event.lost:
            self._spike_lbl.setText(
                f"⚠ QBER SPIKE: {event.rolling_qber*100:.1f}%  —  Possible eavesdropping!"
            )
            self._spike_timer.start(4000)

    def reset(self) -> None:
        """Clear all data."""
        self._total = self._sifted = self._discarded = self._lost = self._errors = 0
        self._update_counters()
        for row in self._rows:
            row.setParent(None)
        self._rows.clear()
        self._spike_lbl.setText("")
        self._eff_bar.setValue(0)
        self._sifting_canvas.reset()
        self._sifted_count_lbl.setText("Sifted key: 0 bits")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _update_counters(self) -> None:
        self._lbl_total.setText(str(self._total))
        self._lbl_sifted.setText(str(self._sifted))
        self._lbl_disc.setText(str(self._discarded))
        self._lbl_lost.setText(str(self._lost))
        self._lbl_errors.setText(str(self._errors))

        if self._total > 0:
            eff = int((self._sifted / self._total) * 100)
            self._eff_bar.setValue(eff)

    def _add_row(self, event: PhotonEvent) -> None:
        row = _PhotonRow()
        row.populate(event)

        # Add to layout
        self._row_container.layout().addWidget(row)
        self._rows.append(row)

        # Prune old rows
        if len(self._rows) > self._MAX_ROWS:
            old = self._rows.pop(0)
            old.setParent(None)

        # Auto-scroll to bottom
        QTimer.singleShot(10, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
