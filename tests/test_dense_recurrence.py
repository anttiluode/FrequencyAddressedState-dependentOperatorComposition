import numpy as np

from frequency_operator_composition.dense_recurrence import (
    DenseAdaptiveRNN,
    HiddenModalDenseRNN,
)


def test_all_v4_attackers_use_the_same_96_state_budget():
    assert DenseAdaptiveRNN(kind="gaussian").real_state_count == 96
    assert DenseAdaptiveRNN(kind="orthogonal").real_state_count == 96
    assert HiddenModalDenseRNN(alignment="local").real_state_count == 96
    assert HiddenModalDenseRNN(alignment="modal").real_state_count == 96


def test_alignment_control_shares_the_same_fast_matrix_and_io():
    local = HiddenModalDenseRNN(seed=3, alignment="local")
    modal = HiddenModalDenseRNN(seed=3, alignment="modal")

    assert np.allclose(local.w0, modal.w0)
    assert np.allclose(local.input_gain, modal.input_gain)
    assert np.allclose(local.output_gain, modal.output_gain)
    assert np.allclose(local.centers, modal.centers)


def test_dense_gaussian_matrix_is_not_block_modal_by_construction():
    model = DenseAdaptiveRNN(seed=0, kind="gaussian")
    off_diagonal = model.w0 - np.diag(np.diag(model.w0))
    assert np.count_nonzero(np.abs(off_diagonal) > 1e-12) > model.n_fast * 10
