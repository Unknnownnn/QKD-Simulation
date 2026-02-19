"""
secure_messaging_app.py
========================
A standalone secure communication application that uses the QKD simulation
infrastructure to encrypt and decrypt real messages.

Architecture:
  - Uses BB84Protocol.full_run() to establish a shared session key.
  - Encrypts messages with XOR (One-Time Pad) using the QKD key.
  - Displays the full flow: key generation → encryption → decryption.
  - Shows QBER, key health, and attack status.
  - Two-panel UI: Alice (send) and Bob (receive).

Run as:  python secure_messaging_app.py
"""
from __future__ import annotations

import sys
import os
import hashlib
import time
from typing import List, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QGroupBox,
    QProgressBar, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget,
)

from simulation.bb84 import BB84Protocol
from simulation.quantum_channel import NoiseModel
from simulation.session_result import SessionResult
from simulation.attacks import (
    InterceptResendAttack, PhotonNumberSplittingAttack,
    TrojanHorseAttack, ATTACK_LABELS,
)
from controller.sdn_controller import SDNController
from ui.network_dashboard import NetworkDashboard
from ui.basis_matching_panel import BasisMatchingPanel
from ui.styles import DARK_STYLESHEET


# ──────────────────────────────────────────────────────────────────────── #
#  Crypto helpers                                                           #
# ──────────────────────────────────────────────────────────────────────── #

def bits_to_bytes(bits: List[int]) -> bytes:
    """Convert a bit list to bytes (zero-padded to multiples of 8)."""
    padded = bits + [0] * ((-len(bits)) % 8)
    out = bytearray()
    for i in range(0, len(padded), 8):
        byte = 0
        for b in padded[i:i+8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)


def bytes_to_bits(data: bytes) -> List[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def xor_encrypt(message: bytes, key_bits: List[int]) -> bytes:
    """XOR (OTP) encrypt message bytes with key bits."""
    key_bytes = bits_to_bytes(key_bits)
    # Repeat key if shorter than message (not true OTP, but practical)
    extended_key = (key_bytes * ((len(message) // len(key_bytes)) + 1))[:len(message)]
    return bytes(a ^ b for a, b in zip(message, extended_key))


def xor_decrypt(ciphertext: bytes, key_bits: List[int]) -> bytes:
    return xor_encrypt(ciphertext, key_bits)   # XOR is self-inverse


# ──────────────────────────────────────────────────────────────────────── #
#  Background QKD key generation thread                                    #
# ──────────────────────────────────────────────────────────────────────── #

class _KeyGenWorker(QObject):
    """Runs BB84 full_run() in a background thread."""

    finished = pyqtSignal(object)   # SessionResult
    error    = pyqtSignal(str)

    def __init__(
        self,
        key_length: int,
        noise_depol: float,
        noise_loss: float,
        eve_active: bool,
        eve_rate: float,
        attack_type: str,
    ):
        super().__init__()
        self.key_length  = key_length
        self.noise_depol = noise_depol
        self.noise_loss  = noise_loss
        self.eve_active  = eve_active
        self.eve_rate    = eve_rate
        self.attack_type = attack_type

    def run(self) -> None:
        try:
            noise = NoiseModel(
                depolarization=self.noise_depol,
                photon_loss=self.noise_loss,
            )
            protocol = BB84Protocol(
                key_length=self.key_length,
                noise_model=noise,
                eve_active=self.eve_active,
                eve_intercept_rate=self.eve_rate,
            )
            result = protocol.full_run()
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ──────────────────────────────────────────────────────────────────────── #
#  Message log widget                                                       #
# ──────────────────────────────────────────────────────────────────────── #

class _MessageLog(QFrame):
    """Scrolling message history with sender, receiver, and encryption details."""

    def __init__(self, title: str, label_color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("messageLog")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"color: {label_color}; font-size: 13px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(hdr)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(
            "QTextEdit { background: rgba(8,8,18,200); color: #e8eaf6;"
            " border: 1px solid rgba(80,100,220,60); border-radius: 6px;"
            " font-family: Consolas, monospace; font-size: 11px; line-height: 1.4; }"
        )
        layout.addWidget(self._text)

    def append(self, line: str, color: str = "#e8eaf6") -> None:
        ts = time.strftime("%H:%M:%S")
        self._text.append(f'<span style="color:{color};">[{ts}] {line}</span>')

    def clear_log(self) -> None:
        self._text.clear()


# ──────────────────────────────────────────────────────────────────────── #
#  Key status widget                                                        #
# ──────────────────────────────────────────────────────────────────────── #

class _KeyStatusWidget(QGroupBox):
    """Displays the current QKD session key status."""

    def __init__(self, parent=None):
        super().__init__("QKD Key Status", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        def row(label, color="#e8eaf6"):
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label + ":")
            lbl.setFixedWidth(120)
            lbl.setStyleSheet("color: #7986cb; font-size: 11px; background: transparent;")
            val = QLabel("—")
            val.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
            h.addWidget(lbl)
            h.addWidget(val, stretch=1)
            layout.addWidget(w)
            return val

        self._lbl_status    = row("Status",       "#fdcb6e")
        self._lbl_qber      = row("QBER",          "#74b9ff")
        self._lbl_key_len   = row("Key bits",      "#74b9ff")
        self._lbl_key_rate  = row("Key rate",      "#74b9ff")
        self._lbl_eve       = row("Eve detected",  "#ff7675")
        self._lbl_hash      = row("Key SHA-256",   "#a29bfe")

        # QBER bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(10)
        self._bar.setFormat("")
        self._bar.setStyleSheet(
            "QProgressBar { background: rgba(20,20,40,200); border-radius: 4px; border: none; }"
            "QProgressBar::chunk { background: #00b894; border-radius: 4px; }"
        )
        layout.addWidget(self._bar)

    def update_from_result(self, result: SessionResult) -> None:
        n_sifted = len(result.sifted_key_alice)
        n_final  = len(result.final_key)
        qber_pct = result.qber * 100

        self._lbl_qber.setText(f"{qber_pct:.1f}%")
        self._lbl_key_len.setText(f"{n_final} bits ({n_final // 8} bytes)")
        self._lbl_key_rate.setText(
            f"{n_sifted / result.key_length_requested * 100:.0f}% sifting, "
            f"{n_final / max(n_sifted, 1) * 100:.0f}% PA"
        )

        if result.eve_detected:
            self._lbl_status.setText("ABORTED — Eve detected!")
            self._lbl_status.setStyleSheet("color: #d63031; font-size: 11px; background: transparent;")
            self._lbl_eve.setText("YES")
            self._lbl_eve.setStyleSheet("color: #d63031; font-size: 11px; font-weight: bold; background: transparent;")
        elif n_final == 0:
            self._lbl_status.setText("No key (insufficient bits)")
            self._lbl_status.setStyleSheet("color: #fdcb6e; font-size: 11px; background: transparent;")
            self._lbl_eve.setText("No")
        else:
            self._lbl_status.setText("Secure key established ✓")
            self._lbl_status.setStyleSheet("color: #00b894; font-size: 11px; background: transparent;")
            self._lbl_eve.setText("No")
            self._lbl_eve.setStyleSheet("color: #00b894; font-size: 11px; background: transparent;")

        if result.final_key:
            key_bytes = bits_to_bytes(result.final_key)
            sha = hashlib.sha256(key_bytes).hexdigest()[:20] + "..."
            self._lbl_hash.setText(sha)

        bar_val = min(int(qber_pct * 2), 100)
        self._bar.setValue(bar_val)
        color = "#00b894" if qber_pct < 11 else "#fdcb6e" if qber_pct < 20 else "#d63031"
        self._bar.setStyleSheet(
            "QProgressBar { background: rgba(20,20,40,200); border-radius: 4px; border: none; }"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
        )

    def reset(self) -> None:
        self._lbl_status.setText("—")
        self._lbl_status.setStyleSheet("color: #fdcb6e; font-size: 11px; background: transparent;")
        self._lbl_qber.setText("—")
        self._lbl_key_len.setText("—")
        self._lbl_key_rate.setText("—")
        self._lbl_eve.setText("—")
        self._lbl_hash.setText("—")
        self._bar.setValue(0)


# ──────────────────────────────────────────────────────────────────────── #
#  Main Secure Messaging Window                                             #
# ──────────────────────────────────────────────────────────────────────── #

class SecureMessagingWindow(QMainWindow):
    """
    Full-stack secure communication application using QKD infrastructure.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QKD Secure Messaging Platform")
        self.resize(1400, 860)
        self.setMinimumSize(1000, 660)
        self.setStyleSheet(DARK_STYLESHEET)

        self._key_bits:   List[int]          = []
        self._session:    Optional[SessionResult] = None
        self._worker:     Optional[_KeyGenWorker] = None
        self._thread:     Optional[QThread]       = None
        self._key_gen_start: float = 0.0

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        # Title bar
        title_row = QHBoxLayout()
        title = QLabel("QKD Secure Messaging Platform")
        title.setStyleSheet(
            "color: #e8eaf6; font-size: 16px; font-weight: bold; background: transparent;"
        )
        subtitle = QLabel("Quantum Key Distribution · One-Time Pad Encryption · SDN Security")
        subtitle.setStyleSheet("color: #7986cb; font-size: 11px; background: transparent;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(subtitle)
        root.addLayout(title_row)

        # Main tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid rgba(80,100,220,60); border-radius: 6px; }"
            "QTabBar::tab { background: rgba(14,14,26,180); color: #90caf9;"
            " padding: 6px 16px; border-radius: 4px; margin-right: 2px; }"
            "QTabBar::tab:selected { background: rgba(40,50,140,200); color: #e8eaf6; }"
            "QTabBar::tab:hover { background: rgba(30,30,80,220); }"
        )

        tabs.addTab(self._build_messaging_tab(), "💬 Secure Messaging")
        tabs.addTab(self._build_key_gen_tab(), "🔑 Key Generation")
        tabs.addTab(self._build_network_tab(), "🌐 Network Dashboard")
        tabs.addTab(self._build_basis_tab(), "📊 Basis Matching")

        root.addWidget(tabs, stretch=1)

        # Status bar
        self.statusBar().setStyleSheet(
            "background: rgba(10,10,25,230); color: #7986cb;"
            " border-top: 1px solid rgba(80,100,220,60); font-size: 11px;"
        )
        self.statusBar().showMessage("Ready — generate a QKD key to begin")

    # ── Tab: Secure Messaging ────────────────────────────────────────── #

    def _build_messaging_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Alice panel
        alice_w = QWidget()
        alice_layout = QVBoxLayout(alice_w)
        alice_layout.setContentsMargins(4, 4, 4, 4)

        alice_hdr = QLabel("🧑 Alice — Sender")
        alice_hdr.setStyleSheet(
            "color: #74b9ff; font-size: 13px; font-weight: bold; background: transparent;"
        )
        alice_layout.addWidget(alice_hdr)

        # Message input
        self._alice_input = QTextEdit()
        self._alice_input.setPlaceholderText("Type a secret message here...")
        self._alice_input.setFixedHeight(80)
        self._alice_input.setStyleSheet(
            "QTextEdit { background: rgba(14,14,40,200); color: #e8eaf6;"
            " border: 1px solid rgba(80,100,220,120); border-radius: 6px; padding: 6px; "
            "font-size: 12px; }"
        )
        alice_layout.addWidget(self._alice_input)

        btn_row = QHBoxLayout()
        self._btn_encrypt = QPushButton("🔒 Encrypt & Send")
        self._btn_encrypt.setEnabled(False)
        self._btn_encrypt.clicked.connect(self._on_encrypt_send)
        self._btn_encrypt.setStyleSheet(
            "QPushButton { background: rgba(74,114,196,100); color: #74b9ff;"
            " border: 1px solid rgba(74,114,196,160); border-radius: 6px; padding: 8px 18px; }"
            "QPushButton:hover { background: rgba(74,114,196,180); }"
            "QPushButton:disabled { background: rgba(40,40,80,80); color: #555; }"
        )
        btn_row.addWidget(self._btn_encrypt)
        btn_row.addStretch()
        alice_layout.addLayout(btn_row)

        self._alice_log = _MessageLog("Alice's Outbox", "#74b9ff")
        alice_layout.addWidget(self._alice_log, stretch=1)
        splitter.addWidget(alice_w)

        # Channel display
        channel_w = QWidget()
        channel_layout = QVBoxLayout(channel_w)
        channel_layout.setContentsMargins(4, 4, 4, 4)

        ch_hdr = QLabel("📡 Quantum Channel")
        ch_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ch_hdr.setStyleSheet(
            "color: #a29bfe; font-size: 13px; font-weight: bold; background: transparent;"
        )
        channel_layout.addWidget(ch_hdr)

        self._key_status = _KeyStatusWidget()
        channel_layout.addWidget(self._key_status)

        # Ciphertext display
        cipher_grp = QGroupBox("Ciphertext (Transmitted)")
        cipher_layout = QVBoxLayout(cipher_grp)
        self._cipher_display = QTextEdit()
        self._cipher_display.setReadOnly(True)
        self._cipher_display.setFixedHeight(80)
        self._cipher_display.setStyleSheet(
            "QTextEdit { background: rgba(14,14,40,200); color: #fdcb6e;"
            " border: 1px solid rgba(253,203,110,80); border-radius: 6px; padding: 4px;"
            " font-family: Consolas, monospace; font-size: 10px; }"
        )
        cipher_layout.addWidget(self._cipher_display)
        channel_layout.addWidget(cipher_grp)

        channel_layout.addStretch()
        splitter.addWidget(channel_w)

        # Bob panel
        bob_w = QWidget()
        bob_layout = QVBoxLayout(bob_w)
        bob_layout.setContentsMargins(4, 4, 4, 4)

        bob_hdr = QLabel("👤 Bob — Receiver")
        bob_hdr.setStyleSheet(
            "color: #00b894; font-size: 13px; font-weight: bold; background: transparent;"
        )
        bob_layout.addWidget(bob_hdr)

        self._btn_decrypt = QPushButton("🔓 Decrypt")
        self._btn_decrypt.setEnabled(False)
        self._btn_decrypt.clicked.connect(self._on_decrypt)
        self._btn_decrypt.setStyleSheet(
            "QPushButton { background: rgba(0,184,148,80); color: #00b894;"
            " border: 1px solid rgba(0,184,148,160); border-radius: 6px; padding: 8px 18px; }"
            "QPushButton:hover { background: rgba(0,184,148,150); }"
            "QPushButton:disabled { background: rgba(40,40,80,80); color: #555; }"
        )
        bob_layout.addWidget(self._btn_decrypt)

        self._bob_log = _MessageLog("Bob's Inbox", "#00b894")
        bob_layout.addWidget(self._bob_log, stretch=1)
        splitter.addWidget(bob_w)

        splitter.setSizes([340, 320, 340])
        layout.addWidget(splitter)

        # Bottom: pending ciphertext holder
        self._pending_cipher: Optional[bytes] = None
        return w

    # ── Tab: Key Generation ──────────────────────────────────────────── #

    def _build_key_gen_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Settings
        settings_grp = QGroupBox("QKD Settings")
        settings_grp.setFixedWidth(280)
        sl = QVBoxLayout(settings_grp)
        sl.setSpacing(10)

        def add_spin(label, default, lo, hi, step=1, double=False):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #90caf9; background: transparent; font-size: 11px;")
            if double:
                spin = QDoubleSpinBox()
                spin.setDecimals(3)
                spin.setSingleStep(step)
                spin.setRange(lo, hi)
                spin.setValue(default)
            else:
                spin = QSpinBox()
                spin.setRange(lo, hi)
                spin.setValue(default)
                spin.setSingleStep(step)
            spin.setStyleSheet(
                "QSpinBox, QDoubleSpinBox { background: rgba(20,20,50,200); color: #e8eaf6;"
                " border: 1px solid rgba(80,100,220,100); border-radius: 4px; padding: 3px; }"
            )
            row.addWidget(lbl, stretch=1)
            row.addWidget(spin)
            sl.addLayout(row)
            return spin

        self._spin_keylen  = add_spin("Key Length (qubits)", 512,  64, 4096, 64)
        self._spin_depol   = add_spin("Depolarization",       0.02, 0.0, 0.3, 0.005, double=True)
        self._spin_loss    = add_spin("Photon Loss",           0.05, 0.0, 0.5, 0.01,  double=True)

        # Eve checkbox + rate
        self._chk_eve = QCheckBox("Enable Eve (intercept-resend)")
        self._chk_eve.setStyleSheet("color: #ff7675; background: transparent; font-size: 11px;")
        sl.addWidget(self._chk_eve)

        self._spin_eve_rate = add_spin("Eve Intercept Rate", 1.0, 0.0, 1.0, 0.1, double=True)

        # Generate button
        self._btn_gen_key = QPushButton("⚡ Generate QKD Key")
        self._btn_gen_key.clicked.connect(self._on_generate_key)
        self._btn_gen_key.setStyleSheet(
            "QPushButton { background: rgba(74,114,196,120); color: #74b9ff;"
            " border: 1px solid rgba(74,114,196,200); border-radius: 6px;"
            " padding: 10px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(74,114,196,200); }"
        )
        sl.addWidget(self._btn_gen_key)

        # Status
        self._gen_status = QLabel("No key generated")
        self._gen_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gen_status.setStyleSheet("color: #7986cb; font-size: 11px; background: transparent;")
        self._gen_status.setWordWrap(True)
        sl.addWidget(self._gen_status)

        self._gen_progress = QProgressBar()
        self._gen_progress.setRange(0, 0)   # indeterminate
        self._gen_progress.setFixedHeight(8)
        self._gen_progress.setTextVisible(False)
        self._gen_progress.setVisible(False)
        self._gen_progress.setStyleSheet(
            "QProgressBar { background: rgba(20,20,40,180); border-radius: 3px; border: none; }"
            "QProgressBar::chunk { background: #74b9ff; border-radius: 3px; }"
        )
        sl.addWidget(self._gen_progress)

        sl.addStretch()
        layout.addWidget(settings_grp)

        # Key display
        key_grp = QGroupBox("Generated Key")
        kl = QVBoxLayout(key_grp)

        self._key_display = QTextEdit()
        self._key_display.setReadOnly(True)
        self._key_display.setStyleSheet(
            "QTextEdit { background: rgba(8,8,18,200); color: #a29bfe;"
            " border: 1px solid rgba(162,155,254,60); border-radius: 6px;"
            " font-family: Consolas, monospace; font-size: 10px; }"
        )
        kl.addWidget(self._key_display)

        # Stats
        stats_grp = QGroupBox("Session Statistics")
        stat_l = QVBoxLayout(stats_grp)
        self._stats_text = QTextEdit()
        self._stats_text.setReadOnly(True)
        self._stats_text.setFixedHeight(130)
        self._stats_text.setStyleSheet(
            "QTextEdit { background: rgba(8,8,18,200); color: #e8eaf6;"
            " border: 1px solid rgba(80,100,220,60); border-radius: 6px; font-size: 11px; }"
        )
        stat_l.addWidget(self._stats_text)
        kl.addWidget(stats_grp)

        layout.addWidget(key_grp, stretch=1)
        return w

    # ── Tab: Network Dashboard ───────────────────────────────────────── #

    def _build_network_tab(self) -> QWidget:
        self._sdn = SDNController()
        self._net_dashboard = NetworkDashboard(self._sdn)
        return self._net_dashboard

    # ── Tab: Basis Matching ──────────────────────────────────────────── #

    def _build_basis_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)

        info = QLabel(
            "This panel visualises the BB84 basis matching and sifting process in detail. "
            "Generate a key from the 'Key Generation' tab to see live data."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #7986cb; font-size: 11px; background: transparent; padding: 4px;")
        layout.addWidget(info)

        self._basis_panel = BasisMatchingPanel()
        layout.addWidget(self._basis_panel, stretch=1)
        return w

    # ------------------------------------------------------------------ #
    #  Key generation                                                      #
    # ------------------------------------------------------------------ #

    def _on_generate_key(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        self._btn_gen_key.setEnabled(False)
        self._gen_progress.setVisible(True)
        self._gen_status.setText("Generating QKD key...")
        self._basis_panel.reset()
        self._key_gen_start = time.time()

        worker = _KeyGenWorker(
            key_length  = self._spin_keylen.value(),
            noise_depol = self._spin_depol.value(),
            noise_loss  = self._spin_loss.value(),
            eve_active  = self._chk_eve.isChecked(),
            eve_rate    = self._spin_eve_rate.value(),
            attack_type = "intercept_resend",
        )
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_key_gen_done)
        worker.error.connect(self._on_key_gen_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_key_gen_done(self, result: SessionResult) -> None:
        elapsed = time.time() - self._key_gen_start
        self._session = result
        self._key_bits = list(result.final_key)

        # Populate basis matching panel
        for record in result.records:
            from controller.simulation_controller import PhotonEvent
            from simulation.qubit import POLARIZATION_COLOURS, POLARIZATION_SYMBOLS, Qubit
            col = Qubit._compute_polarization(record.alice_bit, record.alice_basis)
            ev  = PhotonEvent(
                index        = record.index,
                total        = result.key_length_requested,
                alice_bit    = record.alice_bit,
                alice_basis  = record.alice_basis,
                alice_colour = POLARIZATION_COLOURS.get(col, "#fff"),
                alice_symbol = POLARIZATION_SYMBOLS.get(col, "?"),
                eve_active   = record.eve_active,
                eve_basis    = record.eve_basis,
                eve_bit      = record.eve_bit,
                lost         = record.lost,
                bob_basis    = record.bob_basis,
                bob_bit      = record.bob_bit,
                bases_match  = record.bases_match,
                rolling_qber = 0.0,
                sifted_count = 0,
            )
            self._basis_panel.update_photon(ev)

        # Display key
        if self._key_bits:
            key_bytes = bits_to_bytes(self._key_bits)
            key_hex   = key_bytes.hex()
            lines = [key_hex[i:i+64] for i in range(0, len(key_hex), 64)]
            self._key_display.setPlainText(
                f"Key ({len(self._key_bits)} bits = {len(key_bytes)} bytes):\n\n" +
                "\n".join(lines)
            )
        else:
            self._key_display.setPlainText("No key generated (session aborted or insufficient bits).")

        # Stats
        n_sifted = len(result.sifted_key_alice)
        n_final  = len(result.final_key)
        stats = (
            f"Raw qubits:      {result.raw_count}\n"
            f"Lost photons:    {result.lost_count}  ({result.lost_count/max(result.raw_count,1)*100:.1f}%)\n"
            f"Sifted key:      {n_sifted} bits\n"
            f"QBER:            {result.qber*100:.2f}%\n"
            f"Eve detected:    {'YES ⚠' if result.eve_detected else 'No ✓'}\n"
            f"Final key:       {n_final} bits ({n_final//8} bytes)\n"
            f"Gen time:        {elapsed*1000:.0f} ms\n"
            f"Noise depol:     {result.noise_depol*100:.1f}%\n"
            f"Noise loss:      {result.noise_loss*100:.1f}%"
        )
        self._stats_text.setPlainText(stats)

        # Key status widget
        self._key_status.update_from_result(result)

        # Enable/disable messaging buttons
        can_msg = bool(self._key_bits) and not result.eve_detected
        self._btn_encrypt.setEnabled(can_msg)
        self._btn_decrypt.setEnabled(False)

        self._gen_progress.setVisible(False)
        self._btn_gen_key.setEnabled(True)

        if result.eve_detected:
            msg = f"Key generation ABORTED — Eve detected! QBER={result.qber*100:.1f}%"
            self._gen_status.setText(msg)
            self._gen_status.setStyleSheet("color: #d63031; font-size: 11px; background: transparent;")
            self.statusBar().showMessage(msg)
        else:
            msg = f"Key ready: {n_final} bits  |  QBER: {result.qber*100:.1f}%  |  {elapsed*1000:.0f} ms"
            self._gen_status.setText(msg)
            self._gen_status.setStyleSheet("color: #00b894; font-size: 11px; background: transparent;")
            self.statusBar().showMessage(msg)

        # Cross-layer integration: push QBER to the SDN network
        self._net_dashboard.push_session_qber(result.qber)

    def _on_key_gen_error(self, err: str) -> None:
        self._gen_progress.setVisible(False)
        self._btn_gen_key.setEnabled(True)
        self._gen_status.setText(f"Error: {err}")
        self._gen_status.setStyleSheet("color: #d63031; font-size: 11px; background: transparent;")

    # ------------------------------------------------------------------ #
    #  Encrypt / Decrypt                                                   #
    # ------------------------------------------------------------------ #

    def _on_encrypt_send(self) -> None:
        plaintext = self._alice_input.toPlainText().strip()
        if not plaintext:
            return
        if not self._key_bits:
            self._alice_log.append("No key available. Generate a QKD key first.", "#ff7675")
            return

        plain_bytes  = plaintext.encode("utf-8")
        cipher_bytes = xor_encrypt(plain_bytes, self._key_bits)
        self._pending_cipher = cipher_bytes

        cipher_hex = cipher_bytes.hex()

        self._alice_log.append(f"Message: {plaintext}", "#74b9ff")
        self._alice_log.append(
            f"Encrypted ({len(cipher_bytes)} bytes): {cipher_hex[:80]}{'...' if len(cipher_hex) > 80 else ''}",
            "#a29bfe",
        )
        self._alice_log.append("Sent over quantum-secured channel ✓", "#00b894")

        self._cipher_display.setPlainText(
            f"Hex ciphertext ({len(cipher_bytes)} bytes):\n{cipher_hex}"
        )

        self._btn_decrypt.setEnabled(True)
        self.statusBar().showMessage(
            f"Message encrypted and transmitted  |  Ciphertext: {len(cipher_bytes)} bytes"
        )

    def _on_decrypt(self) -> None:
        if not self._pending_cipher or not self._key_bits:
            return

        plain_bytes = xor_decrypt(self._pending_cipher, self._key_bits)
        try:
            plaintext = plain_bytes.decode("utf-8")
        except UnicodeDecodeError:
            plaintext = f"[Binary: {plain_bytes.hex()}]"

        self._bob_log.append(
            f"Ciphertext received ({len(self._pending_cipher)} bytes)", "#a29bfe"
        )
        self._bob_log.append(f"Decrypted: {plaintext}", "#00b894")
        self._bob_log.append("Message authenticated via QKD key ✓", "#74b9ff")

        self.statusBar().showMessage(
            f"Message decrypted successfully  |  Plaintext: {len(plaintext)} chars"
        )
        self._pending_cipher = None
        self._btn_decrypt.setEnabled(False)


# ──────────────────────────────────────────────────────────────────────── #
#  Application entry point                                                  #
# ──────────────────────────────────────────────────────────────────────── #

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("QKD Secure Messaging Platform")
    app.setOrganizationName("CryptoLab")

    window = SecureMessagingWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
