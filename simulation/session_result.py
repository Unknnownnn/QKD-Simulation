"""
Per-photon record and full session result dataclasses.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PhotonRecord:
    """Complete history for a single photon exchange."""
    index: int

    # Alice's side
    alice_bit: int
    alice_basis: str

    # Eve's side (if eavesdropping)
    eve_active: bool = False
    eve_basis: Optional[str] = None
    eve_bit: Optional[int] = None

    # Channel
    lost: bool = False                # photon was dropped by the channel

    # Bob's side
    bob_basis: Optional[str] = None
    bob_bit: Optional[int] = None    # None if lost

    # Reconciliation
    bases_match: bool = False
    is_error: bool = False           # mismatch between alice_bit and bob_bit (after sifting)

    @property
    def alice_polarization(self) -> float:
        from .qubit import Qubit
        return Qubit._compute_polarization(self.alice_bit, self.alice_basis)


@dataclass
class SessionResult:
    """Aggregated results for one complete BB84 session."""
    key_length_requested: int
    records: List[PhotonRecord] = field(default_factory=list)

    eve_active: bool = False
    noise_depol: float = 0.0
    noise_loss: float = 0.0

    # Derived — populated by BB84Protocol.summarise()
    raw_count: int = 0
    lost_count: int = 0
    sifted_key_alice: List[int] = field(default_factory=list)
    sifted_key_bob: List[int]   = field(default_factory=list)
    qber: float = 0.0
    final_key: List[int] = field(default_factory=list)
    eve_detected: bool = False
    qber_history: List[float] = field(default_factory=list)  # rolling QBER per photon
