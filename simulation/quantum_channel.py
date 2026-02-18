"""
Quantum channel with configurable noise sources:
  - Depolarization  : random bit-flip with probability p_depol
  - Photon loss     : photon is dropped with probability p_loss
  - Dark counts     : phantom photon appears with probability p_dark
"""
import random
from dataclasses import dataclass, field
from typing import Optional

from .qubit import Qubit


@dataclass
class NoiseModel:
    """All noise parameters in one place.  All values are probabilities [0, 1]."""
    depolarization: float = 0.02   # bit-flip noise per transmitted photon
    photon_loss: float    = 0.05   # probability that a photon is lost in transit
    dark_count: float     = 0.001  # probability of a spurious detector click

    def apply(self, qubit: Qubit) -> Optional[Qubit]:
        """
        Applies noise to *qubit* and returns the (possibly modified) qubit,
        or None if the photon was lost.
        """
        # Photon loss — return None to signal the photon never arrived
        if random.random() < self.photon_loss:
            return None

        # Depolarization — flip the bit
        if random.random() < self.depolarization:
            flipped = Qubit(bit=qubit.bit ^ 1, basis=qubit.basis)
            return flipped

        # Dark count — replace with a completely random qubit
        if random.random() < self.dark_count:
            return Qubit.random()

        return qubit


class QuantumChannel:
    """Models the physical (simulated) quantum channel between Alice and Bob."""

    def __init__(self, noise_model: Optional[NoiseModel] = None):
        self.noise_model = noise_model or NoiseModel()

    def transmit(self, qubit: Qubit) -> Optional[Qubit]:
        """
        Transmits *qubit* through the channel, applying noise.
        Returns the qubit as received (possibly altered), or None if lost.
        """
        return self.noise_model.apply(qubit)
