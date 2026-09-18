import numpy as np

from frequency_operator_composition.cable_experiment import PROBE_FREQUENCIES
from frequency_operator_composition.modal_ssm import AdaptiveModalSSM, run_modal_sequence


def test_state_budget_matches_cable_and_compact_variant_is_much_smaller():
    assert AdaptiveModalSSM(n_modes=32).real_state_count == 96
    assert AdaptiveModalSSM(n_modes=4).real_state_count == 12


def test_frozen_operator_can_store_slow_state_without_rewriting_transfer():
    baseline = AdaptiveModalSSM(seed=0, n_modes=32, state_mode="frozen")
    written = run_modal_sequence([0.20, 0.34], seed=0, n_modes=32, state_mode="frozen")

    assert np.linalg.norm(written.slow) > 1e-3
    assert np.allclose(
        written.operator_vector(PROBE_FREQUENCIES),
        baseline.operator_vector(PROBE_FREQUENCIES),
        atol=1e-12,
    )


def test_modal_centers_are_not_the_task_write_frequencies():
    model = AdaptiveModalSSM(seed=0, n_modes=4)
    assert np.allclose(model.centers, np.linspace(0.04, 0.54, 4))
    assert not np.allclose(model.centers, np.array([0.12, 0.20, 0.28, 0.34]))
