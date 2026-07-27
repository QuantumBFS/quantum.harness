# Insights

## Selected

### Hessian Principal-Space Calibration
- **Technique**: Optimize the differentiable model to a high-fidelity pulse, compute the fidelity Hessian at that pulse, keep the leading eigenvectors, and use them as closed-loop calibration coordinates. The intended invariant is not the raw pulse dimension but the number of physically visible gate-error channels, with a generic computational-subspace ceiling of `d^2 - 1`.
- **Applies when**: The open-loop pulse is close enough to the real optimum for a local quadratic approximation to be useful, the model and device share the relevant controllable subspace, and the benchmark can measure exact/noisy infidelity separately.
- **Limits**: Large model-truth gaps, additional leakage channels, symmetry changes, bandwidth starvation, or operation near a hard control-time boundary can rotate or shrink the true sensitive subspace so the model Hessian no longer spans the needed correction.
- **Sources**: [liu_2026_high](../.knowledge/2606.05060_high-fidelity-neutral-atom-gates-leveraging-low-rank-hessian.md), [roslund_2014_dynamic](../.knowledge/10-1103-physrevlett-112-143001.md), [shen_2006_quantum](../.knowledge/10-1063-1-2198836.md).

### Hybrid Open/Closed-Loop Calibration Boundary
- **Technique**: Split the pipeline into a free differentiable model loop and an expensive scalar device loop. Use model gradients only before the boundary, then run derivative-free updates against noisy fidelity estimates while counting every query and shot.
- **Applies when**: The device can return a scalar performance estimate such as randomized-benchmarking fidelity or a simulated finite-shot proxy, and the closed-loop optimizer starts from a model pulse that is already close to useful.
- **Limits**: If fidelity-estimation noise is larger than the typical per-iteration improvement, closed-loop progress stalls even when the optimizer would improve in a noiseless setting. The optimizer must also be prevented from reading private true-device Hamiltonian data.
- **Sources**: [egger_2014_adaptive](../.knowledge/1402.7193_adaptive-hybrid-optimal-quantum-control-for-imprecisely-char.md), [judson_1992_teaching](../.knowledge/10-1103-physrevlett-68-1500.md).

### Fair Low-Dimensional Black-Box Benchmarking
- **Technique**: Compare Hessian subspaces against both full raw-parameter search and random subspaces under identical initial pulses, seeds, shot budgets, stopping rules, and optimizer families. Report median queries-to-target, total shots, and final exact true infidelity.
- **Applies when**: The goal is to demonstrate a real experimental saving rather than only a nicer model loss curve. The benchmark should sweep `k`, model-gap size, and shot budget.
- **Limits**: A single seed, a weak full-space baseline, cherry-picked `k`, or stopping on noisy fidelity alone can make the Hessian method look better than it is.
- **Sources**: [egger_2014_adaptive](../.knowledge/1402.7193_adaptive-hybrid-optimal-quantum-control-for-imprecisely-char.md), [liu_2026_high](../.knowledge/2606.05060_high-fidelity-neutral-atom-gates-leveraging-low-rank-hessian.md), [larocca_2021_diagnosing](../.knowledge/2105.14377_diagnosing-barren-plateaus-with-tools-from-quantum-optimal-c.md).

### Pulse Parameterization Without Baseline Leakage
- **Technique**: Use a compact pulse basis, such as truncated Fourier/CRAB coefficients or carrier-wave B-splines, for the raw control vector; then derive Hessian directions inside that same raw vector. The full-search baseline must optimize the same raw vector the Hessian method projects from.
- **Applies when**: The simulator needs enough pulse degrees of freedom to expose flat solution directions while staying cheap enough for repeated Hessian and black-box runs.
- **Limits**: Too few pulse parameters can fake a low-rank result by underparametrizing the problem; too many with a poor optimizer can make the full baseline unfairly bad.
- **Sources**: [caneva_2011_chopped](../.knowledge/1103.0855_chopped-random-basis-quantum-optimization.md), [petersson_2020_discrete](../.knowledge/2001.01013_discrete-adjoints-for-accurate-numerical-optimization-with-a.md).

### Hessian Numerics And Verification
- **Technique**: Start with explicit Hessians for tiny systems, then move to Hessian-vector products plus Krylov eigensolvers as dimension grows. Validate gradients/HVPs by finite differences, track unitarity drift, and separate compilation/path-search/warm runtime when JAX or tensor-network backends enter.
- **Applies when**: A small one- or two-qubit benchmark is used for the first pass, but the code path should not assume full Hessian materialization forever.
- **Limits**: Generic ODE integration can drift from unitarity; approximate gradients can dominate near high fidelity; tiny eigenvalues need a rank threshold rather than exact equality to zero.
- **Sources**: [petersson_2020_discrete](../.knowledge/2001.01013_discrete-adjoints-for-accurate-numerical-optimization-with-a.md), [dalgaard_2020_hessian](../.knowledge/2006.00935_hessian-based-optimization-of-quantum-dynamics-under-constra.md), [sagun_2017_empirical](../.knowledge/1706.04454_empirical-analysis-of-the-hessian-of-over-parametrized-neura.md).

### Failure Boundary As The Research Result
- **Technique**: Treat failure as signal: sweep model-truth perturbation, measure whether the true optimum remains reachable in the fixed model Hessian subspace, and test safety margins or subspace refresh only after the fixed-subspace boundary is visible.
- **Applies when**: The first headline plot already shows some saving, and the next question is when the saving disappears.
- **Limits**: If the model gap is too easy, every method succeeds and no boundary appears; if it is too hard, the open-loop warm start is not meaningful and the reduced search has no fair chance.
- **Sources**: [liu_2026_high](../.knowledge/2606.05060_high-fidelity-neutral-atom-gates-leveraging-low-rank-hessian.md), [egger_2014_adaptive](../.knowledge/1402.7193_adaptive-hybrid-optimal-quantum-control-for-imprecisely-char.md), [day_2018_glassy](../.knowledge/1803.10856_glassy-phase-of-optimal-quantum-control.md).

## Shelved

### Dynamical-Lie-Algebra Trainability Bridge
- **Technique**: Use dynamical Lie algebra dimension and subspace controllability to connect the observed Hessian rank to VQA trainability, barren plateaus, and overparametrization thresholds.
- **Applies when**: The control benchmark has already validated the `d^2 - 1` picture across at least two system sizes and needs broader theoretical framing.
- **Limits**: This is not necessary for the first calibration demo and can distract from query-count/shots evidence.
- **Sources**: [larocca_2021_diagnosing](../.knowledge/2105.14377_diagnosing-barren-plateaus-with-tools-from-quantum-optimal-c.md), [larocca_2021_theory](../.knowledge/10-1038-s43588-023-00467-6.md).

### Glassy Near-Speed-Limit Regime
- **Technique**: Shorten the control time and look for a rank drop, many near-optimal clusters, or optimizer sensitivity that signals the control landscape has entered a hard/glassy regime.
- **Applies when**: The base model works and the team has compute budget for a second study.
- **Limits**: It changes the task from calibration savings to landscape physics; useful later, too much for the first pass.
- **Sources**: [day_2018_glassy](../.knowledge/1803.10856_glassy-phase-of-optimal-quantum-control.md).

### Real-Hardware Pulse Capstone
- **Technique**: Replace the simulated oracle with a pulse-level device while preserving the same scalar-oracle contract and query/shot accounting.
- **Applies when**: The simulator pipeline is fully validated and a pulse-level account is available.
- **Limits**: Account permissions and metering are schedule risks; spend hardware only after local baselines are stable.
- **Sources**: [egger_2014_adaptive](../.knowledge/1402.7193_adaptive-hybrid-optimal-quantum-control-for-imprecisely-char.md), [liu_2026_high](../.knowledge/2606.05060_high-fidelity-neutral-atom-gates-leveraging-low-rank-hessian.md).
