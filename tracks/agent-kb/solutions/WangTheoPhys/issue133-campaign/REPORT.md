# Issue #133 five-new-problem campaign

Human supervisor: `human.junkaiwang` (`human expert supervision`).

| # | New problem | Human acceptance receipt | Solved receipt | Exact result |
|---:|---|---|---|---|
| 1 | `issue133.new-01-exact-mpo-rank` | `sha256:cbd11366655b89f9347281dfd941a65cbba0cf252c725d2c5d37514c984a93fb` | `sha256:7abaa0516f4b925c7cec90defbb6df431e0543a8b3594365a3955cd75f002ac4` | `{"exact_rank":2,"factor_inner_dimension":2,"minor_determinant":1}` |
| 2 | `issue133.new-02-optimal-contraction` | `sha256:724be8cb35071ff8f4b6ad97de66585ccfdf8927adc9ace43d494661103d67dd` | `sha256:f9e27d6bccbaa7ab64b6ef1bc5c2cd5bddfa857fd95eb00e6b705638eb85b638` | `{"enumerated_parenthesizations":5,"minimum_cost":56,"optimal_count":1}` |
| 3 | `issue133.new-03-transfer-gap` | `sha256:2eede6363bf3489d04179b5b9c073b5b94cdc25ee310a46a42e9764a2f671459` | `sha256:2095537877409ccb30017cf67ed48085dcec6a0ccbfe1031a8175544d2bb6c45` | `{"basis_determinant":-2,"eigenvalues_descending":[4,2,1],"spectral_gap":2}` |
| 4 | `issue133.new-04-schmidt-rank` | `sha256:4d68b2c91ddcb1aaefc930ebfe7cc3cfdec1b06c7a0b6f66007467a8e520a03d` | `sha256:8097b130ef5016bb44b2ffc15d898e177ca67d9fdab4c0cf10ae9498425a0dac` | `{"exact_rank":2,"factor_inner_dimension":2,"minor_determinant":1}` |
| 5 | `issue133.new-05-mps-gauge-equivalence` | `sha256:11a9d32a78bedb0e4b63ae78a30ac603e0b699f87c9c249484923edfd667ee35` | `sha256:f5a6435a92a4c617db890a613a2b85e850f52754b576d12e0920faef35553676` | `{"bond_dimension":2,"gauge_determinant":1,"verified_slices":2}` |

## Counters

- human-accepted new problems: `5 / 5`
- exact solved gates: `5 / 5`
- rejected negative controls: `5 / 5`
- refereed publications: `0`

## Replay

```bash
python3 tracks/agent-kb/solutions/WangTheoPhys/issue133-campaign/run_campaign.py
python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/issue133-campaign/tests -v
```

## Trust boundary

The campaign supplies human-supervised acceptance and exact machine gate evidence. QuantumBFS maintainers control upstream catalog/tier determination; refereed publication is 0.
