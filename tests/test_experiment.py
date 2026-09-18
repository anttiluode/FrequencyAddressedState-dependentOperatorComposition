from frequency_operator_composition.experiment import run_v0


def test_frozen_v0_gate():
    result = run_v0()
    assert result["verdict"] == "PASS_V0_OPERATOR_COMPOSITION_GATE"
    assert all(result["criteria"].values())
