from frequency_operator_composition.unstructured_recurrence_attacker import run_v4


def test_v4_unstructured_recurrence_boundary():
    result = run_v4()

    assert result["verdict"] == "PASS_V4_UNSTRUCTURED_RECURRENCE_ATTACKER_MODAL_ALIGNMENT_SURVIVES"
    assert all(result["criteria"].values())

    gaussian = result["variants"]["gaussian_dense_local_seed0"]
    orthogonal = result["variants"]["orthogonal_dense_local_seed0"]
    local = result["variants"]["same_fast_matrix_local_alignment_seed0"]
    modal = result["variants"]["same_fast_matrix_modal_alignment_rescue_seed0"]

    assert gaussian["operator_write_effective_rank"] < 1.4
    assert orthogonal["operator_write_effective_rank"] < 1.8
    assert local["operator_write_effective_rank"] < 1.8
    assert modal["operator_write_effective_rank"] > 2.5

    assert local["paired_jitter"]["order_to_jitter_ratio"] < 1.2
    assert modal["paired_jitter"]["order_to_jitter_ratio"] > 2.0
