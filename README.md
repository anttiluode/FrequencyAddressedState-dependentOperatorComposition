# Frequency-Addressed State-Dependent Operator Composition

Question: can frequency select a resident operator, can one addressed event change the operator encountered by the next event, and does A→B differ from B→A after fast resonant state has died?

## v0 — isolate the mechanism before putting the cable back

v0 deliberately uses a reduced resident-mode substrate, not a dendritic cable. The gate requires three things at once:

1. Different carrier frequencies excite different mixtures of resident modes.
2. Local modal activity writes slow resident state that changes the later transfer operator.
3. A→B and B→A produce different later operators after a long quiet interval.

The fast modes are damped complex resonators. Slow state is indexed by resident modes, not by requested frequency: there is no explicit frequency-addressed memory register. There is also no slow decay in v0, removing the trivial explanation that the most recent event simply had less time to fade.

## Frozen v0 result

| quantity | full local | global-scalar | frozen operator | homogeneous address |
|---|---:|---:|---:|---:|
| address effective rank | 3.443 | 3.443 | 3.443 | 1.000 |
| single-write operator rank | 3.078 | 1.152 | 0.000 | 1.398 |
| A→B vs B→A commutator ratio | 0.564 | 0.114 | 0.000 | 0.309 |
| order effect / write-jitter scale | 3.374x | 3.101x | 0.000x | 5.000x |

Verdict: PASS_V0_OPERATOR_COMPOSITION_GATE

The controls separate three statements that are easy to blur together. A stored trace is not enough if it cannot change the later operator. Generic history dependence is not enough if different addresses all write the same one-dimensional operator direction. And A→B != B→A is not enough if A and B did not address different resident structure in the first place.

## v1 — put the cable back

v1 replaces the reduced resonators with four heterogeneous quasi-active cable branches. Every branch is a discrete passive cable plus a local recovery variable. The same carrier is injected at the distal end of every branch and the soma reads their proximal outputs.

The important restriction survived implementation: there is still no explicit frequency-indexed slow memory. Every cable compartment owns one slow material scalar. Local voltage energy writes that physical state, and the state changes local cable leakage for the next packet.

The branch geometries and quasi-active parameters are synthetic and deliberately heterogeneous so four useful resonant addresses exist. This is a mechanism experiment, not a biological parameter fit.

### Frozen v1 result

| quantity | heterogeneous local cable | global-scalar state | frozen operator | homogeneous branches |
|---|---:|---:|---:|---:|
| frequency-address effective rank | **3.977** | 3.977 | 3.977 | **1.000** |
| written-operator effective rank | **2.581** | **1.118** | **0.000** | 1.141 |
| local material write rank | **2.904** | 3.233 | 3.208 | 1.146 |
| A→B vs B→A commutator ratio | **0.0612** | 0.0210 | **0.000** | 0.0645 |
| paired order effect / write-jitter | **3.602x** | 1.895x | 0.000x | 7.858x |
| max fast residual after settling | **4.75e-6** | 8.04e-7 | 1.01e-4 | 2.67e-9 |

Verdict: PASS_V1_CABLE_OPERATOR_COMPOSITION_GATE

The pattern is the useful part.

- Heterogeneous cable branches make one physical drive frequency-address nearly four independent branch mixtures.
- Those frequency-selected spatial patterns write about 2.9 effective dimensions of compartment-local material and 2.58 effective dimensions of the later transfer operator.
- After 800 silent steps the full model's fast-state norm is below 1e-5, yet A→B and B→A still leave different later operators.
- On a common-random tape, the order effect is about 3.60x the ordinary within-order frequency/amplitude jitter scale.
- If slow material is allowed to accumulate but forbidden from changing the cable operator, the operator-write rank and commutator both collapse to zero.
- If all compartment state is collapsed to one global scalar before it acts on the cables, the written-operator family collapses to about 1.12 effective dimensions.
- If the four branches are made identical, frequency-address rank collapses to exactly 1.0. That attacker can still be order-dependent, which is why order dependence alone is not promoted to the claim.

So v1 recovers the v0 pattern in an actual cable-shaped dynamical substrate without inserting the frequency-slot memory that made the earlier engineering version too easy.

## What this establishes — and what it does not

The synthetic statement is now narrower and stronger:

    carrier frequency
        -> different heterogeneous cable mixture
        -> different compartment-local slow write
        -> changed cable transfer operator
        -> next packet sees a state-conditioned operator
        -> A then B differs from B then A after fast state is gone

It still does not establish that real dendrites use frequency carriers this way, that this slow material law corresponds to a particular biological mechanism, or that the architecture is computationally preferable to a standard state-space system. The next useful attacker is therefore not another biological embellishment. It is a matched ordinary dynamical system asked to reproduce the same externally observable operator family and composition under the same state budget.

## Run

    python -m pip install -e '.[test]'
    pytest -q
    python -m frequency_operator_composition.experiment --output results/v0.json
    python -m frequency_operator_composition.cable_experiment --output results/v1_cable.json

The committed receipts are compact summaries. Running either experiment writes the full deterministic diagnostic JSON.

## Repository layout

    src/frequency_operator_composition/core.py              reduced v0 resident modes
    src/frequency_operator_composition/experiment.py        v0 gate + attackers
    src/frequency_operator_composition/cable.py             v1 quasi-active cables
    src/frequency_operator_composition/cable_experiment.py  v1 gate + attackers
    tests/                                                   mechanism and frozen-gate tests
    results/                                                 compact committed receipts
    index.html                                               static result microscope

## Lineage

The immediate parent is FrequencyAddressedNonlinearModalCell: hidden matter, sparse stimulation language, frequency as an external address coordinate, and strong boring attackers. The conceptual ancestry also runs through NotSoSimpleNeuron, where receiver state changes what the next event encounters; InformationFlow, where space/frequency/phase form an address; and Operaattori, where physical morphology compiles into an operator.

The question here is deliberately narrower:

**When does an address select not just a channel or memory slot, but a state-conditioned operator whose composition has an order?**
