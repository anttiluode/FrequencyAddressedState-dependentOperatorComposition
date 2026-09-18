from frequency_operator_composition.state_space_attacker import run_v3


def test_v3_modal_ssm_attacker_passes_and_kills_cable_specificity():
    result = run_v3()

    assert result["verdict"] == "PASS_V3_MODAL_SSM_ATTACKER_CABLE_SPECIFICITY_NOT_SUPPORTED"
    assert all(result["criteria"].values())

    matched = result["variants"]["matched_96_state_modal_ssm"]
    compact = result["variants"]["compact_12_state_modal_ssm"]
    frozen = result["variants"]["matched_96_state_frozen_operator_attacker"]
    global_slow = result["variants"]["matched_96_state_global_slow_attacker"]

    assert matched["real_state_count"] == 96
    assert matched["address_effective_rank"] >= 3.0
    assert matched["operator_write_effective_rank"] >= 2.3
    assert matched["paired_jitter"]["order_to_jitter_ratio"] >= 2.5

    assert compact["real_state_count"] == 12
    assert compact["address_effective_rank"] >= 2.5
    assert compact["operator_write_effective_rank"] >= 2.3

    assert frozen["operator_write_effective_rank"] == 0.0
    assert frozen["commutator_ratio"] == 0.0
    assert global_slow["operator_write_effective_rank"] < 1.5
