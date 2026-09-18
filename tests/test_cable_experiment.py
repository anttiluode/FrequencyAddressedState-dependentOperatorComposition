from frequency_operator_composition.cable_experiment import run_v1


def test_frozen_v1_cable_gate():
    result = run_v1()
    assert result["verdict"] == "PASS_V1_CABLE_OPERATOR_COMPOSITION_GATE"
    assert all(result["criteria"].values())
