from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

import numpy as np

StateMode = Literal["local", "global", "frozen"]


@dataclass(frozen=True)
class MatterConfig:
    """Configuration for the reduced resident modal matter.

    The slow state is indexed by *resident modes*, never by requested frequency.
    Frequency only decides which already-existing modes are excited.
    """

    centers: tuple[float, ...] = (0.18, 0.26, 0.34, 0.42)
    radii: tuple[float, ...] = (0.94, 0.955, 0.96, 0.95)
    detune: float = 0.50
    write_rate: float = 0.0025
    state_mode: StateMode = "local"

    def __post_init__(self) -> None:
        if len(self.centers) != len(self.radii):
            raise ValueError("centers and radii must have the same length")
        if len(self.centers) < 2:
            raise ValueError("at least two resident modes are required")
        if any(not (0.0 < r < 1.0) for r in self.radii):
            raise ValueError("all mode radii must lie strictly inside the unit circle")
        if self.write_rate <= 0.0:
            raise ValueError("write_rate must be positive")
        if self.state_mode not in ("local", "global", "frozen"):
            raise ValueError(f"unknown state_mode: {self.state_mode}")


class ResidentModalMatter:
    """Frequency-addressed resonant matter with slow state-dependent dynamics.

    Fast state
    ----------
    Each resident mode is a damped complex oscillator. A carrier at frequency ω
    drives *all* modes, but their existing resonance centers determine the mixture
    that actually absorbs the event.

    Slow state
    ----------
    Local modal energy writes one slow material scalar per resident mode. In the
    full model that local material detunes that same resident mode, so the next
    event encounters a different transfer operator. There is no slow decay in v0:
    this deliberately removes the easy "the most recent event simply decayed less"
    explanation for A→B versus B→A.

    Attackers
    ---------
    ``state_mode='frozen'`` records slow state but denies it causal influence on the
    operator. ``state_mode='global'`` collapses all slow state to one shared scalar
    detuning coordinate. Both use exactly the same fast resonators and writes.
    """

    def __init__(self, config: MatterConfig | None = None) -> None:
        self.config = config or MatterConfig()
        self.centers = np.asarray(self.config.centers, dtype=float)
        self.radii = np.asarray(self.config.radii, dtype=float)
        self.reset()

    @property
    def n_modes(self) -> int:
        return int(self.centers.size)

    def reset(self) -> None:
        self.fast = np.zeros(self.n_modes, dtype=complex)
        self.material = np.zeros(self.n_modes, dtype=float)

    def reset_fast(self) -> None:
        self.fast[:] = 0.0

    def _shift(self) -> np.ndarray:
        mode = self.config.state_mode
        if mode == "frozen":
            return np.zeros_like(self.material)
        if mode == "global":
            return np.full_like(self.material, self.config.detune * float(np.mean(self.material)))
        return self.config.detune * self.material

    def poles(self) -> np.ndarray:
        return self.radii * np.exp(1j * (self.centers + self._shift()))

    def step(self, drive: complex, *, update_material: bool = True) -> complex:
        self.fast = self.poles() * self.fast + complex(drive)
        if update_material:
            energy = np.abs(self.fast) ** 2
            bounded = energy / (1.0 + energy)
            self.material += self.config.write_rate * bounded * (1.0 - self.material)
            self.material = np.clip(self.material, 0.0, 1.0)
        return complex(np.mean(self.fast))

    def write(self, omega: float, *, amplitude: float = 0.03, duration: int = 160) -> None:
        for t in range(int(duration)):
            self.step(amplitude * np.exp(1j * float(omega) * t), update_material=True)

    def settle(self, steps: int = 160) -> None:
        for _ in range(int(steps)):
            self.step(0.0j, update_material=True)

    def branch_transfer(self, omega: float) -> np.ndarray:
        z = np.exp(1j * float(omega))
        return 1.0 / (z - self.poles())

    def transfer(self, omega: float) -> complex:
        return complex(np.mean(self.branch_transfer(omega)))

    def operator_signature(self, probes: Sequence[float]) -> np.ndarray:
        return np.asarray([self.transfer(float(w)) for w in probes], dtype=complex)

    def operator_vector(self, probes: Sequence[float]) -> np.ndarray:
        signature = self.operator_signature(probes)
        return np.concatenate([signature.real, signature.imag])

    def address_profile(self, omega: float) -> np.ndarray:
        """Normalized baseline participation of resident modes at one frequency."""
        response = np.abs(self.branch_transfer(omega)) ** 2
        total = float(np.sum(response))
        return response / max(total, 1e-12)


def run_sequence(
    order: Iterable[float],
    *,
    config: MatterConfig | None = None,
    amplitude: float = 0.03,
    duration: int = 160,
    settle_steps: int = 160,
) -> ResidentModalMatter:
    matter = ResidentModalMatter(config)
    for omega in order:
        matter.write(float(omega), amplitude=amplitude, duration=duration)
        matter.settle(settle_steps)
    return matter


def effective_rank(matrix: np.ndarray) -> float:
    singular = np.linalg.svd(np.asarray(matrix, dtype=float), compute_uv=False)
    denom = float(np.dot(singular, singular))
    if denom <= 1e-18:
        return 0.0
    return float((np.sum(singular) ** 2) / denom)
