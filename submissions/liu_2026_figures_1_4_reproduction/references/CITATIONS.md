# References and source boundary

## Original challenge

QuantumBFS/quantum.harness Issue #113, “[challenge]: Sim-to-Real for Quantum
Gates,” released by Lei Wang, Institute of Physics, Chinese Academy of
Sciences, 17 July 2026.

- Issue: <https://github.com/QuantumBFS/quantum.harness/issues/113>
- Local structured summary: `ISSUE_113.md`

The issue defines the open-loop model, Hessian extraction, and query-only
closed-loop stages; it also defines the required query/dimension, gap,
system-size, and noise studies used in this submission’s completion audit.

## Primary paper

Genyue Liu, Guillaume Bornet, Deniz Kurdak, Mingxuan Xiao, Chenyuan Li,
Bichen Zhang, and Jeff D. Thompson, “High-fidelity neutral atom gates
leveraging low-rank Hessian optimization,” arXiv:2606.05060v1 (2026).

- Abstract page: <https://arxiv.org/abs/2606.05060>
- DOI: <https://doi.org/10.48550/arXiv.2606.05060>
- Local rendered copy: `liu_2026_paper_rendered.md`

The local rendered copy contains the paper’s own bibliography and is the
source for the Hamiltonian, pulse-family constraints, parameters, target
figures, Table-I probabilities, and Appendix-E error anchors used here.

## Fluorescence calibration

A. G. Radnaev et al., “A universal neutral-atom quantum computer with
individual optical addressing and non-destructive readout,” PRX Quantum 6,
030334 (2025), arXiv:2408.08288v3, especially Methods 6.8.2.

- Source: <https://arxiv.org/abs/2408.08288>
- Calibration file:
  `../source/simulator/data/published/radnaev_2025_ndssr_fit.json`

Only the published numerical fit summary is used. Raw camera frames were not
public and are not included. This calibration describes a different
neutral-atom apparatus and is used only to exercise the camera-analysis
pipeline.

## Erasure-conversion context

Bichen Zhang et al., “Leveraging erasure errors in logical qubits with
metastable 171Yb atoms,” arXiv:2506.13724v1 (2025).

- Source: <https://arxiv.org/abs/2506.13724>
- Local rendered copy: `zhang_2025_erasure_context.md`

This is contextual literature for the erasure/postselection interpretation;
it is not a source of the independently computed Hessian values.

## Parallel neutral-atom gate context

Simon J. Evered et al., “High-fidelity parallel entangling gates on a
neutral-atom quantum computer,” Nature 622, 268–272 (2023),
arXiv:2304.05420.

- Source: <https://doi.org/10.1038/s41586-023-06481-y>
- Local rendered metadata and abstract: `evered_2023_parallel_gates.md`

This paper informs the selection of realistic neutral-atom error mechanisms
and leakage/noise sensitivity checks. Its rubidium intermediate-state model is
not copied into the single-photon ytterbium Hamiltonian.

## Software source

- Collaborator simulator:
  <https://github.com/thy10817/Sim-to-real-simulation>
- Source commit:
  `c9e4066e61767f77afc10611a227a7d6f0c3a4ac`
- Bundled simulator modules: `../source/simulator/src/cs_tweezer_sim/`
- Bundled reproduction modules: `../source/reproduce/`
- Local simulator-to-input bridge:
  `../source/liu_2026_simulator_input_bridge.py`
- Complete Figure-4 digital-twin runner:
  `../source/liu_2026_complete_digital_twin.py`

Runtime libraries are declared in `../source/reproduce/requirements.txt` and
`../source/simulator/pyproject.toml`. NumPy/SciPy perform propagation and
optimization, JAX x64 performs the differentiable robust-control/Hessian
stages, QuTiP supplies the multilevel open-system backend, and matplotlib
renders the figures.

## Explicitly unavailable source material

- Liu et al. experimental shot records and raw photon-count arrays
- the authors’ numerical 400-bin AR phase array
- the measured AOM transfer function and microscopic noise spectra
- the experiment-specific MQDT pair-interaction table

No file in this submission should be interpreted as a recovered copy of those
unpublished sources.

Machine-readable BibTeX for these references is in `references.bib`.
