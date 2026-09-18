from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .cable import BranchSpec, CableCell, DEFAULT_BRANCHES
from .cable_experiment import (
    PROBE_FREQUENCIES,
    WRITE_FREQUENCIES,
    _address,
    _composition,
    _paired_jitter,
    _single_writes,
)
from .core import effective_rank


def representative_kinetics() -> tuple[float, float, float]:
    values = np.asarray([[spec.g, spec.d, spec.c] for spec in DEFAULT_BRANCHES], dtype=float)
    g, d, c = np.median(values, axis=0)
    return float(g), float(d), float(c)


def geometry_only_specs() -> tuple[BranchSpec, ...]:
    """Keep branch lengths; make every channel/recovery parameter identical."""
    g, d, c = representative_kinetics()
    return tuple(
        BranchSpec(
            n=spec.n,
            g=g,
            d=d,
            c=c,
            leak=DEFAULT_BRANCHES[0].leak,
            coupling=DEFAULT_BRANCHES[0].coupling,
        )
        for spec in DEFAULT_BRANCHES
    )


def kinetics_only_specs(n: int = 8) -> tuple[BranchSpec, ...]:
    """Keep original quasi-active kinetics; make every branch the same length."""
    return tuple(
        BranchSpec(
            n=n,
            g=spec.g,
            d=spec.d,
            c=spec.c,
            leak=spec.leak,
            coupling=spec.coupling,
        )
        for spec in DEFAULT_BRANCHES
    )


def uniform_specs(n: int = 8) -> tuple[BranchSpec, ...]:
    g, d, c = representative_kinetics()
    return tuple(
        BranchSpec(
            n=n,
            g=g,
            d=d,
            c=c,
            leak=DEFAULT_BRANCHES[0].leak,
            coupling=DEFAULT_BRANCHES[0].coupling,
        )
        for _ in DEFAULT_BRANCHES
    )


def gain_normalized_address_rank(branch_specs: tuple[BranchSpec, ...]) -> float:
    """Diagnostic upper bound after removing static branch-amplitude imbalance.

    This does not change the simulated machine. It asks whether geometry contains
    useful *spectral shape* that is merely hidden by the stronger attenuation of
    longer branches.
    """
    cell = CableCell(branch_specs=branch_specs)
    baseline = np.asarray(
        [np.abs(cell.branch_transfer(freq)) for freq in PROBE_FREQUENCIES],
        dtype=float,
    )
    rms = np.sqrt(np.mean(baseline**2, axis=0))
    profiles = []
    for freq in WRITE_FREQUENCIES:
        magnitude = np.abs(cell.branch_transfer(freq)) / np.maximum(rms, 1e-15)
        power = magnitude**2
        profiles.append(power / max(float(np.sum(power)), 1e-15))
    return effective_rank(np.asarray(profiles))


def variant(branch_specs: tuple[BranchSpec, ...]) -> dict:
    kwargs = {"state_mode": "local", "branch_specs": branch_specs}
    return {
        "address": _address(CableCell(**kwargs)),
        "gain_normalized_address_rank": gain_normalized_address_rank(branch_specs),
        "single_writes": _single_writes(**kwargs),
        "composition": _composition(**kwargs),
        "paired_jitter": _paired_jitter(**kwargs),
    }


def run_v2() -> dict:
    full = variant(DEFAULT_BRANCHES)
    geometry = variant(geometry_only_specs())
    kinetics = variant(kinetics_only_specs())
    uniform = variant(uniform_specs())

    geometry_address_gate = geometry["address"]["effective_rank"] >= 2.5
    geometry_shape_gate = geometry["gain_normalized_address_rank"] >= 2.5

    findings = {
        "geometry_only_address_gate_passes": geometry_address_gate,
        "geometry_only_gain_normalized_shape_gate_passes": geometry_shape_gate,
        "kinetics_only_preserves_high_address_rank": kinetics["address"]["effective_rank"] >= 3.5,
        "full_operator_family_exceeds_kinetics_only_by_at_least_0_5": (
            full["single_writes"]["operator_effective_rank"]
            - kinetics["single_writes"]["operator_effective_rank"]
            >= 0.5
        ),
        "geometry_only_can_remain_order_dependent_without_being_a_good_address": (
            geometry["paired_jitter"]["order_to_jitter_ratio"] >= 2.0
            and geometry["address"]["effective_rank"] < 1.5
        ),
        "uniform_control_address_rank_is_one": abs(uniform["address"]["effective_rank"] - 1.0) < 1e-9,
    }

    return {
        "experiment": "v2_geometry_vs_quasi_active_kinetics",
        "seed": 20260918,
        "design": {
            "full": "original lengths 5/7/9/11 plus original branch-specific quasi-active kinetics",
            "geometry_only": "original lengths 5/7/9/11; identical median g/d/c and identical passive cable constants",
            "kinetics_only": "all branches length 8; original branch-specific g/d/c retained",
            "uniform": "all branches length 8 and identical median g/d/c",
            "geometry_gate": "address effective rank >= 2.5",
            "gain_normalized_geometry_gate": "address rank >= 2.5 after static per-branch RMS equalization diagnostic",
        },
        "variants": {
            "full": full,
            "geometry_only": geometry,
            "kinetics_only": kinetics,
            "uniform": uniform,
        },
        "findings": findings,
        "verdict": (
            "GEOMETRY_ONLY_ADDRESS_HYPOTHESIS_NOT_SUPPORTED"
            if not geometry_address_gate and not geometry_shape_gate
            else "GEOMETRY_ONLY_ADDRESS_HYPOTHESIS_SURVIVES"
        ),
        "claim_boundary": (
            "For the tested path-cable lengths, distal-input/proximal-readout interface and representative "
            "shared kinetics, morphology alone does not preserve the strong four-way frequency address. "
            "The strong address is carried primarily by heterogeneous quasi-active kinetics. Morphology is "
            "not irrelevant: with kinetic diversity present, the full system has a richer written-operator "
            "family than the equal-length kinetics-only control. This is a synthetic mechanism result, not "
            "a statement about biological dendrites in general."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/v2_geometry_vs_kinetics.json"))
    args = parser.parse_args()
    result = run_v2()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "findings": result["findings"],
        "full_address_rank": result["variants"]["full"]["address"]["effective_rank"],
        "geometry_address_rank": result["variants"]["geometry_only"]["address"]["effective_rank"],
        "geometry_gain_normalized_rank": result["variants"]["geometry_only"]["gain_normalized_address_rank"],
        "kinetics_address_rank": result["variants"]["kinetics_only"]["address"]["effective_rank"],
        "full_operator_write_rank": result["variants"]["full"]["single_writes"]["operator_effective_rank"],
        "kinetics_operator_write_rank": result["variants"]["kinetics_only"]["single_writes"]["operator_effective_rank"],
    }, indent=2))


if __name__ == "__main__":
    main()
