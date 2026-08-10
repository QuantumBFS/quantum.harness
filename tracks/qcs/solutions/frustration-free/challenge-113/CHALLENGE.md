### Released by

[Lei Wang (王磊)](https://wangleiphy.github.io), Institute of Physics, Chinese Academy of Sciences

### Contact email

wangleiphy@gmail.com

### Method

Differentiable programming / quantum optimal control

### Challenge issue

> Track: quantum control · differentiable programming
> Difficulty: advanced (comfortable with autodiff, quantum dynamics, and reading ML/physics papers)
> Compute: one GPU per team is enough for the week
> Starting notebook: a differentiable quantum-control notebook (link below) — fork it and build outward

Calibrating a quantum gate on real hardware is slow and expensive: every trial is a physical experiment, and there are far more pulse parameters to tune than you can afford to explore blindly. But here is the surprise — most of those parameters do not matter. Hidden in the geometry of the control problem is a small set of directions, exactly $d^2 - 1$ of them, that carry everything; all the rest are free. Your job this week is to find those directions in a cheap, differentiable simulator and use them to calibrate a device you can only poke at, reaching target fidelity in a fraction of the experiments. That device can be a black box you build in software — or, for the bold, a real superconducting quantum computer on a Hefei cloud. It is a clean piece of sim-to-real physics, it starts from a single notebook you can fork today, and done well it is a publishable result.

## The problem

There are two ways to find a control pulse for a quantum gate, and they have opposite strengths.

The **open-loop** way uses a *model* of the device. You write down the drift Hamiltonian and the control Hamiltonians, simulate the Schrödinger equation, differentiate through the simulation, and optimize the pulse in software. This is the classic gradient-based optimal-control idea (GRAPE, Khaneja et al. 2005), made especially convenient by modern automatic differentiation: exact gradients, fast and precise. Its weakness is that the answer is only as good as the model, and no model matches the real chip — there are always miscalibrated couplings, stray terms, and drift that you did not put in.

The **closed-loop** way puts the real device in the loop. You apply a pulse, *measure* the fidelity on hardware, feed that number back to an optimizer, and repeat. This is adaptive feedback control, an old and powerful idea (Judson & Rabitz 1992) that is now routine for calibrating real qubits (Kelly et al. 2014). It corrects for everything the model got wrong. Its weakness is cost: every evaluation is a real experiment costing many measurement shots, and because you cannot differentiate through hardware, you are stuck with *derivative-free* optimization, whose number of experiments grows quickly with the number of pulse parameters.

So one loop is cheap but wrong, and the other is right but expensive. The best real-world methods combine them — optimize open-loop on the model, then refine closed-loop on the device (Egger & Wilhelm 2014). This challenge is about making that combination *efficient*, using a structural fact about control landscapes that tells you exactly where the expensive closed-loop effort should go.

## The observation you will exploit

Optimize the model to a target gate and look at the Hessian of the infidelity at the optimum. Writing the final propagator as $U(T) = U_{\text{target}} e^{iA}$ for a small Hermitian generator $A$ (a $d\times d$ Hermitian matrix, so $d^2$ real directions), the infidelity expands to second order as

```math
\mathcal{L} \;\approx\; \frac{1}{2d}\,\mathrm{Tr}\!\left[\Big(A - \tfrac{\mathrm{Tr}\,A}{d}\,I\Big)^{\!2}\right].
```

This only sees the traceless part of $A$. The identity direction, $A \propto I$, is a global phase, and the fidelity is phase-blind because of the absolute value in $\tfrac{1}{d}\lvert\mathrm{Tr}(U^\dagger U_{\text{target}})\rvert$; so that one direction is flat. The remaining traceless Hermitian directions form $\mathfrak{su}(d)$ and carry all the curvature — exactly $d^2-1$ of them (15 for a two-qubit gate), no matter how many Fourier or piecewise-constant parameters your pulse has. The extra parameters do not add curvature; they enlarge a flat *solution manifold* of pulses that all realize the gate equally well.

That the effective dimension of a control landscape is set by the size of the state space rather than by the number of control knobs is a known feature (Shen, Hsieh & Rabitz 2006; Roslund & Rabitz 2014), and it has a close cousin in machine learning, where the Hessian of an over-parametrized network has a few large eigenvalues and a bulk near zero (Sagun et al. 2017). It also rests on controllability: for a controllable system with enough resources the landscape is trap-free (Rabitz, Hsieh & Rosenthal 2004), which is why the model optimizer converges so cleanly in the first place.

Two consequences drive the whole challenge:

- The number of directions worth optimizing is an invariant of the *target*, not of your ansatz. The closed-loop search therefore has an intrinsic dimension of only $d^2-1$, even if the pulse has hundreds of parameters.
- That invariant holds only while the system stays controllable and over-resourced. Starve it — too little time, too little bandwidth — and the curved rank drops below $d^2-1$; the subspace the model hands you is then no longer the right one.

## The idea: a cheap simulator guiding an expensive reality

This is the *sim-to-real* pattern from robotics, applied to quantum control: use a cheap, differentiable simulator to do most of the thinking, then spend a small amount of expensive real-world effort where it actually matters.

| | Sim-to-real transfer | This challenge |
|---|---|---|
| Cheap, differentiable model | physics simulator | the Schrödinger model $(H_0, h_i)$, autodiff through the ODE solver |
| Expensive black box | the real robot | the true device: query-only, noisy fidelity from finite shots |
| What the model buys you | a policy to fine-tune | a warm-start pulse and the $d^2-1$ directions that matter |
| Real-world optimization | fine-tune on hardware | derivative-free search inside the $d^2-1$-dim subspace |
| Failure mode | the sim-to-real gap | the model–truth gap rotates the true subspace away from the model's |

The pipeline has three stages, and the first two are essentially the starting notebook.

1. **Open-loop, model-based.** Differentiate through the model and optimize the pulse to a model-optimal $u^\star$.
2. **Landscape extraction.** Compute the model Hessian at $u^\star$ and take its top $k$ eigenvectors $\lbrace v_1,\dots,v_k \rbrace$ with $k \approx d^2-1$. Use Hessian–vector products with a Krylov eigensolver so this scales without ever forming the full Hessian. These are your reduced coordinates.
3. **Closed-loop, model-free.** Parametrize the pulse as $u = u^\star + \sum_{j=1}^k c_j v_j$ and optimize the coefficients $c_j$ against the noisy black-box device with a derivative-free optimizer. Compare the cost of this against searching all raw parameters directly.

## What you will build

- **A model** you can differentiate: the notebook's simulator, with a drift $H_0$, control operators $h_i$, and a pulse ansatz (the notebook uses a truncated Fourier basis, in the spirit of CRAB, Caneva, Calarco & Montangero 2011).
- **A true device** you can only query: take the model and perturb it — a shifted drift $H_0^{\text{true}} = H_0 + \varepsilon V$, mis-scaled control couplings, a small unmodeled term — then return a fidelity *estimated from a finite number of measurement shots*, so the returned number is noisy. Your code may call this device and read its scalar output, but may not differentiate through it or inspect its internals. The gap size $\varepsilon$ and the shot budget are your experimental knobs. This is what turns a software exercise into a genuine sim-to-real problem.
- **The three-stage pipeline** above, with the closed-loop stage driven by a derivative-free optimizer (Nelder–Mead, CMA-ES, or Bayesian optimization).

## Core task and questions

The core deliverable is one plot: black-box queries to reach a target fidelity (say $1-F \le 10^{-3}$ on the true device) versus the dimension of the search space, showing that the model-informed subspace reaches the target with far fewer experiments than the full-parameter search. Build that, then push on the questions that make it research.

1. **The saving.** How many device queries — and how many total measurement shots — does each method need to hit the target? Sweep the subspace dimension $k$: too small and the search plateaus below target because it cannot reach the true optimum; too large and it wastes queries. Is the sweet spot near $d^2-1$?
2. **The failure mode.** As the model–truth gap $\varepsilon$ grows, the true device's relevant subspace rotates away from the model's $d^2-1$ directions. When does the model subspace stop being good enough? Does carrying a few extra directions as a safety margin, or re-estimating the subspace from device data as you go, recover the advantage?
3. **The invariant.** Does the required subspace dimension track $d^2-1$ across systems — a single-qubit gate ($d=2$, three directions), a two-qubit gate ($d=4$, fifteen), a three-qubit gate ($d=8$, sixty-three)? Confirming this shows the method is not tuned to one case.
4. **Noise.** Finite shots make the black box noisy, and derivative-free search in high dimensions suffers most from noise. Quantify how the subspace reduction changes the query count as a function of shot budget.

## Getting started

- **Start from the notebook.** It already integrates the Schrödinger equation through a differentiable ODE solver, optimizes a pulse to a target gate, and computes the Hessian and its principal directions — so stages 1 and 2 are largely in place. The sandbox cell that perturbs the optimum along the top eigenvectors and watches the loss barely move is a direct preview of the reduced coordinates you will search in.
- **Scale stage 2 with Hessian–vector products.** For larger $d$, use `hvp` plus a Krylov eigensolver (`scipy.sparse.linalg.eigsh`) rather than forming the full Hessian; the notebook sets this up. The autodiff cookbook explains forward-over-reverse and HVPs.
- **Keep a strict model/device boundary.** The model is differentiable and free to call; the device is query-only, counted, and noisy. Count every device query and every shot — those counts, not wall-clock time, are the currency of closed-loop control.
- **Note on integration.** Treating the Schrödinger equation as a generic ODE can let the propagator drift from unitarity; a structure-preserving integrator avoids this, and exact gradients can also be obtained by the discrete-adjoint route (Petersson et al. 2020). This matters more as you scale up.

## Optional: close the loop on a real quantum computer

The simulated device is a faithful stand-in, but the whole point of the sim-to-real framing is that the same pipeline connects to real hardware — and in Hefei you have a pulse-level machine within reach. The superconducting cloud of the Chinese Academy of Sciences / USTC quantum platform (`quantumcomputer.ac.cn`), and its QuantumCTek (国盾量子) sibling, expose pulse-level control on a Zuchongzhi-class chip through the QCIS `PULSE` instruction: you specify a waveform with amplitude, sideband frequency, phase, and DRAG coefficient, and use the coupler and two-qubit instructions (`G`, `AACZ`) for entangling control. Programs are submitted from Python with the `pyezQ` SDK and return a measurement probability distribution over output states — exactly the noisy, model-free fidelity signal your closed loop consumes.

Pointing the pipeline at this device makes the exercise a genuine sim-to-real problem: your differentiable simulator is the model, the chip is the truth, and the model–truth gap is no longer injected by hand but is whatever the real hardware does. A convincing result — the subspace reduction cutting the number of real-hardware experiments needed to calibrate a gate, measured head-to-head against a full-parameter search on the same chip — would be publishable on its own.

Two practical points to plan for, not around:

- The `PULSE` instruction is a beta (内测) feature that must be enabled for your account. Email the platform support early to request pulse-level access, confirm which machine exposes it, and learn how runs are metered. The permission grant, not the physics, is the schedule risk.
- Pulse programs go through raw QCIS text via `pyezQ`; the friendlier gate-level SDK will not emit them. Debug the entire loop against the simulator first and spend real-device budget only on the final comparison.

Teams without access to the Chinese cloud can run the same capstone on Amazon Braket's pulse interface on a Rigetti superconducting processor, which offers arbitrary waveforms and a documented gate-calibration override flow.

## Deliverables

Scoped to a few focused days, with a tail that can become a paper.

1. A reproducible pipeline: model optimizer, landscape extractor, simulated query-only device, and subspace closed-loop optimizer, with a clean interface between the differentiable model and the black box.
2. The headline result: queries-to-target versus search dimension, with error bars over several seeds and a few model–truth gaps, comparing full-parameter and subspace search.
3. The failure-mode study: advantage versus gap size $\varepsilon$, and whether a safety margin or subspace re-estimation extends the useful range.
4. The invariant check across at least two system sizes, testing the $d^2-1$ prediction.
5. A short report or notebook and a pull request, including one honest account of a case where the reduction failed and what you learned from it.

## Judging

- Correctness and reproducibility of the three-stage pipeline, with a clean model/black-box boundary.
- Rigor of the headline comparison: real baselines, honest query and shot counting, error bars.
- Depth on the failure mode — the model–truth gap is where the physics is.
- Insight connecting the empirical subspace dimension to the $d^2-1$ prediction.
- Clarity.

Bonus: a data-driven rule for choosing the subspace dimension; a demonstration that iterative subspace re-estimation beats a fixed subspace when the model is poor; or a closed-loop calibration run on real superconducting hardware.

## The part that makes it research

The clean version — extract $d^2-1$ directions from the model, search only those on hardware — works when the model is good. The interesting question is what happens when it is not. A large model–truth gap rotates the true relevant subspace, so the model's directions no longer span where the real optimum lives, and the reduced search converges to the wrong pulse. Detecting that, and deciding when to widen the subspace, when to re-estimate it from device data, and when to fall back to a full search, is the real content. This is the quantum-control version of the sim-to-real gap, and it is exactly the regime the Ad-HOC method (Egger & Wilhelm 2014) was built for — you are making that idea sharper by asking not just *how* to refine on hardware, but in *which* few directions.

## Research extensions

- **Close the loop on the subspace itself:** use device feedback to update the reduced coordinates, not only the coefficients within them.
- **The other side of the invariant:** shorten the control time toward the quantum speed limit and watch the curved rank fall below $d^2-1$. There the landscape itself changes character and optimal control becomes genuinely hard — a glassy phase with exponentially many near-degenerate near-optima (Day et al. 2019). Map where your subspace method must give up because the geometry, not just the model, has changed.
- **Connect to variational quantum algorithms.** The same controllability and dimension-counting ideas explain when quantum models are trainable and when they hit barren plateaus (Larocca et al. 2022; Larocca et al. 2023). A clean bridge between your control-landscape measurements and that language would be a strong result.
- **Better black-box optimizers:** trust-region or Bayesian methods that exploit the known low intrinsic dimension.
- **A realistic device:** two coupled transmons with leakage out of the computational subspace, where the model–truth gap and the shot noise are physically grounded.

## Resources

**Starting notebook.** A differentiable quantum-control notebook (fork this): https://colab.research.google.com/drive/1T0_sJMwmk7rbpxHMcBZwdD9pnYZx93oh — it integrates the time-dependent Schrödinger equation with a differentiable ODE solver, optimizes a pulse to a target gate, and analyzes the control landscape through its Hessian.

**Optimal control — the two loops.**
- N. Khaneja, T. Reiss, C. Kehlet, T. Schulte-Herbrüggen, S. J. Glaser, "Optimal control of coupled spin dynamics: design of NMR pulse sequences by gradient ascent algorithms," *J. Magn. Reson.* **172**, 296–305 (2005). [doi:10.1016/j.jmr.2004.11.004](https://doi.org/10.1016/j.jmr.2004.11.004) — GRAPE, the gradient-based open-loop method.
- T. Caneva, T. Calarco, S. Montangero, "Chopped random-basis quantum optimization," *Phys. Rev. A* **84**, 022326 (2011). [arXiv:1103.0855](https://arxiv.org/abs/1103.0855) — the truncated-basis pulse ansatz the notebook uses.
- N. A. Petersson et al., "Discrete Adjoints for Accurate Numerical Optimization with Application to Quantum Control," [arXiv:2001.01013](https://arxiv.org/abs/2001.01013) (2020) — exact gradients through the dynamics with a structure-preserving integrator.
- R. S. Judson, H. Rabitz, "Teaching lasers to control molecules," *Phys. Rev. Lett.* **68**, 1500 (1992). [doi:10.1103/PhysRevLett.68.1500](https://doi.org/10.1103/PhysRevLett.68.1500) — the origin of closed-loop / adaptive feedback control.
- D. J. Egger, F. K. Wilhelm, "Adaptive Hybrid Optimal Quantum Control for Imprecisely Characterized Systems," *Phys. Rev. Lett.* **112**, 240503 (2014). [arXiv:1402.7193](https://arxiv.org/abs/1402.7193) — Ad-HOC: open-loop model optimization plus closed-loop experimental refinement.
- J. Kelly et al., "Optimal Quantum Control Using Randomized Benchmarking," *Phys. Rev. Lett.* **112**, 240504 (2014). [arXiv:1403.0035](https://arxiv.org/abs/1403.0035) — closed-loop calibration of superconducting-qubit gates.

**Control landscapes and their dimensionality.**
- H. A. Rabitz, M. M. Hsieh, C. M. Rosenthal, "Quantum Optimally Controlled Transition Landscapes," *Science* **303**, 1998–2001 (2004). [doi:10.1126/science.1093649](https://doi.org/10.1126/science.1093649) — controllable systems have trap-free landscapes.
- Z. Shen, M. Hsieh, H. Rabitz, "Quantum optimal control: Hessian analysis of the control landscape," *J. Chem. Phys.* **124**, 204106 (2006). [doi:10.1063/1.2198836](https://doi.org/10.1063/1.2198836) — the Hessian rank is set by the number of participating states.
- J. Roslund, H. Rabitz, "Dynamic Dimensionality Identification for Quantum Control," *Phys. Rev. Lett.* **112**, 143001 (2014). [doi:10.1103/PhysRevLett.112.143001](https://doi.org/10.1103/PhysRevLett.112.143001) — the effective search dimension is set by the state space, not the number of controls.
- L. Sagun, U. Evci, V. U. Guney, Y. Dauphin, L. Bottou, "Empirical Analysis of the Hessian of Over-Parametrized Neural Networks," [arXiv:1706.04454](https://arxiv.org/abs/1706.04454) (2017; ICLR 2018 Workshop) — the machine-learning parallel: a few large Hessian eigenvalues, a bulk near zero.

**Hardness, and the bridge to quantum machine learning.**
- A. G. R. Day, M. Bukov, P. Weinberg, P. Mehta, D. Sels, "Glassy Phase of Optimal Quantum Control," *Phys. Rev. Lett.* **122**, 020601 (2019). [arXiv:1803.10856](https://arxiv.org/abs/1803.10856) — a spin-glass-like hard phase near the quantum speed limit.
- M. Larocca, P. Czarnik, K. Sharma, G. Muraleedharan, P. J. Coles, M. Cerezo, "Diagnosing Barren Plateaus with Tools from Quantum Optimal Control," *Quantum* **6**, 824 (2022). [arXiv:2105.14377](https://arxiv.org/abs/2105.14377) — control-landscape geometry and VQA trainability.
- M. Larocca, N. Ju, D. García-Martín, P. J. Coles, M. Cerezo, "Theory of overparametrization in quantum neural networks," *Nat. Comput. Sci.* **3**, 542–551 (2023). [doi:10.1038/s43588-023-00467-6](https://doi.org/10.1038/s43588-023-00467-6) — the overparametrization phase transition.

**Real hardware for the optional capstone.**
- 中国科学院 / USTC quantum computing cloud (Hefei): [quantumcomputer.ac.cn](https://quantumcomputer.ac.cn/) — pulse-level control through the QCIS `PULSE` instruction and the `pyezQ` Python SDK ([instruction reference](https://docs.quantumcomputer.ac.cn/Appendix/C2/), [getting started](https://docs.quantumcomputer.ac.cn/Start/1/)). The `PULSE` instruction is a beta feature; request access from platform support in advance.
- 国盾量子 (QuantumCTek) cloud (Hefei): the same QCIS pulse instruction on a sibling stack — [docs.quantumctek-cloud.com](https://docs.quantumctek-cloud.com/Start/4/).
- Non-China alternative: [Amazon Braket Pulse](https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse.html) on Rigetti superconducting processors — arbitrary waveforms and a native-gate [calibration override](https://docs.aws.amazon.com/braket/latest/developerguide/braket-native-gate-pulse.html) flow.

**Tools.** JAX (autodiff through the ODE, Hessian–vector products; see the [autodiff cookbook](https://jax.readthedocs.io/en/latest/notebooks/autodiff_cookbook.html)); SciPy (`Nelder-Mead`, `L-BFGS-B`, `eigsh`); a CMA-ES or Bayesian-optimization library for the closed-loop stage.


