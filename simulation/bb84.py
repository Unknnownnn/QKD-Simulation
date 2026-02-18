"""
BB84Protocol: orchestrates one complete BB84 QKD session.

The protocol can run in two modes:
  1. full_run()   – processes all qubits at once and returns a SessionResult.
  2. step()       – processes one qubit at a time (used by the animated GUI).
"""
import random
import hashlib
from typing import List, Optional

from .qubit import Qubit
from .quantum_channel import QuantumChannel, NoiseModel
from .session_result import SessionResult, PhotonRecord


QBER_ABORT_THRESHOLD = 0.11   # 11 % — standard BB84 security threshold


class BB84Protocol:
    """Full implementation of the BB84 QKD protocol."""

    def __init__(
        self,
        key_length: int = 100,
        noise_model: Optional[NoiseModel] = None,
        eve_active: bool = False,
        eve_intercept_rate: float = 1.0,
    ):
        self.key_length = key_length
        self.noise_model = noise_model or NoiseModel()
        self.eve_active = eve_active
        self.eve_intercept_rate = eve_intercept_rate

        self._channel = QuantumChannel(self.noise_model)

        # --- Step-mode state ---
        self._alice_qubits: List[Qubit] = []
        self._bob_bases: List[str] = []
        self._records: List[PhotonRecord] = []
        self._step_index: int = 0
        self._prepared: bool = False

    # ------------------------------------------------------------------ #
    #  Preparation                                                         #
    # ------------------------------------------------------------------ #
    def prepare(self) -> None:
        """Alice prepares all qubits and Bob pre-selects his random bases."""
        self._alice_qubits = [Qubit.random() for _ in range(self.key_length)]
        self._bob_bases = [random.choice(['+', 'x']) for _ in range(self.key_length)]
        self._records = []
        self._step_index = 0
        self._prepared = True

    # ------------------------------------------------------------------ #
    #  Step-by-step mode (used by animated GUI)                           #
    # ------------------------------------------------------------------ #
    def step(self) -> Optional[PhotonRecord]:
        """
        Processes the next photon in the sequence.
        Returns a PhotonRecord, or None when the sequence is exhausted.
        """
        if not self._prepared:
            self.prepare()

        if self._step_index >= self.key_length:
            return None

        idx = self._step_index
        alice_q = self._alice_qubits[idx]
        bob_basis = self._bob_bases[idx]

        record = self._process_photon(idx, alice_q, bob_basis)
        self._records.append(record)
        self._step_index += 1
        return record

    @property
    def steps_done(self) -> int:
        return self._step_index

    @property
    def steps_total(self) -> int:
        return self.key_length

    @property
    def is_complete(self) -> bool:
        return self._step_index >= self.key_length

    # ------------------------------------------------------------------ #
    #  Full-run mode                                                       #
    # ------------------------------------------------------------------ #
    def full_run(self) -> SessionResult:
        """Runs the entire BB84 session at once and returns a SessionResult."""
        self.prepare()
        while not self.is_complete:
            self.step()
        return self.summarise()

    # ------------------------------------------------------------------ #
    #  Summarise results                                                   #
    # ------------------------------------------------------------------ #
    def summarise(self) -> SessionResult:
        """Computes sifted key, QBER, and final key from recorded steps."""
        result = SessionResult(
            key_length_requested=self.key_length,
            records=list(self._records),
            eve_active=self.eve_active,
            noise_depol=self.noise_model.depolarization,
            noise_loss=self.noise_model.photon_loss,
        )

        result.raw_count = len(self._records)
        result.lost_count = sum(1 for r in self._records if r.lost)

        # Build sifted keys — keep only bits where bases matched and photon arrived
        sifted_alice = []
        sifted_bob   = []
        for r in self._records:
            if not r.lost and r.bases_match:
                sifted_alice.append(r.alice_bit)
                sifted_bob.append(r.bob_bit)
                r.is_error = (r.alice_bit != r.bob_bit)

        result.sifted_key_alice = sifted_alice
        result.sifted_key_bob   = sifted_bob
        result.qber = _calculate_qber(sifted_alice, sifted_bob)
        result.eve_detected = result.qber > QBER_ABORT_THRESHOLD

        # Rolling QBER history for the chart
        errors, compared = 0, 0
        for a, b in zip(sifted_alice, sifted_bob):
            compared += 1
            if a != b:
                errors += 1
            result.qber_history.append(errors / compared if compared else 0.0)

        # Privacy amplification (only if session is not aborted)
        if not result.eve_detected and sifted_alice:
            result.final_key = _privacy_amplification(sifted_alice)
        else:
            result.final_key = []

        return result

    # ------------------------------------------------------------------ #
    #  Internal: per-photon processing                                     #
    # ------------------------------------------------------------------ #
    def _process_photon(self, idx: int, alice_q: Qubit, bob_basis: str) -> PhotonRecord:
        record = PhotonRecord(
            index=idx,
            alice_bit=alice_q.bit,
            alice_basis=alice_q.basis,
            eve_active=self.eve_active,
        )

        transmitted_q = alice_q

        # --- Eve intercepts (optional) ---
        if self.eve_active and random.random() < self.eve_intercept_rate:
            eve_basis = random.choice(['+', 'x'])
            eve_bit   = transmitted_q.measure(eve_basis)
            record.eve_basis = eve_basis
            record.eve_bit   = eve_bit
            # Eve re-emits a new qubit based on what she measured
            transmitted_q = Qubit(bit=eve_bit, basis=eve_basis)

        # --- Quantum channel (noise / loss) ---
        transmitted_q = self._channel.transmit(transmitted_q)

        if transmitted_q is None:
            record.lost = True
            record.bob_basis = bob_basis
            return record

        # --- Bob measures ---
        bob_bit        = transmitted_q.measure(bob_basis)
        record.bob_basis   = bob_basis
        record.bob_bit     = bob_bit
        record.bases_match = (alice_q.basis == bob_basis)

        return record


# ------------------------------------------------------------------ #
#  Pure functions                                                      #
# ------------------------------------------------------------------ #
def _calculate_qber(alice_key: List[int], bob_key: List[int]) -> float:
    if not alice_key:
        return 0.0
    errors = sum(1 for a, b in zip(alice_key, bob_key) if a != b)
    return errors / len(alice_key)


def _privacy_amplification(sifted_key: List[int]) -> List[int]:
    """
    Applies SHA-256 compression to remove any partial information Eve may
    have gained.  Returns a shorter but provably secure bit string.
    """
    if not sifted_key:
        return []
    as_int   = int(''.join(map(str, sifted_key)), 2)
    as_bytes = as_int.to_bytes((len(sifted_key) + 7) // 8, byteorder='big')
    digest   = hashlib.sha256(as_bytes).digest()
    bits = []
    for byte in digest:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    # Return half the sifted key length or 256 bits, whichever is smaller
    target = min(len(sifted_key) // 2, 256)
    return bits[:target]
