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

### Why the attackers matter

- Frozen operator: frequency addressing remains, but slow material is denied causal influence. Operator change and the order commutator collapse to zero.
- Global scalar: history can still matter, but four frequency writes collapse to about 1.15 effective operator dimensions. Generic memory is weaker than address-specific operator rewrite.
- Homogeneous resident modes: order effects can still exist, but frequency-address rank collapses to 1.0. A→B != B→A alone is not enough.

So the gate requires both an addressable resident operator family and state-dependent noncommuting rewrite.

## Claim boundary

This is a synthetic reduced resonator model. It does not establish that biological dendrites use carrier frequency this way, that a cable naturally supplies the slow rewrite law, or that the architecture beats standard recurrent/state-space systems.

## Next gate

v1 puts heterogeneous quasi-active cable branches back into the machine. The strict rule is: no explicit slow[frequency_band] register. Slow state must live on physical branch/mode state. The same A→B / B→A gate and frozen/global/homogeneous attackers will be reused, followed by a matched linear/state-space attacker.

## Run

    python -m pip install -e '.[test]'
    pytest -q
    python -m frequency_operator_composition.experiment --output results/v0.json

Lineage: FrequencyAddressedNonlinearModalCell → this repo, with conceptual ancestry from NotSoSimpleNeuron, InformationFlow, and Operaattori.
