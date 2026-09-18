import numpy as np

from frequency_operator_composition.cable import DEFAULT_BRANCHES
from frequency_operator_composition.geometry_vs_kinetics import (
    geometry_only_specs,
    kinetics_only_specs,
    run_v2,
    uniform_specs,
)


def test_factorization_changes_only_the_intended_axes():
    geometry = geometry_only_specs()
    assert [s.n for s in geometry] == [s.n for s in DEFAULT_BRANCHES]
    assert len({(s.g, s.d, s.c, s.leak, s.coupling) for s in geometry}) == 1

    for index, ref in enumerate(DEFAULT_BRANCHES):
        shared = geometry_only_specs(index)
        assert [s.n for s in shared] == [s.n for s in DEFAULT_BRANCHES]
        assert len({(s.g, s.d, s.c, s.leak, s.coupling) for s in shared}) == 1
        assert (shared[0].g, shared[0].d, shared[0].c) == (ref.g, ref.d, ref.c)

    kinetics = kinetics_only_specs()
    assert len({s.n for s in kinetics}) == 1
    assert [(s.g, s.d, s.c) for s in kinetics] == [(s.g, s.d, s.c) for s in DEFAULT_BRANCHES]

    uniform = uniform_specs()
    assert len({(s.n, s.g, s.d, s.c, s.leak, s.coupling) for s in uniform}) == 1


def test_v2_geometry_only_address_hypothesis_is_killed_not_hidden():
    result = run_v2()
    assert result["verdict"] == "GEOMETRY_ONLY_ADDRESS_HYPOTHESIS_NOT_SUPPORTED"
    assert result["findings"]["kinetics_only_preserves_high_address_rank"]
    assert result["findings"]["geometry_only_can_remain_order_dependent_without_being_a_good_address"]
    assert result["findings"]["all_original_shared_kinetics_raw_address_rank_below_1_5"]
    assert result["findings"]["all_original_shared_kinetics_gain_normalized_rank_below_2"]
    assert not result["findings"]["geometry_only_address_gate_passes"]
    assert not result["findings"]["geometry_only_gain_normalized_shape_gate_passes"]

    geometry = result["variants"]["geometry_only"]
    kinetics = result["variants"]["kinetics_only"]
    assert geometry["address"]["effective_rank"] < 1.5
    assert geometry["gain_normalized_address_rank"] < 2.5
    assert kinetics["address"]["effective_rank"] > 3.5
    assert result["sweep_summary"]["max_raw_address_rank"] < 1.5
    assert result["sweep_summary"]["max_gain_normalized_address_rank"] < 2.0
