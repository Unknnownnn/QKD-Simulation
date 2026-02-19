"""
attacks.py
==========
Advanced eavesdropping attack models for QKD BB84 simulation.

Supported attacks:
  1. InterceptResendAttack   – Eve measures each photon and re-emits.
  2. PhotonNumberSplitting   – Eve exploits multi-photon pulses (simulated).
  3. TrojanHorseAttack       – Eve injects a probe into Alice's device.

Each attack exposes:
  - apply(qubit, alice_basis) -> (qubit_out, AttackRecord)

AttackRecord holds metadata for visualisation and analytics.
"""
from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

from .qubit import Qubit


# ──────────────────────────────────────────────────────────────────────── #
#  Per-photon attack record (carried through to SessionResult)             #
# ──────────────────────────────────────────────────────────────────────── #

@dataclass
class AttackRecord:
    attack_type: str           # "intercept_resend" | "pns" | "trojan_horse" | "none"
    intercepted: bool = False

    # Intercept-resend specific
    eve_basis: Optional[str]  = None
    eve_bit:   Optional[int]  = None
    basis_match: bool         = False  # whether Eve guessed Alice's basis

    # PNS specific
    split_photon: bool = False         # True if a copy was split off
    pns_info_gain: float = 0.0         # fraction of bit info gained [0,1]

    # Trojan horse specific
    probe_reflected: bool = False      # probe signal came back
    settings_leaked: bool = False      # Alice's device settings were exposed

    # QBER contribution
    introduced_error: bool = False


# ──────────────────────────────────────────────────────────────────────── #
#  1. Intercept-Resend Attack                                               #
# ──────────────────────────────────────────────────────────────────────── #

class InterceptResendAttack:
    """
    Classic intercept-resend attack.
    Eve measures every intercepted photon with a random basis,
    then re-emits a fresh photon matching her result.

    QBER contribution:
      Each intercepted photon has a 25% chance of introducing an error
      (Eve guesses Alice's basis wrong 50% of the time; Bob then gets
       a random outcome, causing another 50% error — combined: 25%).
    """

    def __init__(self, intercept_rate: float = 1.0):
        """
        Args:
            intercept_rate: Fraction of photons Eve intercepts [0, 1].
        """
        self.intercept_rate = max(0.0, min(1.0, intercept_rate))

    def apply(self, qubit: Qubit) -> Tuple[Qubit, AttackRecord]:
        """
        Returns the (possibly modified) qubit and an AttackRecord.
        If not intercepted, the original qubit is returned unchanged.
        """
        rec = AttackRecord(attack_type="intercept_resend")

        if random.random() > self.intercept_rate:
            return qubit, rec   # Eve doesn't intercept this one

        rec.intercepted = True
        eve_basis  = random.choice(['+', 'x'])
        eve_bit    = qubit.measure(eve_basis)
        rec.eve_basis   = eve_basis
        rec.eve_bit     = eve_bit
        rec.basis_match = (eve_basis == qubit.basis)

        # Re-emit a fresh qubit based on Eve's measured result
        new_qubit = Qubit(bit=eve_bit, basis=eve_basis)

        # Error is introduced when Eve's basis != Alice's basis
        # (re-emitted qubit is in Eve's basis; Bob sees a 50/50 outcome)
        rec.introduced_error = not rec.basis_match

        return new_qubit, rec

    @property
    def expected_qber_contribution(self) -> float:
        """Theoretical QBER increase = intercept_rate × 0.25"""
        return self.intercept_rate * 0.25


# ──────────────────────────────────────────────────────────────────────── #
#  2. Photon Number Splitting Attack                                        #
# ──────────────────────────────────────────────────────────────────────── #

class PhotonNumberSplittingAttack:
    """
    Photon Number Splitting (PNS) attack.

    In real QKD, coherent laser pulses occasionally contain more than one
    photon.  Eve can:
      1. Split off the extra photon(s) while letting one through to Bob.
      2. Store the split photon and measure it after basis reconciliation
         is public — gaining full information with no QBER increase.

    Here we model it probabilistically:
      - multi_photon_rate: probability that a pulse contains >1 photon.
      - When split, Eve stores a copy and gains complete key information.
      - Single-photon pulses pass untouched (PNS cannot attack them).
      - Because Eve lets one photon through, QBER stays near 0%!

    Detection mechanism: reduced key rate. If Eve blocks all single-photon
    pulses and only multi-photon pulses reach Bob, the key rate drops
    dramatically. This is detectable via key-rate analysis.
    """

    def __init__(
        self,
        multi_photon_rate: float = 0.15,
        block_single_photon: bool = True,
    ):
        """
        Args:
            multi_photon_rate:    Fraction of pulses that are multi-photon.
            block_single_photon:  If True Eve blocks single-photon pulses
                                  (lowers key rate; raises suspicion).
        """
        self.multi_photon_rate    = max(0.0, min(1.0, multi_photon_rate))
        self.block_single_photon  = block_single_photon

    def apply(self, qubit: Qubit) -> Tuple[Optional[Qubit], AttackRecord]:
        """
        Returns (qubit_or_None, record).
        None means the photon was blocked (simulates photon loss from PNS).
        """
        rec = AttackRecord(attack_type="pns")

        is_multi = random.random() < self.multi_photon_rate

        if is_multi:
            # Eve splits the extra photon — she stores a copy, lets one through
            rec.intercepted    = True
            rec.split_photon   = True
            rec.pns_info_gain  = 1.0   # complete information after public reconciliation
            rec.introduced_error = False   # QBER stays clean
            return qubit, rec          # qubit passes through to Bob unchanged

        else:
            # Single-photon pulse — Eve cannot split it
            if self.block_single_photon:
                # Eve blocks to prevent Bob from noticing the single-photon baseline
                rec.intercepted = True
                rec.introduced_error = False
                return None, rec       # None = photon lost (increases loss rate)
            return qubit, rec          # Not attacked

    @property
    def expected_qber_contribution(self) -> float:
        """PNS introduces NO direct QBER increase — the attack is stealthy."""
        return 0.0

    @property
    def expected_key_rate_reduction(self) -> float:
        """
        Fraction by which the key rate drops when single photons are blocked.
        """
        if self.block_single_photon:
            return 1.0 - self.multi_photon_rate
        return 0.0


# ──────────────────────────────────────────────────────────────────────── #
#  3. Trojan Horse Attack                                                   #
# ──────────────────────────────────────────────────────────────────────── #

class TrojanHorseAttack:
    """
    Trojan Horse Attack (THA).

    Eve shines a bright probe light into Alice's optical apparatus.
    The reflected light reveals the internal setting of Alice's basis
    modulator without disturbing the transmitted photon.

    Key properties:
      - Does NOT disturb the quantum channel → QBER stays near 0%.
      - If successful, Eve learns Alice's basis for the intercepted pulses.
      - Defence: optical isolators at Alice's device input.

    Simulation:
      - probe_success_rate: probability that a probe yields Alice's basis.
      - When successful, Eve performs an optimal measurement later,
        gaining complete bit information for fully intercepted pulses.
    """

    def __init__(
        self,
        probe_success_rate: float = 0.40,
        subsequent_intercept: bool = True,
    ):
        """
        Args:
            probe_success_rate:    Prob. that the probe successfully reveals Alice's basis.
            subsequent_intercept:  If True, Eve also intercepts & resends photons
                                   where she learnt the basis (0% QBER due to correct basis).
        """
        self.probe_success_rate    = max(0.0, min(1.0, probe_success_rate))
        self.subsequent_intercept  = subsequent_intercept

    def apply(self, qubit: Qubit) -> Tuple[Qubit, AttackRecord]:
        """
        Returns (qubit, record).  The qubit may be replaced if subsequent
        interception succeeds (with correct basis → no QBER increase).
        """
        rec = AttackRecord(attack_type="trojan_horse")

        probe_reflected = random.random() < self.probe_success_rate

        if probe_reflected:
            rec.intercepted        = True
            rec.probe_reflected    = True
            rec.settings_leaked    = True
            rec.eve_basis          = qubit.basis   # Eve learns Alice's basis!
            rec.basis_match        = True

            if self.subsequent_intercept:
                # Eve measures with Alice's CORRECT basis → perfect recovery
                eve_bit          = qubit.measure(qubit.basis)
                rec.eve_bit      = eve_bit
                new_qubit        = Qubit(bit=eve_bit, basis=qubit.basis)
                rec.introduced_error = False       # no QBER increase — stealthy!
                return new_qubit, rec

        return qubit, rec

    @property
    def expected_qber_contribution(self) -> float:
        """Trojan Horse introduces NO QBER increase when using correct basis."""
        return 0.0


# ──────────────────────────────────────────────────────────────────────── #
#  Attack Registry                                                          #
# ──────────────────────────────────────────────────────────────────────── #

ATTACK_TYPES = {
    "intercept_resend": InterceptResendAttack,
    "pns":              PhotonNumberSplittingAttack,
    "trojan_horse":     TrojanHorseAttack,
}

ATTACK_LABELS = {
    "intercept_resend": "Intercept-Resend",
    "pns":              "Photon Number Splitting",
    "trojan_horse":     "Trojan Horse",
}

ATTACK_DESCRIPTIONS = {
    "intercept_resend": (
        "Eve measures each photon and re-emits a fresh one. "
        "Causes ~25% QBER increase at 100% intercept rate."
    ),
    "pns": (
        "Eve splits multi-photon pulses, gaining full key info "
        "with ZERO QBER increase. Detected via reduced key rate."
    ),
    "trojan_horse": (
        "Eve probes Alice's optical device to learn the basis "
        "setting. Zero QBER impact. Blocked by optical isolators."
    ),
}


def make_attack(attack_type: str, **kwargs):
    """Factory function — create an attack by name."""
    cls = ATTACK_TYPES.get(attack_type)
    if cls is None:
        raise ValueError(f"Unknown attack type: {attack_type!r}")
    return cls(**kwargs)
