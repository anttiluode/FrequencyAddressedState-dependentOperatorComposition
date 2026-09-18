from frequency_operator_composition.dense_recurrence import (
    DenseAdaptiveRNN,
    HiddenModalDenseRNN,
)
from frequency_operator_composition.unstructured_recurrence_attacker import _metrics


def test_v4_seed0_boundary_before_full_ci_sweep():
    gaussian = _metrics(lambda: DenseAdaptiveRNN(seed=0, kind="gaussian"))
    orthogonal = _metrics(lambda: DenseAdaptiveRNN(seed=0, kind="orthogonal"))
    local = _metrics(lambda: HiddenModalDenseRNN(seed=0, alignment="local"))
    modal = _metrics(lambda: HiddenModalDenseRNN(seed=0, alignment="modal"))

    assert gaussian["real_state_count"] == 96
    assert orthogonal["real_state_count"] == 96
    assert local["real_state_count"] == 96
    assert modal["real_state_count"] == 96

    assert gaussian["operator_write_effective_rank"] < 1.4
    assert orthogonal["operator_write_effective_rank"] < 1.8
    assert local["operator_write_effective_rank"] < 1.8

    assert modal["address_effective_rank"] > 2.8
    assert modal["operator_write_effective_rank"] > 2.5
    assert modal["commutator_ratio"] > 0.1
