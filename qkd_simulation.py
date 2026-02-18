"""
This module simulates the BB84 Quantum Key Distribution (QKD) protocol.

It includes classes for representing quantum states (photons) and the entities
involved in the protocol: Alice (the sender), Bob (the receiver), and Eve
(the eavesdropper).

The simulation demonstrates how Alice and Bob can agree on a shared secret key
while also detecting the presence of an eavesdropper.
"""

import random

class Photon:
    """Represents a single photon with a specific polarization."""
    def __init__(self, bit=None, basis=None):
        self.bit = bit
        self.basis = basis  # '+' for rectilinear, 'x' for diagonal
        self.polarization = None
        if bit is not None and basis is not None:
            self.encode(bit, basis)

    def encode(self, bit, basis):
        """Sets the photon's polarization based on a bit and a basis."""
        self.bit = bit
        self.basis = basis
        if basis == '+':  # Rectilinear basis
            self.polarization = 0 if bit == 0 else 90
        elif basis == 'x':  # Diagonal basis
            self.polarization = 45 if bit == 0 else 135

    def measure(self, basis):
        """Measures the photon's bit value using a given basis."""
        if self.basis == basis:
            # Correct basis measurement, no change
            return self.bit
        else:
            # Incorrect basis measurement, outcome is random
            # This also changes the photon's state
            measured_bit = random.randint(0, 1)
            self.encode(measured_bit, basis)
            return measured_bit

    def __repr__(self):
        return f"Photon(bit={self.bit}, basis='{self.basis}', pol={self.polarization}°)"

class Alice:
    """The sender of the photons."""
    def __init__(self, key_length):
        self.key_length = key_length
        self.bits = []
        self.bases = []
        self.photons = []

    def generate_photons(self):
        """Generates a sequence of photons based on random bits and bases."""
        self.bits = [random.randint(0, 1) for _ in range(self.key_length)]
        self.bases = [random.choice(['+', 'x']) for _ in range(self.key_length)]
        self.photons = [Photon(self.bits[i], self.bases[i]) for i in range(self.key_length)]
        return self.photons

class Bob:
    """The receiver of the photons."""
    def __init__(self, key_length):
        self.key_length = key_length
        self.bases = []
        self.measured_bits = []

    def measure_photons(self, photons):
        """Measures a sequence of photons using random bases."""
        self.bases = [random.choice(['+', 'x']) for _ in range(len(photons))]
        self.measured_bits = [photons[i].measure(self.bases[i]) for i in range(len(photons))]

class Eve:
    """The eavesdropper who tries to intercept and measure the photons."""
    def __init__(self, key_length):
        self.key_length = key_length
        self.bases = []
        self.intercepted_bits = []

    def intercept_and_resend(self, photons):
        """Intercepts photons, measures them with random bases, and resends new ones."""
        self.bases = [random.choice(['+', 'x']) for _ in range(len(photons))]
        
        new_photons = []
        for i, photon in enumerate(photons):
            # Eve measures the photon
            intercepted_bit = photon.measure(self.bases[i])
            self.intercepted_bits.append(intercepted_bit)
            
            # Eve creates a new photon based on her measurement and sends it to Bob
            new_photon = Photon(intercepted_bit, self.bases[i])
            new_photons.append(new_photon)
            
        return new_photons

def compare_bases(alice_bases, bob_bases):
    """Compares Alice's and Bob's bases to find matches."""
    matching_indices = [i for i, (b1, b2) in enumerate(zip(alice_bases, bob_bases)) if b1 == b2]
    return matching_indices

def sift_key(bits, indices):
    """Sifts a key based on a list of matching indices."""
    return [bits[i] for i in indices]

def calculate_qber(alice_key, bob_key):
    """Calculates the Quantum Bit Error Rate (QBER)."""
    if not alice_key:
        return 0.0
    errors = sum(1 for a, b in zip(alice_key, bob_key) if a != b)
    return errors / len(alice_key)
