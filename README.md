# Dynamic Mitigation of Quantum Side-Channel Attacks in Software-Defined QKD Networks

This project provides a Python simulation demonstrating how an SDN controller can monitor Quantum Bit Error Rate (QBER) and dynamically reroute traffic in a QKD network when a side-channel attack occurs, then restore optimal routing after recovery.

## Features
- Object-oriented classes for `QuantumLink`, `QuantumNode`, and `SDNController`.
- SDN controller sets link weights based on QBER and distance, and runs Dijkstra's algorithm.
- Attack injection (e.g., photon number splitting) raises QBER above the 11% threshold.
- One-tick rerouting latency modeled in the simulation.
- Visualization of throughput over time and optional network topology highlighting.

## Requirements
- Python 3.9+
- `networkx`, `matplotlib`

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python quantum_sdn_sim.py
```

On Windows with the configured virtual environment, the tool has already installed dependencies. If you prefer using the venv directly:

```bash
.cvenv\Scripts\python.exe quantum_sdn_sim.py
```

## Notes
- QBER threshold is 11% (no key generation above this).
- Reroute latency is one tick; throughput dips at attack start and stop.
- The research gap addressed is dynamic SDN-based mitigation rather than static routing in QKD.
