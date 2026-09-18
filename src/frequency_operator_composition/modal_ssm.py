from __future__ import annotations

from typing import Literal, Sequence

import numpy as np

StateMode = Literal["local", "global", "frozen"]


class AdaptiveModalSSM:
    """Ordinary modal state-space attacker with no cable geometry.

    Each complex mode is two real fast state variables. One slow scalar belongs to
    each resident mode. A 32-mode instance therefore has 64 fast + 32 slow = 96
    real state variables, exactly matching the v1 cable cell's 64 fast (v,w) +
    32 compartment-local material states.

    The resident frequencies span a broad fixed band and are not set to the four
    task write frequencies. Slow state is indexed by resident mode, not by the
    requested carrier frequency.
    """

    def __init__(
        self,
        *,
        seed: int = 0,
        n_modes: int = 32,
        radius: float = 0.95,
        beta: float = 0.45,
        write_rate: float = 0.02,
        state_mode: StateMode = "local",
    ) -> None:
        if n_modes < 2:
            raise ValueError("n_modes must be >= 2")
        if state_mode not in ("local", "global", "frozen"):
            raise ValueError(f"unknown state_mode: {state_mode}")
        rng = np.random.default_rng(seed)

        self.seed = int(seed)
        self.n_modes = int(n_modes)
        self.centers = np.linspace(0.04, 0.54, self.n_modes)
        self.radii = np.clip(
            radius + rng.normal(0.0, 0.005, self.n_modes),
            0.90,
            0.98,
        )
        self.input_gain = rng.normal(1.0, 0.08, self.n_modes)
        self.output_gain = rng.normal(0.0, 1.0, self.n_modes)
        self.output_gain /= np.linalg.norm(self.output_gain)

        self.beta = float(beta)
        self.write_rate = float(write_rate)
        self.state_mode = state_mode
        self.z = np.zeros(self.n_modes, dtype=complex)
        self.slow = np.zeros(self.n_modes, dtype=float)

    @property
    def real_state_count(self) -> int:
        return 3 * self.n_modes

    def _effective_slow(self) -> np.ndarray:
        if self.state_mode == "frozen":
            return np.zeros_like(self.slow)
        if self.state_mode == "global":
            return np.full_like(self.slow, float(np.mean(self.slow)))
        return self.slow

    def poles(self) -> np.ndarray:
        return self.radii * np.exp(
            1j * (self.centers + self.beta * self._effective_slow())
        )

    def step(self, drive: float) -> float:
        self.z = self.poles() * self.z + self.input_gain * float(drive)

        energy = np.abs(self.z) ** 2
        bounded = energy / (1.0 + energy)
        self.slow += self.write_rate * bounded * (1.0 - self.slow)
        self.slow = np.clip(self.slow, 0.0, 1.0)

        return float(np.real(np.dot(self.output_gain, self.z)))

    def write(
        self,
        omega: float,
        *,
        amplitude: float = 0.04,
        duration: int = 200,
    ) -> None:
        for t in range(int(duration)):
            self.step(amplitude * np.sin(float(omega) * t))

    def settle(self, steps: int = 800) -> None:
        for _ in range(int(steps)):
            self.step(0.0)

    def transfer(self, omega: float) -> complex:
        z = np.exp(1j * float(omega))
        return complex(
            np.sum(
                self.output_gain
                * self.input_gain
                / (z - self.poles())
            )
        )

    def operator_vector(self, probes: Sequence[float]) -> np.ndarray:
        signature = np.asarray([self.transfer(float(w)) for w in probes], dtype=complex)
        return np.concatenate([signature.real, signature.imag])

    def address_profile(self, omega: float) -> np.ndarray:
        """Baseline resident-mode participation before any slow-state write."""
        z = np.exp(1j * float(omega))
        baseline_poles = self.radii * np.exp(1j * self.centers)
        response = np.abs(self.input_gain / (z - baseline_poles)) ** 2
        return response / max(float(np.sum(response)), 1e-15)

    def fast_norm(self) -> float:
        return float(np.linalg.norm(self.z))


def run_modal_sequence(
    order: Sequence[float],
    *,
    seed: int = 0,
    n_modes: int = 32,
    state_mode: StateMode = "local",
    radius: float = 0.95,
    beta: float = 0.45,
    write_rate: float = 0.02,
    amplitude: float = 0.04,
    duration: int = 200,
    settle_steps: int = 800,
) -> AdaptiveModalSSM:
    model = AdaptiveModalSSM(
        seed=seed,
        n_modes=n_modes,
        radius=radius,
        beta=beta,
        write_rate=write_rate,
        state_mode=state_mode,
    )
    for omega in order:
        model.write(omega, amplitude=amplitude, duration=duration)
        model.settle(settle_steps)
    return model
