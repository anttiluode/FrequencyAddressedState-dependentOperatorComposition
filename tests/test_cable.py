import numpy as np

from frequency_operator_composition.cable import CableCell, homogeneous_specs, run_cable_sequence


def test_heterogeneous_cables_create_frequency_dependent_branch_mix():
    cell = CableCell()
    low = cell.address_profile(0.12)
    high = cell.address_profile(0.34)
    cosine = float(low @ high / (np.linalg.norm(low) * np.linalg.norm(high)))
    assert 1.0 - cosine > 0.8


def test_homogeneous_branch_attacker_collapses_frequency_address():
    cell = CableCell(branch_specs=homogeneous_specs())
    low = cell.address_profile(0.12)
    high = cell.address_profile(0.34)
    assert np.allclose(low, high, atol=1e-10)


def test_order_effect_survives_fast_state_settling_and_needs_causal_material():
    probes = np.linspace(0.06, 0.50, 20)
    ab = run_cable_sequence([0.20, 0.34])
    ba = run_cable_sequence([0.34, 0.20])
    assert ab.fast_norm() < 1e-5
    assert ba.fast_norm() < 1e-5
    assert np.linalg.norm(ab.operator_vector(probes) - ba.operator_vector(probes)) > 1e-3

    frozen_ab = run_cable_sequence([0.20, 0.34], state_mode="frozen")
    frozen_ba = run_cable_sequence([0.34, 0.20], state_mode="frozen")
    assert np.linalg.norm(frozen_ab.operator_vector(probes) - frozen_ba.operator_vector(probes)) < 1e-10
