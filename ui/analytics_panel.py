"""
AnalyticsPanel
==============
Right-side analytics dashboard with:
  - QBER live numeric display + colour-coded bar
  - Live QBER line chart (rolling)
  - Sifted key counter
  - Final key display (post-session)
"""
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QGroupBox, QPlainTextEdit,
    QSizePolicy,
)

try:
    import pyqtgraph as pg
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

from controller.simulation_controller import SessionSummary


class AnalyticsPanel(QFrame):
    """Live analytics and session summary panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("analyticsPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        root.addWidget(self._build_qber_meter())
        root.addWidget(self._build_chart())
        root.addWidget(self._build_counters())
        self._log_group = None          # set by _build_log
        root.addWidget(self._build_log())

        self._qber_data: List[float] = []

    # ------------------------------------------------------------------ #
    #  Builders                                                            #
    # ------------------------------------------------------------------ #
    def _build_qber_meter(self) -> QGroupBox:
        grp = QGroupBox("Quantum Bit Error Rate (QBER)")
        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        # Big numeric value
        self._lbl_qber = QLabel("0.0 %")
        self._lbl_qber.setObjectName("labelQber")
        self._lbl_qber.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_qber.setStyleSheet("font-size: 32px; font-weight: bold; color: #00b894;")
        layout.addWidget(self._lbl_qber)

        # Coloured progress bar
        self._bar_qber = QProgressBar()
        self._bar_qber.setRange(0, 100)
        self._bar_qber.setValue(0)
        self._bar_qber.setFormat("")
        self._bar_qber.setFixedHeight(22)
        layout.addWidget(self._bar_qber)

        # Threshold labels
        thr_row = QHBoxLayout()
        thr_row.addStretch()
        lbl_safe = QLabel("Safe < 11%")
        lbl_safe.setStyleSheet("color: #00b894; font-size: 10px;")
        lbl_warn = QLabel("Warning < 20%")
        lbl_warn.setStyleSheet("color: #fdcb6e; font-size: 10px;")
        lbl_abort = QLabel("Abort > 20%")
        lbl_abort.setStyleSheet("color: #d63031; font-size: 10px;")
        thr_row.addWidget(lbl_safe)
        thr_row.addSpacing(8)
        thr_row.addWidget(lbl_warn)
        thr_row.addSpacing(8)
        thr_row.addWidget(lbl_abort)
        thr_row.addStretch()
        layout.addLayout(thr_row)

        return grp

    def _build_chart(self) -> QGroupBox:
        grp = QGroupBox("QBER Over Time (rolling)")
        layout = QVBoxLayout(grp)

        if _HAS_PG:
            pg.setConfigOptions(antialias=True, background="#050508", foreground="#7986cb")
            self._plot_widget = pg.PlotWidget()
            self._plot_widget.setLabel("left",   "QBER", units="%")
            self._plot_widget.setLabel("bottom", "Sifted bit #")
            self._plot_widget.setYRange(0, 35)
            self._plot_widget.showGrid(x=True, y=True, alpha=0.15)

            # Threshold reference lines
            pen_safe  = pg.mkPen(color="#00b894", width=1, style=Qt.PenStyle.DashLine)
            pen_abort = pg.mkPen(color="#d63031", width=1, style=Qt.PenStyle.DashLine)
            self._plot_widget.addLine(y=11, pen=pen_abort, label="Abort threshold (11%)")
            self._plot_widget.addLine(y=25, pen=pen_abort)

            self._qber_curve = self._plot_widget.plot(
                pen=pg.mkPen(color="#5c6bc0", width=2)
            )
            self._plot_widget.setMinimumHeight(160)
            layout.addWidget(self._plot_widget)
        else:
            # Fallback — just a label
            self._plot_widget = None
            self._qber_curve  = None
            lbl = QLabel(
                "Install pyqtgraph for live charts.\n"
                "pip install pyqtgraph"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #7f8c8d; font-size: 12px;")
            layout.addWidget(lbl)

        return grp

    def _build_counters(self) -> QGroupBox:
        grp = QGroupBox("Statistics")
        layout = QVBoxLayout(grp)
        layout.setSpacing(4)

        self._stat_labels = {}
        fields = [
            ("raw",     "Raw qubits sent"),
            ("lost",    "Photons lost"),
            ("sifted",  "Sifted key length"),
            ("final",   "Final key length"),
        ]
        for key, name in fields:
            row = QHBoxLayout()
            name_lbl = QLabel(name + ":")
            name_lbl.setStyleSheet("color: #7986cb; font-size: 12px;")
            val_lbl = QLabel("\u2014")
            val_lbl.setStyleSheet("color: #e8eaf6; font-weight: bold;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(val_lbl)
            layout.addLayout(row)
            self._stat_labels[key] = val_lbl

        return grp

    def _build_log(self) -> QGroupBox:
        grp = QGroupBox("Session Log")
        grp.setVisible(False)          # hidden by default; shown on session complete
        layout = QVBoxLayout(grp)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(200)
        self._log.setMinimumHeight(80)
        layout.addWidget(self._log)
        self._log_group = grp
        return grp

    # ------------------------------------------------------------------ #
    #  Update API                                                          #
    # ------------------------------------------------------------------ #
    def update_qber(self, qber: float) -> None:
        pct = qber * 100
        self._qber_data.append(pct)

        # Label + colour
        if pct < 10:
            colour = "#00b894"
        elif pct < 20:
            colour = "#fdcb6e"
        else:
            colour = "#d63031"
        self._lbl_qber.setText(f"{pct:.1f} %")
        self._lbl_qber.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {colour};"
        )
        self._bar_qber.setValue(int(pct))

        # Chart
        if _HAS_PG and self._qber_curve is not None:
            self._qber_curve.setData(list(range(len(self._qber_data))), self._qber_data)

    def update_stats(self, raw: int = 0, lost: int = 0,
                     sifted: int = 0, final: int = 0) -> None:
        self._stat_labels["raw"].setText(str(raw))
        self._stat_labels["lost"].setText(str(lost))
        self._stat_labels["sifted"].setText(str(sifted))
        self._stat_labels["final"].setText(str(final) if final else "—")

    def append_log(self, message: str) -> None:
        self._log.appendPlainText(message)

    def show_session_summary(self, summary: SessionSummary) -> None:
        """Update all widgets with final session data."""
        # Reveal the session log now that there's something to show
        if self._log_group is not None:
            self._log_group.setVisible(True)

        # Final QBER freeze
        self.update_qber(summary.qber)
        self.update_stats(
            raw=summary.raw_count,
            lost=summary.lost_count,
            sifted=summary.sifted_length,
            final=summary.final_key_length,
        )

        # Draw final QBER history onto chart if chart was empty (fast-run)
        if _HAS_PG and self._qber_curve is not None and summary.qber_history:
            history_pct = [q * 100 for q in summary.qber_history]
            self._qber_curve.setData(
                list(range(len(history_pct))), history_pct
            )

        # Log summary
        self.append_log("─" * 40)
        self.append_log("SESSION SUMMARY")
        self.append_log(f"  Raw qubits:     {summary.raw_count}")
        self.append_log(f"  Photons lost:   {summary.lost_count}")
        self.append_log(f"  Sifted key:     {summary.sifted_length} bits")
        self.append_log(f"  QBER:           {summary.qber*100:.2f} %")
        if summary.eve_detected:
            self.append_log("  Eve DETECTED  --  key ABORTED")
        else:
            self.append_log(f"  Final key:      {summary.final_key_length} bits (secure)")
            if summary.final_key_hex:
                key_preview = summary.final_key_hex[:48]
                if len(summary.final_key_hex) > 48:
                    key_preview += "…"
                self.append_log(f"  Key (hex):      {key_preview}")
        self.append_log("─" * 40)

    def reset(self) -> None:
        self._qber_data = []
        self._lbl_qber.setText("0.0 %")
        self._lbl_qber.setStyleSheet("font-size: 32px; font-weight: bold; color: #00b894;")
        self._bar_qber.setValue(0)
        if _HAS_PG and self._qber_curve is not None:
            self._qber_curve.setData([], [])
        self._log.clear()
        if self._log_group is not None:
            self._log_group.setVisible(False)
        for lbl in self._stat_labels.values():
            lbl.setText("—")
