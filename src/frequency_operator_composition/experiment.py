from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from itertools import combinations
from pathlib import Path

import numpy as np

from .core import MatterConfig, ResidentModalMatter, effective_rank, run_sequence

WRITE_FREQUENCIES = (0.19, 0.25, 0.33, 0.41)
PROBE_FREQUENCIES = tuple(np.linspace(0.12, 0.50, 24))


def _operator_vector(matter: ResidentModalMatter) -> np.ndarray:
    return matter.operator_vector(PROBE_FREQUENCIES)


def _address_metrics(config: MatterConfig) -> dict:
    matter = ResidentModalMatter(config)
    profiles = np.asarray([matter.address_profile(w) for w in WRITE_FREQUENCIES])
    cos = profiles @ profiles.T
    norm = np.linalg.norm(profiles, axis=1)
    cos /= norm[:, None] * norm[None, :] + 1e-12
    upper = (1.0 - cos)[np.triu_indices(len(WRITE_FREQUENCIES), 1)]
    return {
        "effective_rank": effective_rank(profiles),
        "minimum_pair_cosine_distance": float(np.min(upper)),
        "mean_pair_cosine_distance": float(np.mean(upper)),
        "profiles": profiles.tolist(),
    }


def _single_write_operator_metrics(config: MatterConfig) -> dict:
    baseline = _operator_vector(ResidentModalMatter(config))
    displacements = []
    material = []
    for omega in WRITE_FREQUENCIES:
        matter = run_sequence([omega], config=config)
        displacements.append(_operator_vector(matter) - baseline)
        material.append(matter.material.copy())
    displacement = np.asarray(displacements)
    singular = np.linalg.svd(displacement, compute_uv=False)
    return {
        "effective_rank": effective_rank(displacement),
        "mean_norm": float(np.mean(np.linalg.norm(displacement, axis=1))),
        "singular_values": singular.tolist(),
        "material_states": np.asarray(material).tolist(),
    }


def _composition_metrics(config: MatterConfig) -> dict:
    baseline = _operator_vector(ResidentModalMatter(config))
    single_norms = []
    for omega in WRITE_FREQUENCIES:
        matter = run_sequence([omega], config=config)
        single_norms.append(float(np.linalg.norm(_operator_vector(matter) - baseline)))
    single_scale = float(np.mean(single_norms))

    pair_differences = []
    pair_material_differences = []
    receipts = []
    for i, j in combinations(range(len(WRITE_FREQUENCIES)), 2):
        a, b = WRITE_FREQUENCIES[i], WRITE_FREQUENCIES[j]
        ab = run_sequence([a, b], config=config)
        ba = run_sequence([b, a], config=config)
        op_diff = float(np.linalg.norm(_operator_vector(ab) - _operator_vector(ba)))
        state_diff = float(np.linalg.norm(ab.material - ba.material))
        pair_differences.append(op_diff)
        pair_material_differences.append(state_diff)
        receipts.append(
            {
                "a": a,
                "b": b,
                "operator_difference": op_diff,
                "material_difference": state_diff,
            }
        )
    mean_difference = float(np.mean(pair_differences))
    return {
        "mean_pair_operator_difference": mean_difference,
        "mean_pair_material_difference": float(np.mean(pair_material_differences)),
        "mean_single_write_operator_change": single_scale,
        "commutator_ratio": mean_difference / max(single_scale, 1e-12),
        "pairs": receipts,
    }


def _paired_jitter_ratio(config: MatterConfig, *, trials: int = 64, seed: int = 20260918) -> dict:
    """Compare order effect to ordinary symbol-level write jitter on a common tape."""
    rng = np.random.default_rng(seed)
    a, b = 0.21, 0.39
    order_differences = []
    ab_signatures = []
    ba_signatures = []

    for _ in range(trials):
        params = {
            "a": (a + rng.normal(0.0, 0.003), 0.03 * (1.0 + rng.normal(0.0, 0.03))),
            "b": (b + rng.normal(0.0, 0.003), 0.03 * (1.0 + rng.normal(0.0, 0.03))),
        }

        def execute(labels: tuple[str, str]) -> np.ndarray:
            matter = ResidentModalMatter(config)
            for label in labels:
                omega, amplitude = params[label]
                matter.write(omega, amplitude=amplitude, duration=160)
                matter.settle(160)
            return _operator_vector(matter)

        sig_ab = execute(("a", "b"))
        sig_ba = execute(("b", "a"))
        ab_signatures.append(sig_ab)
        ba_signatures.append(sig_ba)
        order_differences.append(float(np.linalg.norm(sig_ab - sig_ba)))

    ab = np.asarray(ab_signatures)
    ba = np.asarray(ba_signatures)
    within = 0.5 * (
        np.mean(np.linalg.norm(ab - np.mean(ab, axis=0), axis=1))
        + np.mean(np.linalg.norm(ba - np.mean(ba, axis=0), axis=1))
    )
    mean_order = float(np.mean(order_differences))
    return {
        "trials": int(trials),
        "mean_paired_order_difference": mean_order,
        "within_order_jitter_scale": float(within),
        "order_to_jitter_ratio": mean_order / max(float(within), 1e-12),
    }


def _variant(config: MatterConfig) -> dict:
    return {
        "config": asdict(config),
        "address": _address_metrics(config),
        "operator_writes": _single_write_operator_metrics(config),
        "composition": _composition_metrics(config),
        "paired_jitter": _paired_jitter_ratio(config),
    }


def run_v0() -> dict:
    full = MatterConfig()
    global_state = MatterConfig(state_mode="global")
    frozen = MatterConfig(state_mode="frozen")
    homogeneous = MatterConfig(
        centers=(0.30, 0.30, 0.30, 0.30),
        radii=(0.95, 0.95, 0.95, 0.95),
    )

    variants = {
        "full_local_state": _variant(full),
        "global_scalar_state_attacker": _variant(global_state),
        "frozen_operator_attacker": _variant(frozen),
        "homogeneous_address_attacker": _variant(homogeneous),
    }

    criteria = {
        "full_address_rank_at_least_2_5": variants["full_local_state"]["address"]["effective_rank"] >= 2.5,
        "full_operator_write_rank_at_least_2_5": variants["full_local_state"]["operator_writes"]["effective_rank"] >= 2.5,
        "full_commutator_ratio_at_least_0_30": variants["full_local_state"]["composition"]["commutator_ratio"] >= 0.30,
        "full_order_effect_exceeds_jitter_by_2x": variants["full_local_state"]["paired_jitter"]["order_to_jitter_ratio"] >= 2.0,
        "frozen_operator_commutator_below_1e_9": variants["frozen_operator_attacker"]["composition"]["commutator_ratio"] <= 1e-9,
        "global_operator_write_rank_below_1_5": variants["global_scalar_state_attacker"]["operator_writes"]["effective_rank"] <= 1.5,
        "homogeneous_address_rank_below_1_1": variants["homogeneous_address_attacker"]["address"]["effective_rank"] <= 1.1,
    }

    return {
        "experiment": "v0_frequency_addressed_state_dependent_operator_composition",
        "seed": 20260918,
        "write_frequencies": list(WRITE_FREQUENCIES),
        "probe_frequencies": list(PROBE_FREQUENCIES),
        "variants": variants,
        "criteria": criteria,
        "verdict": "PASS_V0_OPERATOR_COMPOSITION_GATE" if all(criteria.values()) else "FAIL_V0_OPERATOR_COMPOSITION_GATE",
        "claim_boundary": (
            "This is a synthetic reduced resonator model. It establishes an executable distinction between "
            "frequency addressing, local state-dependent operator change, scalar global adaptation and a frozen "
            "operator control. It does not establish that dendrites implement this mechanism, that the reduced "
            "resonators are a faithful cable model, or that this architecture outperforms conventional recurrent systems."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/v0.json"))
    args = parser.parse_args()
    result = run_v0()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "criteria": result["criteria"],
        "full_address_rank": result["variants"]["full_local_state"]["address"]["effective_rank"],
        "full_operator_write_rank": result["variants"]["full_local_state"]["operator_writes"]["effective_rank"],
        "full_commutator_ratio": result["variants"]["full_local_state"]["composition"]["commutator_ratio"],
        "full_order_to_jitter": result["variants"]["full_local_state"]["paired_jitter"]["order_to_jitter_ratio"],
    }, indent=2))


if __name__ == "__main__":
    main()
