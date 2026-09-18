from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from .cable_experiment import PROBE_FREQUENCIES, WRITE_FREQUENCIES
from .core import effective_rank
from .modal_ssm import AdaptiveModalSSM, run_modal_sequence


CABLE_V1_REFERENCE = {
    "real_state_count": 96,
    "address_effective_rank": 3.977218590346758,
    "operator_write_effective_rank": 2.5809808523945814,
    "material_write_effective_rank": 2.904142161763569,
    "commutator_ratio": 0.06120145337764039,
    "order_to_jitter_ratio": 3.6015378961384967,
}


def _operator(model: AdaptiveModalSSM) -> np.ndarray:
    return model.operator_vector(PROBE_FREQUENCIES)


def _metrics(
    *,
    seed: int,
    n_modes: int,
    state_mode: str = "local",
    with_jitter: bool = False,
) -> dict:
    kwargs = {
        "seed": seed,
        "n_modes": n_modes,
        "state_mode": state_mode,
    }
    baseline = AdaptiveModalSSM(**kwargs)
    base_operator = _operator(baseline)
    profiles = np.asarray(
        [baseline.address_profile(freq) for freq in WRITE_FREQUENCIES]
    )

    operator_displacements = []
    slow_states = []
    fast_residuals = []
    for freq in WRITE_FREQUENCIES:
        model = run_modal_sequence([freq], **kwargs)
        operator_displacements.append(_operator(model) - base_operator)
        slow_states.append(model.slow.copy())
        fast_residuals.append(model.fast_norm())

    operator_displacements = np.asarray(operator_displacements)
    slow_states = np.asarray(slow_states)
    mean_single_change = float(
        np.mean(np.linalg.norm(operator_displacements, axis=1))
    )

    pair_differences = []
    for i, j in combinations(range(len(WRITE_FREQUENCIES)), 2):
        a = WRITE_FREQUENCIES[i]
        b = WRITE_FREQUENCIES[j]
        ab = run_modal_sequence([a, b], **kwargs)
        ba = run_modal_sequence([b, a], **kwargs)
        pair_differences.append(float(np.linalg.norm(_operator(ab) - _operator(ba))))

    mean_pair_difference = float(np.mean(pair_differences))
    result = {
        "real_state_count": 3 * n_modes,
        "address_effective_rank": effective_rank(profiles),
        "operator_write_effective_rank": effective_rank(operator_displacements),
        "slow_write_effective_rank": effective_rank(slow_states),
        "mean_single_write_operator_change": mean_single_change,
        "mean_pair_operator_difference": mean_pair_difference,
        "commutator_ratio": mean_pair_difference / max(mean_single_change, 1e-15),
        "max_fast_residual_after_settle": float(np.max(fast_residuals)),
    }

    if with_jitter:
        rng = np.random.default_rng(20260918 + seed)
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
                model = AdaptiveModalSSM(**kwargs)
                for freq, amplitude in (first, second):
                    model.write(freq, amplitude=amplitude, duration=200)
                    model.settle(800)
                return _operator(model)

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
        result["paired_jitter"] = {
            "trials": 24,
            "mean_paired_order_difference": float(np.mean(paired)),
            "within_order_jitter_scale": float(within),
            "order_to_jitter_ratio": float(np.mean(paired)) / max(float(within), 1e-15),
        }

    return result


def _seed_sweep(n_modes: int) -> dict:
    rows = []
    for seed in range(8):
        row = _metrics(seed=seed, n_modes=n_modes, with_jitter=False)
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


def run_v3() -> dict:
    matched = _metrics(seed=0, n_modes=32, with_jitter=True)
    matched_global = _metrics(seed=0, n_modes=32, state_mode="global")
    matched_frozen = _metrics(seed=0, n_modes=32, state_mode="frozen")
    compact = _metrics(seed=0, n_modes=4, with_jitter=True)

    matched_sweep = _seed_sweep(32)
    compact_sweep = _seed_sweep(4)

    criteria = {
        "matched_state_budget_is_exact": matched["real_state_count"] == CABLE_V1_REFERENCE["real_state_count"],
        "matched_address_rank_at_least_3": matched["address_effective_rank"] >= 3.0,
        "matched_operator_write_rank_at_least_2_3": matched["operator_write_effective_rank"] >= 2.3,
        "matched_commutator_ratio_at_least_0_04": matched["commutator_ratio"] >= 0.04,
        "matched_order_exceeds_jitter_by_2_5x": matched["paired_jitter"]["order_to_jitter_ratio"] >= 2.5,
        "matched_fast_state_settled_below_1e_5": matched["max_fast_residual_after_settle"] <= 1e-5,
        "matched_seed_sweep_min_address_rank_at_least_3": matched_sweep["summary"]["address_effective_rank"]["min"] >= 3.0,
        "matched_seed_sweep_median_operator_rank_at_least_2_5": matched_sweep["summary"]["operator_write_effective_rank"]["median"] >= 2.5,
        "frozen_operator_write_rank_is_zero": matched_frozen["operator_write_effective_rank"] <= 1e-12,
        "frozen_commutator_is_zero": matched_frozen["commutator_ratio"] <= 1e-12,
        "global_state_collapses_operator_family_below_1_5": matched_global["operator_write_effective_rank"] <= 1.5,
        "compact_12_state_address_rank_at_least_2_5": compact["address_effective_rank"] >= 2.5,
        "compact_12_state_operator_rank_at_least_2_3": compact["operator_write_effective_rank"] >= 2.3,
        "compact_12_state_order_exceeds_jitter_by_2_5x": compact["paired_jitter"]["order_to_jitter_ratio"] >= 2.5,
        "compact_seed_sweep_median_address_rank_at_least_2_5": compact_sweep["summary"]["address_effective_rank"]["median"] >= 2.5,
        "compact_seed_sweep_median_operator_rank_at_least_2_5": compact_sweep["summary"]["operator_write_effective_rank"]["median"] >= 2.5,
    }

    return {
        "experiment": "v3_modal_state_space_attacker",
        "seed": 0,
        "design": {
            "matched_attacker": (
                "32 complex resident modes = 64 real fast states plus 32 local slow states, "
                "for exactly 96 real state variables, matching the v1 cable state budget"
            ),
            "compact_attacker": (
                "4 complex resident modes plus 4 local slow states = 12 real state variables"
            ),
            "resident_frequency_band": [0.04, 0.54],
            "important_non_cheat": (
                "resident mode centers are evenly spread across a broad fixed band and are not "
                "set to the four task write frequencies; slow state is indexed by resident mode, "
                "not requested carrier frequency"
            ),
        },
        "cable_v1_reference": CABLE_V1_REFERENCE,
        "variants": {
            "matched_96_state_modal_ssm": matched,
            "matched_96_state_global_slow_attacker": matched_global,
            "matched_96_state_frozen_operator_attacker": matched_frozen,
            "compact_12_state_modal_ssm": compact,
        },
        "seed_sweeps": {
            "matched_96_state_modal_ssm": matched_sweep,
            "compact_12_state_modal_ssm": compact_sweep,
        },
        "criteria": criteria,
        "verdict": (
            "PASS_V3_MODAL_SSM_ATTACKER_CABLE_SPECIFICITY_NOT_SUPPORTED"
            if all(criteria.values())
            else "FAIL_V3_MODAL_SSM_ATTACKER"
        ),
        "claim_boundary": (
            "This attacker does not show that every generic RNN or arbitrary dense state-space model "
            "automatically develops the mechanism. It shows that cable geometry is not required by the "
            "current gates: an ordinary non-geometric modal state-space system with local adaptive slow "
            "state reproduces the addressed persistent noncommuting operator family at the same state "
            "budget, and a much smaller 12-real-state version still crosses the weaker multi-address gate. "
            "What remains distinctive is therefore the inductive bias that supplies separated resident modes "
            "and local state-dependent operator rewrite, not the cable substrate itself."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/v3_modal_ssm.json"))
    args = parser.parse_args()
    result = run_v3()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "criteria": result["criteria"],
        "matched": {
            k: result["variants"]["matched_96_state_modal_ssm"][k]
            for k in (
                "real_state_count",
                "address_effective_rank",
                "operator_write_effective_rank",
                "slow_write_effective_rank",
                "commutator_ratio",
            )
        },
        "matched_order_to_jitter": result["variants"]["matched_96_state_modal_ssm"]["paired_jitter"]["order_to_jitter_ratio"],
        "compact": {
            k: result["variants"]["compact_12_state_modal_ssm"][k]
            for k in (
                "real_state_count",
                "address_effective_rank",
                "operator_write_effective_rank",
                "slow_write_effective_rank",
                "commutator_ratio",
            )
        },
        "compact_order_to_jitter": result["variants"]["compact_12_state_modal_ssm"]["paired_jitter"]["order_to_jitter_ratio"],
    }, indent=2))


if __name__ == "__main__":
    main()
