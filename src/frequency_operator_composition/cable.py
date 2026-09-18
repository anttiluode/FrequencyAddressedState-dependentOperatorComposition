from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np

CableStateMode = Literal["local", "global", "frozen"]


@dataclass(frozen=True)
class BranchSpec:
    n: int
    g: float
    d: float
    c: float
    leak: float = 0.015
    coupling: float = 0.18


DEFAULT_BRANCHES: tuple[BranchSpec, ...] = (
    BranchSpec(5, 0.13960124004916397, 0.9185656230911622, 0.08104556966507002),
    BranchSpec(7, 0.38626925720616234, 0.9380414177664963, 0.09311277644010527),
    BranchSpec(9, 0.4175518164125044, 0.9139470695843545, 0.17210258407443785),
    BranchSpec(11, 0.5492018255250434, 0.8826229468455242, 0.1999997881613304),
)


def cable_operator(n: int, leak: float, coupling: float) -> np.ndarray:
    """Passive symmetric cable step operator on a path graph."""
    lap = np.zeros((n, n), dtype=float)
    for i in range(n - 1):
        lap[i, i] += 1.0
        lap[i + 1, i + 1] += 1.0
        lap[i, i + 1] -= 1.0
        lap[i + 1, i] -= 1.0
    return np.eye(n) - leak * np.eye(n) - coupling * lap


class QuasiActiveBranch:
    """One cable branch with local voltage/recovery state and local slow material.

    The input is injected at compartment 0 and the soma reads compartment n-1.
    Slow material is attached to physical compartments, not to frequency bins.
    """

    def __init__(self, spec: BranchSpec, *, beta: float, write_rate: float) -> None:
        self.spec = spec
        self.beta = float(beta)
        self.write_rate = float(write_rate)
        self.a0 = cable_operator(spec.n, spec.leak, spec.coupling)
        self.v = np.zeros(spec.n, dtype=float)
        self.w = np.zeros(spec.n, dtype=float)
        self.material = np.zeros(spec.n, dtype=float)

    def reset(self) -> None:
        self.v[:] = 0.0
        self.w[:] = 0.0
        self.material[:] = 0.0

    def step(self, drive: float, shift: np.ndarray) -> float:
        old_v = self.v
        old_w = self.w
        new_v = self.a0 @ old_v - self.beta * shift * old_v - self.spec.g * old_w
        new_v[0] += float(drive)
        new_w = self.spec.d * old_w + self.spec.c * old_v
        self.v = new_v
        self.w = new_w

        energy = new_v * new_v
        bounded = energy / (1.0 + energy)
        self.material += self.write_rate * bounded * (1.0 - self.material)
        self.material = np.clip(self.material, 0.0, 1.0)
        return float(new_v[-1])

    def state_matrix(self, shift: np.ndarray) -> np.ndarray:
        n = self.spec.n
        a = self.a0 - self.beta * np.diag(shift)
        return np.block(
            [
                [a, -self.spec.g * np.eye(n)],
                [self.spec.c * np.eye(n), self.spec.d * np.eye(n)],
            ]
        )

    def transfer(self, omega: float, shift: np.ndarray) -> complex:
        n = self.spec.n
        matrix = self.state_matrix(shift)
        b = np.zeros(2 * n, dtype=float)
        b[0] = 1.0
        read = np.zeros(2 * n, dtype=float)
        read[n - 1] = 1.0
        z = np.exp(1j * float(omega))
        return complex(read @ np.linalg.solve(z * np.eye(2 * n) - matrix, b))

    def fast_norm(self) -> float:
        return float(np.sqrt(np.dot(self.v, self.v) + np.dot(self.w, self.w)))


class CableCell:
    """Heterogeneous quasi-active branches -> soma, with physical local slow state."""

    def __init__(
        self,
        *,
        branch_specs: Sequence[BranchSpec] = DEFAULT_BRANCHES,
        state_mode: CableStateMode = "local",
        beta: float = 0.7,
        write_rate: float = 0.02,
    ) -> None:
        if state_mode not in ("local", "global", "frozen"):
            raise ValueError(f"unknown state mode: {state_mode}")
        self.state_mode = state_mode
        self.branches = [QuasiActiveBranch(spec, beta=beta, write_rate=write_rate) for spec in branch_specs]

    def reset(self) -> None:
        for branch in self.branches:
            branch.reset()

    def _global_material(self) -> float:
        values = np.concatenate([branch.material for branch in self.branches])
        return float(np.mean(values))

    def _shift_for(self, branch: QuasiActiveBranch) -> np.ndarray:
        if self.state_mode == "frozen":
            return np.zeros(branch.spec.n, dtype=float)
        if self.state_mode == "global":
            return np.full(branch.spec.n, self._global_material(), dtype=float)
        return branch.material

    def step(self, drive: float) -> float:
        if self.state_mode == "global":
            shared = self._global_material()
            shifts = [np.full(branch.spec.n, shared, dtype=float) for branch in self.branches]
        elif self.state_mode == "frozen":
            shifts = [np.zeros(branch.spec.n, dtype=float) for branch in self.branches]
        else:
            shifts = [branch.material.copy() for branch in self.branches]
        soma = [branch.step(drive, shift) for branch, shift in zip(self.branches, shifts)]
        return float(np.mean(soma))

    def write(self, omega: float, *, amplitude: float = 0.04, duration: int = 200) -> None:
        for t in range(int(duration)):
            self.step(amplitude * np.sin(float(omega) * t))

    def settle(self, steps: int = 800) -> None:
        for _ in range(int(steps)):
            self.step(0.0)

    def transfer(self, omega: float) -> complex:
        values = [branch.transfer(omega, self._shift_for(branch)) for branch in self.branches]
        return complex(np.mean(values))

    def branch_transfer(self, omega: float) -> np.ndarray:
        return np.asarray(
            [branch.transfer(omega, self._shift_for(branch)) for branch in self.branches],
            dtype=complex,
        )

    def operator_vector(self, probes: Sequence[float]) -> np.ndarray:
        signature = np.asarray([self.transfer(float(freq)) for freq in probes], dtype=complex)
        return np.concatenate([signature.real, signature.imag])

    def address_profile(self, omega: float) -> np.ndarray:
        response = np.abs(self.branch_transfer(omega)) ** 2
        return response / max(float(np.sum(response)), 1e-15)

    def material_vector(self) -> np.ndarray:
        return np.concatenate([branch.material for branch in self.branches])

    def fast_norm(self) -> float:
        return float(np.sqrt(sum(branch.fast_norm() ** 2 for branch in self.branches)))


def homogeneous_specs() -> tuple[BranchSpec, ...]:
    """Matched attacker: four copies of one branch, eliminating address heterogeneity."""
    return (DEFAULT_BRANCHES[1],) * len(DEFAULT_BRANCHES)


def run_cable_sequence(
    order: Sequence[float],
    *,
    branch_specs: Sequence[BranchSpec] = DEFAULT_BRANCHES,
    state_mode: CableStateMode = "local",
    beta: float = 0.7,
    write_rate: float = 0.02,
    amplitude: float = 0.04,
    duration: int = 200,
    settle_steps: int = 800,
) -> CableCell:
    cell = CableCell(
        branch_specs=branch_specs,
        state_mode=state_mode,
        beta=beta,
        write_rate=write_rate,
    )
    for omega in order:
        cell.write(omega, amplitude=amplitude, duration=duration)
        cell.settle(settle_steps)
    return cell
