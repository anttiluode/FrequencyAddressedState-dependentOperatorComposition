import numpy as np

from frequency_operator_composition.core import MatterConfig, ResidentModalMatter, run_sequence


def test_frequency_addresses_distinct_resident_mode_mixtures():
    matter = ResidentModalMatter()
    low = matter.address_profile(0.19)
    high = matter.address_profile(0.41)
    cosine = float(low @ high / (np.linalg.norm(low) * np.linalg.norm(high)))
    assert 1.0 - cosine > 0.5


def test_fast_state_is_gone_after_settle_but_material_remains():
    matter = ResidentModalMatter()
    matter.write(0.25)
    matter.settle(320)
    assert np.linalg.norm(matter.fast) < 1e-5
    assert np.linalg.norm(matter.material) > 1e-3


def test_order_changes_operator_only_when_slow_state_is_causal():
    probes = np.linspace(0.12, 0.50, 16)
    full_ab = run_sequence([0.21, 0.39])
    full_ba = run_sequence([0.39, 0.21])
    full_difference = np.linalg.norm(full_ab.operator_vector(probes) - full_ba.operator_vector(probes))
    assert full_difference > 0.5

    frozen = MatterConfig(state_mode="frozen")
    frozen_ab = run_sequence([0.21, 0.39], config=frozen)
    frozen_ba = run_sequence([0.39, 0.21], config=frozen)
    frozen_difference = np.linalg.norm(frozen_ab.operator_vector(probes) - frozen_ba.operator_vector(probes))
    assert frozen_difference < 1e-10
