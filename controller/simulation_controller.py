"""
SimulationController
====================
Sits between the simulation engine and the UI.

It owns:
  - A BB84Protocol instance
  - A QTimer that drives the step-by-step animated loop
  - PyQt signals that the UI connects to

The UI controls *what* parameters to use; the controller drives *when* each
photon is processed and emits events the animation canvas and charts respond to.
"""
from dataclasses import dataclass
from typing import List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from simulation.bb84 import BB84Protocol
from simulation.quantum_channel import NoiseModel
from simulation.session_result import PhotonRecord, SessionResult


# ------------------------------------------------------------------ #
#  Data objects carried by signals                                       #
# ------------------------------------------------------------------ #
@dataclass
class PhotonEvent:
    """Snapshot of a single processed photon, emitted after each step."""
    index: int
    total: int
    alice_bit: int
    alice_basis: str
    alice_colour: str       # hex colour for the animation
    alice_symbol: str       # ↑ → ↗ ↖

    eve_active: bool
    eve_basis: Optional[str]
    eve_bit: Optional[int]

    lost: bool
    bob_basis: Optional[str]
    bob_bit: Optional[int]
    bases_match: bool

    rolling_qber: float     # QBER computed up to this photon (sifted key)
    sifted_count: int       # number of sifted-key bits so far


@dataclass
class SessionSummary:
    """Emitted once when the session finishes."""
    raw_count: int
    lost_count: int
    sifted_length: int
    qber: float
    eve_detected: bool
    final_key_length: int
    final_key_hex: str
    qber_history: List[float]


# ------------------------------------------------------------------ #
#  Controller                                                          #
# ------------------------------------------------------------------ #
class SimulationController(QObject):

    # ---- Signals ----
    photon_processed = pyqtSignal(object)   # PhotonEvent
    qber_updated     = pyqtSignal(float)    # current rolling QBER
    progress_updated = pyqtSignal(int, int) # (done, total)
    session_complete = pyqtSignal(object)   # SessionSummary
    simulation_reset = pyqtSignal()
    log_message      = pyqtSignal(str)      # status-log text

    # ---- Default animation speed (ms between photons) ----
    DEFAULT_INTERVAL_MS = 80

    def __init__(self, parent=None):
        super().__init__(parent)

        self._protocol: Optional[BB84Protocol] = None
        self._session_result: Optional[SessionResult] = None

        # Running stats (updated each step)
        self._sifted_alice:  List[int] = []
        self._sifted_bob:    List[int] = []
        self._error_count:   int = 0

        # Timer drives the step loop
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        # Settings (updated by control panel before clicking Run)
        self.key_length:        int   = 100
        self.eve_active:        bool  = False
        self.eve_intercept_rate: float = 1.0
        self.noise_depol:       float = 0.02
        self.noise_loss:        float = 0.05
        self.noise_dark:        float = 0.001
        self.speed_ms:          int   = self.DEFAULT_INTERVAL_MS

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Prepare a new session and start the step timer."""
        if self._timer.isActive():
            return

        noise = NoiseModel(
            depolarization=self.noise_depol,
            photon_loss=self.noise_loss,
            dark_count=self.noise_dark,
        )
        self._protocol = BB84Protocol(
            key_length=self.key_length,
            noise_model=noise,
            eve_active=self.eve_active,
            eve_intercept_rate=self.eve_intercept_rate,
        )
        self._protocol.prepare()
        self._sifted_alice = []
        self._sifted_bob = []
        self._error_count = 0

        self.log_message.emit(
            f"Session started — {self.key_length} qubits, "
            f"Eve={'ON' if self.eve_active else 'OFF'}, "
            f"noise={self.noise_depol:.1%}"
        )
        self._timer.start(self.speed_ms)

    def pause(self) -> None:
        self._timer.stop()
        self.log_message.emit("Paused.")

    def resume(self) -> None:
        if self._protocol and not self._protocol.is_complete:
            self._timer.start(self.speed_ms)
            self.log_message.emit("Resumed.")

    def step_once(self) -> None:
        """Process exactly one photon (for step-through mode)."""
        self._timer.stop()
        self._on_tick()

    def reset(self) -> None:
        self._timer.stop()
        self._protocol = None
        self._sifted_alice = []
        self._sifted_bob = []
        self._error_count = 0
        self.simulation_reset.emit()
        self.log_message.emit("Reset.")

    def set_speed(self, ms: int) -> None:
        self.speed_ms = max(10, ms)
        if self._timer.isActive():
            self._timer.setInterval(self.speed_ms)

    # ------------------------------------------------------------------ #
    #  Internal tick                                                       #
    # ------------------------------------------------------------------ #
    def _on_tick(self) -> None:
        if self._protocol is None:
            self._timer.stop()
            return

        record: Optional[PhotonRecord] = self._protocol.step()

        if record is None:
            # All photons done
            self._timer.stop()
            self._finish_session()
            return

        # Update sifted-key running stats
        if not record.lost and record.bases_match:
            self._sifted_alice.append(record.alice_bit)
            self._sifted_bob.append(record.bob_bit)
            if record.alice_bit != record.bob_bit:
                self._error_count += 1

        sifted_count = len(self._sifted_alice)
        rolling_qber = self._error_count / sifted_count if sifted_count > 0 else 0.0

        # Build and emit the photon event
        from simulation.qubit import Qubit
        col = Qubit._compute_polarization(record.alice_bit, record.alice_basis)
        from simulation.qubit import POLARIZATION_COLOURS, POLARIZATION_SYMBOLS

        event = PhotonEvent(
            index        = record.index,
            total        = self._protocol.steps_total,
            alice_bit    = record.alice_bit,
            alice_basis  = record.alice_basis,
            alice_colour = POLARIZATION_COLOURS.get(col, "#ffffff"),
            alice_symbol = POLARIZATION_SYMBOLS.get(col, "?"),
            eve_active   = record.eve_active,
            eve_basis    = record.eve_basis,
            eve_bit      = record.eve_bit,
            lost         = record.lost,
            bob_basis    = record.bob_basis,
            bob_bit      = record.bob_bit,
            bases_match  = record.bases_match,
            rolling_qber = rolling_qber,
            sifted_count = sifted_count,
        )
        self.photon_processed.emit(event)
        self.qber_updated.emit(rolling_qber)
        self.progress_updated.emit(record.index + 1, self._protocol.steps_total)

    def _finish_session(self) -> None:
        result = self._protocol.summarise()
        self._session_result = result

        key_hex = ""
        if result.final_key:
            # Convert bit list to hex string
            as_int = int(''.join(map(str, result.final_key)), 2)
            key_hex = hex(as_int)[2:].upper()

        summary = SessionSummary(
            raw_count        = result.raw_count,
            lost_count       = result.lost_count,
            sifted_length    = len(result.sifted_key_alice),
            qber             = result.qber,
            eve_detected     = result.eve_detected,
            final_key_length = len(result.final_key),
            final_key_hex    = key_hex,
            qber_history     = result.qber_history,
        )
        self.session_complete.emit(summary)

        status = "Eve DETECTED -- session aborted!" if result.eve_detected else "Secure key established."
        self.log_message.emit(
            f"Session complete. QBER={result.qber:.1%}. "
            f"Sifted key: {len(result.sifted_key_alice)} bits. {status}"
        )
