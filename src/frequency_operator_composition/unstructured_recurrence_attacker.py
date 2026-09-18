from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Callable

import numpy as np

from .cable_experiment import PROBE_FREQUENCIES, WRITE_FREQUENCIES
from .core import effective_rank
from .dense_recurrence import DenseAdaptiveRNN, HiddenModalDenseRNN


def _operator(model) -> np.ndarray:
    return model.operator_vector(PROBE_FREQUENCIES)


def _run_sequence(factory: Callable[[], object], order, amplitudes=None):
    model = factory()
    for i, omega in enumerate(order):
        amplitude = 0.04 if amplitudes is None else float(amplitudes[i])
        model.write(float(omega), amplitude=amplitude, duration=200)
        model.settle(800)
    return model


def _metrics(factory: Callable[[], object]) -> dict:
    baseline = factory()
    base_operator = _operator(baseline)
    profiles = np.asarray(
        [baseline.address_profile(freq) for freq in WRITE_FREQUENCIES],
        dtype=float,
    )

    displacements = []
    slow_states = []
    fast_residuals = []
    for freq in WRITE_FREQUENCIES:
        model = _run_sequence(factory, [freq])
        displacements.append(_operator(model) - base_operator)
        slow_states.append(model.slow.copy())
        fast_residuals.append(model.fast_norm())

    displacements = np.asarray(displacements)
    slow_states = np.asarray(slow_states)
    mean_single = float(np.mean(np.linalg.norm(displacements, axis=1)))

    pair_differences = []
    for a, b in combinations(WRITE_FREQUENCIES, 2):
        ab = _run_sequence(factory, [a, b])
        ba = _run_sequence(factory, [b, a])
        pair_differences.append(float(np.linalg.norm(_operator(ab) - _operator(ba))))

    mean_pair = float(np.mean(pair_differences))
    return {
        "real_state_count": int(baseline.real_state_count),
        "address_effective_rank": effective_rank(profiles),
        "operator_write_effective_rank": effective_rank(displacements),
        "slow_write_effective_rank": effective_rank(slow_states),
        "mean_single_write_operator_change": mean_single,
        "mean_pair_operator_difference": mean_pair,
        "commutator_ratio": mean_pair / max(mean_single, 1e-15),
        "max_fast_residual_after_settle": float(np.max(fast_residuals)),
    }


def _paired_jitter(factory: Callable[[], object], *, seed: int) -> dict:
    rng = np.random.default_rng(20260918 + int(seed))
    a0, b0 = 0.20, 0.34
    ab_rows = []
    ba_rows = []
    paired = []

    for _ in range(24):
        a = a0 + rng.normal(0.0, 0.0015)
        b = b0 + rng.normal(0.0, 0.0015)
        amp_a = 0.04 * (1.0 + rng.normal(0.0, 0.02))
        amp_b = 0.04 * (1.0 + rng.normal(0.0, 0.02))

        ab = _operator(_run_sequence(factory, [a, b], [amp_a, amp_b]))
        ba = _operator(_run_sequence(factory, [b, a], [amp_b, amp_a]))
        ab_rows.append(ab)
        ba_rows.append(ba)
        paired.append(float(np.linalg.norm(ab - ba)))

    ab = np.asarray(ab_rows)
    ba = np.asarray(ba_rows)
    within = 0.5 * (
        np.mean(np.linalg.norm(ab - np.mean(ab, axis=0), axis=1))
        + np.mean(np.linalg.norm(ba - np.mean(ba, axis=0), axis=1))
    )
    return {
        "trials": 24,
        "mean_paired_order_difference": float(np.mean(paired)),
        "within_order_jitter_scale": float(within),
        "order_to_jitter_ratio": float(np.mean(paired)) / max(float(within), 1e-15),
    }


def _seed_sweep(factory_builder: Callable[[int], object]) -> dict:
    rows = []
    for seed in range(8):
        row = _metrics(lambda seed=seed: factory_builder(seed))
        rows.append(
            {
                "seed": seed,
                "address_effective_rank": row["address_effective_rank"],
                "operator_write_effective_rank": row["operator_write_effective_rank"],
                "slow_write_effective_rank": row["slow_write_effective_rank"],
                "commutator_ratio": row["commutator_ratio"],
            }
        )

    summary = {}
    for key in (
        "address_effective_rank",
        "operator_write_effective_rank",
        "slow_write_effective_rank",
        "commutator_ratio",
    ):
        values = np.asarray([row[key] for row in rows], dtype=float)
        summary[key] = {
            "min": float(np.min(values)),
            "median": float(np.median(values)),
            "max": float(np.max(values)),
        }
    return {"rows": rows, "summary": summary}


def run_v4() -> dict:
    gaussian_builder = lambda seed: DenseAdaptiveRNN(seed=seed, kind="gaussian")
    orthogonal_builder = lambda seed: DenseAdaptiveRNN(seed=seed, kind="orthogonal")
    local_builder = lambda seed: HiddenModalDenseRNN(seed=seed, alignment="local")
    modal_builder = lambda seed: HiddenModalDenseRNN(seed=seed, alignment="modal")

    gaussian = _metrics(lambda: gaussian_builder(0))
    orthogonal = _metrics(lambda: orthogonal_builder(0))
    hidden_local = _metrics(lambda: local_builder(0))
    hidden_modal = _metrics(lambda: modal_builder(0))

    hidden_local["paired_jitter"] = _paired_jitter(lambda: local_builder(0), seed=0)
    hidden_modal["paired_jitter"] = _paired_jitter(lambda: modal_builder(0), seed=0)

    sweeps = {
        "gaussian_dense_local": _seed_sweep(gaussian_builder),
        "orthogonal_dense_local": _seed_sweep(orthogonal_builder),
        "same_fast_matrix_local_alignment": _seed_sweep(local_builder),
        "same_fast_matrix_modal_alignment_rescue": _seed_sweep(modal_builder),
    }

    g = sweeps["gaussian_dense_local"]["summary"]
    o = sweeps["orthogonal_dense_local"]["summary"]
    local = sweeps["same_fast_matrix_local_alignment"]["summary"]
    modal = sweeps["same_fast_matrix_modal_alignment_rescue"]["summary"]

    criteria = {
        "all_variants_match_96_state_budget": all(
            row["real_state_count"] == 96
            for row in (gaussian, orthogonal, hidden_local, hidden_modal)
        ),
        "gaussian_unstructured_max_address_below_1_9": g["address_effective_rank"]["max"] < 1.9,
        "gaussian_unstructured_max_operator_rank_below_1_4": g["operator_write_effective_rank"]["max"] < 1.4,
        "gaussian_unstructured_max_commutator_below_0_01": g["commutator_ratio"]["max"] < 0.01,
        "orthogonal_unstructured_max_address_below_2_4": o["address_effective_rank"]["max"] < 2.4,
        "orthogonal_unstructured_max_operator_rank_below_1_8": o["operator_write_effective_rank"]["max"] < 1.8,
        "orthogonal_unstructured_max_commutator_below_0_02": o["commutator_ratio"]["max"] < 0.02,
        "same_fast_matrix_local_max_operator_rank_below_1_8": local["operator_write_effective_rank"]["max"] < 1.8,
        "same_fast_matrix_local_max_commutator_below_0_04": local["commutator_ratio"]["max"] < 0.04,
        "modal_alignment_min_address_at_least_2_8": modal["address_effective_rank"]["min"] >= 2.8,
        "modal_alignment_min_operator_rank_at_least_2_1": modal["operator_write_effective_rank"]["min"] >= 2.1,
        "modal_alignment_min_commutator_at_least_0_06": modal["commutator_ratio"]["min"] >= 0.06,
        "modal_alignment_seed0_order_exceeds_jitter_by_2x": hidden_modal["paired_jitter"]["order_to_jitter_ratio"] >= 2.0,
        "local_alignment_seed0_order_below_1_2x_jitter": hidden_local["paired_jitter"]["order_to_jitter_ratio"] < 1.2,
        "modal_alignment_median_operator_rank_exceeds_local_by_0_7": (
            modal["operator_write_effective_rank"]["median"]
            - local["operator_write_effective_rank"]["median"]
            >= 0.7
        ),
    }

    return {
        "experiment": "v4_unstructured_recurrence_attacker",
        "seed": 0,
        "design": {
            "state_budget": "all four variants use 64 real fast + 32 slow = 96 real states",
            "gaussian_dense_local": (
                "generic dense Gaussian recurrence rescaled to spectral radius 0.95; "
                "slow state is written and fed back in arbitrary visible unit-pair coordinates"
            ),
            "orthogonal_dense_local": (
                "random dense orthogonal recurrence rescaled to radius 0.95; same local unit-pair adaptation"
            ),
            "alignment_control": (
                "two dense normal recurrent systems share the same W0 = Q B Q^T, input vector, output vector "
                "and hidden broad rotation spectrum. One adapts visible unit pairs; the rescue exposes the hidden "
                "rotation-pair coordinates to the slow write and operator rewrite."
            ),
            "training": "none; v4 tests natural possession, not learnability",
        },
        "variants": {
            "gaussian_dense_local_seed0": gaussian,
            "orthogonal_dense_local_seed0": orthogonal,
            "same_fast_matrix_local_alignment_seed0": hidden_local,
            "same_fast_matrix_modal_alignment_rescue_seed0": hidden_modal,
        },
        "seed_sweeps": sweeps,
        "criteria": criteria,
        "verdict": (
            "PASS_V4_UNSTRUCTURED_RECURRENCE_ATTACKER_MODAL_ALIGNMENT_SURVIVES"
            if all(criteria.values())
            else "FAIL_V4_UNSTRUCTURED_RECURRENCE_ATTACKER"
        ),
        "claim_boundary": (
            "A matched untrained dense recurrence does not naturally reproduce the current addressed-operator "
            "gate when persistent state is written in arbitrary unit coordinates, even when the fast matrix is "
            "orthogonal and therefore has long-lived complex eigenmodes. A dense system with the same hidden fast "
            "matrix recovers the gate when slow write and feedback are aligned to its resident modal coordinates. "
            "This does not establish that a trained dense RNN cannot learn such an alignment. The surviving "
            "hypothesis is therefore modal/adaptation coordinate alignment as an inductive bias, not cable matter."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/v4_unstructured_recurrence.json"))
    args = parser.parse_args()
    result = run_v4()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "criteria": result["criteria"],
        "seed0": {
            name: {
                "address": row["address_effective_rank"],
                "operator_rank": row["operator_write_effective_rank"],
                "commutator": row["commutator_ratio"],
            }
            for name, row in result["variants"].items()
        },
    }, indent=2))
    if result["verdict"].startswith("FAIL"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
