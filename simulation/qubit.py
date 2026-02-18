"""
Qubit: represents a single quantum bit (photon) in the BB84 protocol.

Polarization map:
  Rectilinear (+) basis:  0° = bit 0,  90° = bit 1
  Diagonal    (×) basis: 45° = bit 0, 135° = bit 1
"""
import random


# Colours used by the animation canvas
POLARIZATION_COLOURS = {
    0.0:   "#74b9ff",   # →  blue
    90.0:  "#ff7675",   # ↑  red
    45.0:  "#55efc4",   # ↗  green
    135.0: "#fdcb6e",   # ↖  orange
}

POLARIZATION_SYMBOLS = {
    0.0:   "→",
    90.0:  "↑",
    45.0:  "↗",
    135.0: "↖",
}


class Qubit:
    """A single qubit encoded with a classical bit and a measurement basis."""

    def __init__(self, bit: int, basis: str):
        """
        Args:
            bit:   Classical bit value (0 or 1).
            basis: '+' for rectilinear, 'x' for diagonal.
        """
        assert bit in (0, 1), "Bit must be 0 or 1"
        assert basis in ('+', 'x'), "Basis must be '+' or 'x'"
        self.bit = bit
        self.basis = basis
        self.polarization = self._compute_polarization(bit, basis)

    # ------------------------------------------------------------------ #
    #  Factory                                                             #
    # ------------------------------------------------------------------ #
    @classmethod
    def random(cls) -> "Qubit":
        """Creates a qubit with a random bit and a random basis."""
        return cls(bit=random.randint(0, 1), basis=random.choice(['+', 'x']))

    # ------------------------------------------------------------------ #
    #  Quantum mechanics                                                   #
    # ------------------------------------------------------------------ #
    def measure(self, measurement_basis: str) -> int:
        """
        Returns the measured bit when Bob (or Eve) uses *measurement_basis*.

        If the bases match, the correct bit is returned deterministically.
        If they differ, the outcome is random (50 / 50) — this is the core
        of the BB84 security argument.
        """
        if self.basis == measurement_basis:
            return self.bit
        return random.randint(0, 1)

    # ------------------------------------------------------------------ #
    #  Properties                                                          #
    # ------------------------------------------------------------------ #
    @property
    def colour(self) -> str:
        return POLARIZATION_COLOURS.get(self.polarization, "#ffffff")

    @property
    def symbol(self) -> str:
        return POLARIZATION_SYMBOLS.get(self.polarization, "?")

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _compute_polarization(bit: int, basis: str) -> float:
        if basis == '+':
            return 0.0 if bit == 0 else 90.0
        return 45.0 if bit == 0 else 135.0

    def __repr__(self) -> str:
        return (
            f"Qubit(bit={self.bit}, basis='{self.basis}', "
            f"pol={self.polarization}°, {self.symbol})"
        )
