from __future__ import annotations

from typing import Literal, Sequence

import numpy as np

StateMode = Literal["local", "global", "frozen"]
DenseKind = Literal["gaussian", "orthogonal"]
Alignment = Literal["local", "modal"]


class DenseAdaptiveRNN:
    """Dense real recurrence with local slow state and no supplied modal basis.

    The matched default has 64 real fast units and 32 slow variables. Each slow
    variable belongs to one arbitrary adjacent pair of unit coordinates, giving
    exactly 96 real state variables like the v1 cable and v3 matched modal SSM.
    """

    def __init__(
        self,
        *,
        seed: int = 0,
        kind: DenseKind = "gaussian",
        n_fast: int = 64,
        n_slow: int = 32,
        radius: float = 0.95,
        beta: float = 0.45,
        write_rate: float = 0.02,
        state_mode: StateMode = "local",
    ) -> None:
        if n_fast != 2 * n_slow:
            raise ValueError("matched dense attacker expects n_fast == 2 * n_slow")
        if kind not in ("gaussian", "orthogonal"):
            raise ValueError(f"unknown dense kind: {kind}")
        if state_mode not in ("local", "global", "frozen"):
            raise ValueError(f"unknown state mode: {state_mode}")

        rng = np.random.default_rng(seed)
        if kind == "gaussian":
            matrix = rng.normal(0.0, 1.0 / np.sqrt(n_fast), size=(n_fast, n_fast))
            spectral_radius = float(np.max(np.abs(np.linalg.eigvals(matrix))))
            matrix = radius * matrix / max(spectral_radius, 1e-15)
        else:
            q, r = np.linalg.qr(rng.normal(size=(n_fast, n_fast)))
            q = q @ np.diag(np.sign(np.diag(r)))
            matrix = radius * q

        self.seed = int(seed)
        self.kind = kind
        self.n_fast = int(n_fast)
        self.n_slow = int(n_slow)
        self.w0 = np.asarray(matrix, dtype=float)

        self.input_gain = rng.normal(size=n_fast)
        self.input_gain /= np.linalg.norm(self.input_gain)
        self.output_gain = rng.normal(size=n_fast)
        self.output_gain /= np.linalg.norm(self.output_gain)

        self.beta = float(beta)
        self.write_rate = float(write_rate)
        self.state_mode = state_mode
        self.x = np.zeros(n_fast, dtype=float)
        self.slow = np.zeros(n_slow, dtype=float)

    @property
    def real_state_count(self) -> int:
        return self.n_fast + self.n_slow

    def _effective_slow(self) -> np.ndarray:
        if self.state_mode == "frozen":
            return np.zeros_like(self.slow)
        if self.state_mode == "global":
            return np.full_like(self.slow, float(np.mean(self.slow)))
        return self.slow

    def expanded_slow(self) -> np.ndarray:
        return np.repeat(self._effective_slow(), 2)

    def matrix(self) -> np.ndarray:
        return self.w0 - self.beta * np.diag(self.expanded_slow())

    def step(self, drive: float) -> float:
        self.x = self.w0 @ self.x - self.beta * self.expanded_slow() * self.x
        self.x += self.input_gain * float(drive)

        pair_state = self.x.reshape(self.n_slow, 2)
        energy = np.sum(pair_state * pair_state, axis=1)
        bounded = energy / (1.0 + energy)
        self.slow += self.write_rate * bounded * (1.0 - self.slow)
        self.slow = np.clip(self.slow, 0.0, 1.0)
        return float(self.output_gain @ self.x)

    def write(self, omega: float, *, amplitude: float = 0.04, duration: int = 200) -> None:
        for t in range(int(duration)):
            self.step(amplitude * np.sin(float(omega) * t))

    def settle(self, steps: int = 800) -> None:
        for _ in range(int(steps)):
            self.step(0.0)

    def transfer(self, omega: float) -> complex:
        z = np.exp(1j * float(omega))
        return complex(
            self.output_gain
            @ np.linalg.solve(z * np.eye(self.n_fast) - self.matrix(), self.input_gain)
        )

    def operator_vector(self, probes: Sequence[float]) -> np.ndarray:
        response = np.asarray([self.transfer(float(w)) for w in probes], dtype=complex)
        return np.concatenate([response.real, response.imag])

    def address_profile(self, omega: float) -> np.ndarray:
        z = np.exp(1j * float(omega))
        response = np.linalg.solve(
            z * np.eye(self.n_fast) - self.w0,
            self.input_gain,
        ).reshape(self.n_slow, 2)
        power = np.sum(np.abs(response) ** 2, axis=1)
        return power / max(float(np.sum(power)), 1e-15)

    def fast_norm(self) -> float:
        return float(np.linalg.norm(self.x))


class HiddenModalDenseRNN:
    """Dense normal recurrence used to isolate adaptation-coordinate alignment.

    Both variants share the same dense baseline recurrence W0 = Q B Q^T, random
    input/output vectors, 64 fast + 32 slow states, and broad hidden spectrum.
    Local alignment writes visible unit-pairs. Modal alignment writes the hidden
    rotation-pair coordinates and detunes those same resident modes.
    """

    def __init__(
        self,
        *,
        seed: int = 0,
        alignment: Alignment = "local",
        n_pairs: int = 32,
        radius: float = 0.95,
        beta: float = 0.45,
        write_rate: float = 0.02,
        state_mode: StateMode = "local",
    ) -> None:
        if alignment not in ("local", "modal"):
            raise ValueError(f"unknown alignment: {alignment}")
        if state_mode not in ("local", "global", "frozen"):
            raise ValueError(f"unknown state mode: {state_mode}")

        rng = np.random.default_rng(seed)
        self.seed = int(seed)
        self.alignment = alignment
        self.n_pairs = int(n_pairs)
        self.n_fast = 2 * self.n_pairs
        self.radius = float(radius)
        self.beta = float(beta)
        self.write_rate = float(write_rate)
        self.state_mode = state_mode
        self.centers = np.linspace(0.04, 0.54, self.n_pairs)

        q, r = np.linalg.qr(rng.normal(size=(self.n_fast, self.n_fast)))
        self.q = q @ np.diag(np.sign(np.diag(r)))
        self.b0 = self._block_matrix(self.centers)
        self.w0 = self.q @ self.b0 @ self.q.T

        self.input_gain = rng.normal(size=self.n_fast)
        self.input_gain /= np.linalg.norm(self.input_gain)
        self.output_gain = rng.normal(size=self.n_fast)
        self.output_gain /= np.linalg.norm(self.output_gain)

        self.x = np.zeros(self.n_fast, dtype=float)
        self.slow = np.zeros(self.n_pairs, dtype=float)

    @property
    def real_state_count(self) -> int:
        return self.n_fast + self.n_pairs

    def _effective_slow(self) -> np.ndarray:
        if self.state_mode == "frozen":
            return np.zeros_like(self.slow)
        if self.state_mode == "global":
            return np.full_like(self.slow, float(np.mean(self.slow)))
        return self.slow

    def _block_matrix(self, phases: np.ndarray) -> np.ndarray:
        block = np.zeros((self.n_fast, self.n_fast), dtype=float)
        for i, phase in enumerate(phases):
            c = np.cos(float(phase))
            s = np.sin(float(phase))
            block[2 * i : 2 * i + 2, 2 * i : 2 * i + 2] = self.radius * np.array(
                [[c, -s], [s, c]],
                dtype=float,
            )
        return block

    def matrix(self) -> np.ndarray:
        slow = self._effective_slow()
        if self.alignment == "local":
            return self.w0 - self.beta * np.diag(np.repeat(slow, 2))
        detuned = self._block_matrix(self.centers + self.beta * slow)
        return self.q @ detuned @ self.q.T

    def step(self, drive: float) -> float:
        slow = self._effective_slow()

        if self.alignment == "local":
            self.x = self.w0 @ self.x - self.beta * np.repeat(slow, 2) * self.x
            self.x += self.input_gain * float(drive)
            coordinates = self.x.reshape(self.n_pairs, 2)
        else:
            modal = (self.q.T @ self.x).reshape(self.n_pairs, 2)
            phases = self.centers + self.beta * slow
            c = np.cos(phases)
            s = np.sin(phases)
            a = modal[:, 0].copy()
            b = modal[:, 1].copy()
            modal[:, 0] = self.radius * (c * a - s * b)
            modal[:, 1] = self.radius * (s * a + c * b)
            self.x = self.q @ modal.reshape(self.n_fast)
            self.x += self.input_gain * float(drive)
            coordinates = (self.q.T @ self.x).reshape(self.n_pairs, 2)

        energy = np.sum(coordinates * coordinates, axis=1)
        bounded = energy / (1.0 + energy)
        self.slow += self.write_rate * bounded * (1.0 - self.slow)
        self.slow = np.clip(self.slow, 0.0, 1.0)
        return float(self.output_gain @ self.x)

    def write(self, omega: float, *, amplitude: float = 0.04, duration: int = 200) -> None:
        for t in range(int(duration)):
            self.step(amplitude * np.sin(float(omega) * t))

    def settle(self, steps: int = 800) -> None:
        for _ in range(int(steps)):
            self.step(0.0)

    def transfer(self, omega: float) -> complex:
        z = np.exp(1j * float(omega))
        return complex(
            self.output_gain
            @ np.linalg.solve(z * np.eye(self.n_fast) - self.matrix(), self.input_gain)
        )

    def operator_vector(self, probes: Sequence[float]) -> np.ndarray:
        response = np.asarray([self.transfer(float(w)) for w in probes], dtype=complex)
        return np.concatenate([response.real, response.imag])

    def address_profile(self, omega: float) -> np.ndarray:
        z = np.exp(1j * float(omega))
        response = np.linalg.solve(
            z * np.eye(self.n_fast) - self.w0,
            self.input_gain,
        )
        if self.alignment == "modal":
            response = self.q.T @ response
        pairs = response.reshape(self.n_pairs, 2)
        power = np.sum(np.abs(pairs) ** 2, axis=1)
        return power / max(float(np.sum(power)), 1e-15)

    def fast_norm(self) -> float:
        return float(np.linalg.norm(self.x))
