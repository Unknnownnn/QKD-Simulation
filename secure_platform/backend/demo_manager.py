"""
demo_manager.py — Guided demonstration mode controller.
Runs a 6-step demo: secure chat → Eve attack → QBER spike → 
smart routing → maintained comms → key regeneration.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from models import DemoStep, DemoState


def _make_steps() -> List[DemoStep]:
    return [
        DemoStep(
            step=1,
            title="Normal Secure Communication",
            description="Alice and Bob establish a QKD key and exchange encrypted messages securely.",
            action="normal_chat",
        ),
        DemoStep(
            step=2,
            title="Activate Eve (Eavesdropper)",
            description="An attacker (Eve) begins intercepting photons on the quantum channel using intercept-resend.",
            action="activate_eve",
        ),
        DemoStep(
            step=3,
            title="Observe QBER Increase",
            description="The QBER spikes above 11% threshold, indicating the presence of an eavesdropper.",
            action="observe_qber",
        ),
        DemoStep(
            step=4,
            title="Trigger Smart Routing",
            description="The SDN controller detects the attack and reroutes traffic through an alternate secure path.",
            action="smart_routing",
        ),
        DemoStep(
            step=5,
            title="Maintain Secure Communication",
            description="Communication continues uninterrupted over the new secure route.",
            action="maintain_comms",
        ),
        DemoStep(
            step=6,
            title="Regenerate Keys",
            description="Fresh QKD keys are generated on the new path. Old compromised keys are invalidated.",
            action="regen_keys",
        ),
    ]


class DemoManager:
    """Controls the guided demo mode."""

    def __init__(self):
        self._state = DemoState(steps=_make_steps(), total_steps=6)
        self._on_event: Optional[Callable] = None

    @property
    def state(self) -> DemoState:
        return self._state

    def start(self) -> DemoState:
        self._state = DemoState(
            running=True,
            current_step=0,
            total_steps=6,
            steps=_make_steps(),
            auto_advance=True,
        )
        return self._state

    def advance(self) -> Optional[DemoStep]:
        if not self._state.running:
            return None
        idx = self._state.current_step
        if idx >= self._state.total_steps:
            self._state.running = False
            return None

        step = self._state.steps[idx]
        step.status = "running"
        self._state.current_step = idx + 1
        return step

    def complete_step(self, step_num: int, data: Dict[str, Any] = {}):
        for s in self._state.steps:
            if s.step == step_num:
                s.status = "completed"
                s.data = data
                break

    def reset(self) -> DemoState:
        self._state = DemoState(steps=_make_steps(), total_steps=6)
        return self._state

    def get_current_step(self) -> Optional[DemoStep]:
        idx = self._state.current_step
        if 0 <= idx < self._state.total_steps:
            return self._state.steps[idx]
        return None
