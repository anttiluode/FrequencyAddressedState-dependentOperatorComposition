from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from .cable import CableCell, homogeneous_specs, run_cable_sequence
from .core import effective_rank

WRITE_FREQUENCIES = (0.12, 0.20, 0.28, 0.34)
PROBE_FREQUENCIES = tuple(np.linspace(0.06, 0.50, 30))


def _operator(cell: CableCell) -> np.ndarray:
    return cell.operator_vector(PROBE_FREQUENCIES)


def _address(cell: CableCell) -> dict:
    profiles = np.asarray([cell.address_profile(freq) for freq in WRITE_FREQUENCIES])
    return {
        "effective_rank": effective_rank(profiles),
        "profiles": profiles.tolist(),
    }


def _single_writes(**kwargs) -> dict:
    baseline = _operator(CableCell(**kwargs))
    operator_displacements = []
    material = []
    fast_residuals = []
    for freq in WRITE_FREQUENCIES:
        cell = run_cable_sequence([freq], **kwargs)
        operator_displacements.append(_operator(cell) - baseline)
        material.append(cell.material_vector())
        fast_residuals.append(cell.fast_norm())
    operator_displacements = np.asarray(operator_displacements)
    material = np.asarray(material)
    return {
        "operator_effective_rank": effective_rank(operator_displacements),
        "material_effective_rank": effective_rank(material),
        "mean_operator_change": float(np.mean(np.linalg.norm(operator_displacements, axis=1))),
        "max_fast_residual_after_settle": float(np.max(fast_residuals)),
    }


def _composition(**kwargs) -> dict:
    baseline = _operator(CableCell(**kwargs))
    single = []
    for freq in WRITE_FREQUENCIES:
        single.append(float(np.linalg.norm(_operator(run_cable_sequence([freq], **kwargs)) - baseline)))
    scale = float(np.mean(single))
    pair_rows = []
    for a, b in combinations(WRITE_FREQUENCIES, 2):
        ab = run_cable_sequence([a, b], **kwargs)
        ba = run_cable_sequence([b, a], **kwargs)
        pair_rows.append(
            {
                "a": a,
                "b": b,
                "operator_difference": float(np.linalg.norm(_operator(ab) - _operator(ba))),
                "material_difference": float(np.linalg.norm(ab.material_vector() - ba.material_vector())),
            }
        )
    mean_difference = float(np.mean([row["operator_difference"] for row in pair_rows]))
    return {
        "mean_pair_operator_difference": mean_difference,
        "mean_single_write_operator_change": scale,
        "commutator_ratio": mean_difference / max(scale, 1e-15),
        "pairs": pair_rows,
    }


def _paired_jitter(**kwargs) -> dict:
    rng = np.random.default_rng(20260918)
    a0, b0 = 0.20, 0.34
    ab_rows = []
    ba_rows = []
    paired = []
    for _ in range(24):
        a = a0 + rng.normal(0.0, 0.0015)
        b = b0 + rng.normal(0.0, 0.0015)
        amp_a = 0.04 * (1.0 + rng.normal(0.0, 0.02))
        amp_b = 0.04 * (1.0 + rng.normal(0.0, 0.02))

        def execute(first: tuple[float, float], second: tuple[float, float]) -> np.ndarray:
            cell = CableCell(**kwargs)
            for freq, amp in (first, second):
                cell.write(freq, amplitude=amp, duration=200)
                cell.settle(800)
            return _operator(cell)

        ab = execute((a, amp_a), (b, amp_b))
        ba = execute((b, amp_b), (a, amp_a))
        ab_rows.append(ab)
        ba_rows.append(ba)
        paired.append(float(np.linalg.norm(ab - ba)))

    ab = np.asarray(ab_rows)
    ba = np.asarray(ba_rows)
    within = 0.5 * (
        np.mean(np.linalg.norm(ab - np.mean(ab, axis=0), axis=1))
        + np.mean(np.linalg.norm(ba - np.mean(ba, axis=0), axis=1))
    )
    mean_paired = float(np.mean(paired))
    return {
        "trials": 24,
        "mean_paired_order_difference": mean_paired,
        "within_order_jitter_scale": float(within),
        "order_to_jitter_ratio": mean_paired / max(float(within), 1e-15),
    }


def _variant(**kwargs) -> dict:
    cell = CableCell(**kwargs)
    return {
        "address": _address(cell),
        "single_writes": _single_writes(**kwargs),
        "composition": _composition(**kwargs),
        "paired_jitter": _paired_jitter(**kwargs),
    }


def run_v1() -> dict:
    full = _variant(state_mode="local")
    global_state = _variant(state_mode="global")
    frozen = _variant(state_mode="frozen")
    homogeneous = _variant(state_mode="local", branch_specs=homogeneous_specs())

    variants = {
        "heterogeneous_local_cable": full,
        "global_scalar_state_attacker": global_state,
        "frozen_operator_attacker": frozen,
        "homogeneous_branch_attacker": homogeneous,
    }
    criteria = {
        "heterogeneous_address_rank_at_least_3": full["address"]["effective_rank"] >= 3.0,
        "local_operator_write_rank_at_least_2_3": full["single_writes"]["operator_effective_rank"] >= 2.3,
        "local_commutator_ratio_at_least_0_04": full["composition"]["commutator_ratio"] >= 0.04,
        "local_order_exceeds_jitter_by_2_5x": full["paired_jitter"]["order_to_jitter_ratio"] >= 2.5,
        "fast_state_settled_below_1e_5": full["single_writes"]["max_fast_residual_after_settle"] <= 1e-5,
        "frozen_commutator_below_1e_9": frozen["composition"]["commutator_ratio"] <= 1e-9,
        "global_operator_write_rank_below_1_5": global_state["single_writes"]["operator_effective_rank"] <= 1.5,
        "homogeneous_address_rank_below_1_1": homogeneous["address"]["effective_rank"] <= 1.1,
    }
    return {
        "experiment": "v1_heterogeneous_quasi_active_cable_operator_composition",
        "seed": 20260918,
        "write_frequencies": list(WRITE_FREQUENCIES),
        "probe_frequencies": list(PROBE_FREQUENCIES),
        "variants": variants,
        "criteria": criteria,
        "verdict": "PASS_V1_CABLE_OPERATOR_COMPOSITION_GATE" if all(criteria.values()) else "FAIL_V1_CABLE_OPERATOR_COMPOSITION_GATE",
        "claim_boundary": (
            "The branch geometry and quasi-active parameters are synthetic and chosen to expose four separated resonant addresses. "
            "Slow state lives on physical cable compartments rather than explicit frequency bins. Passing this gate shows only that "
            "a cable-embodied version of the v0 mechanism is executable under these controls; it is not a biological dendrite claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/v1_cable.json"))
    args = parser.parse_args()
    result = run_v1()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "criteria": result["criteria"],
        "address_rank": result["variants"]["heterogeneous_local_cable"]["address"]["effective_rank"],
        "operator_write_rank": result["variants"]["heterogeneous_local_cable"]["single_writes"]["operator_effective_rank"],
        "commutator_ratio": result["variants"]["heterogeneous_local_cable"]["composition"]["commutator_ratio"],
        "order_to_jitter": result["variants"]["heterogeneous_local_cable"]["paired_jitter"]["order_to_jitter_ratio"],
    }, indent=2))


if __name__ == "__main__":
    main()
