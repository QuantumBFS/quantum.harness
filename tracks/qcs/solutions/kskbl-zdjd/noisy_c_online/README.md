# Online noisy-C recovery

This experiment treats the six-bit Task C input-output map as hidden from the
learner. Every optimization step samples 100 fresh 12-bit inputs, queries a
separate data-stream oracle, and independently flips output bits before the
learner receives them. The learner is randomly initialized and may not read
the known 156-gate circuit or the clean full-domain evaluator.

The clean 4096-input domain is used only by an isolated evaluation path. It
records convergence curves and never contributes gradients, model selection,
mutation acceptance, or stopping decisions.

The initial protocol uses a 25% output-bit flip rate. This attenuates the clean
binary signal by a factor of one half and inflates the idealized sample
complexity by a factor of four, making convergence measurable while preserving
learnability.

Bulk checkpoints and raw trajectories belong under:

`tracks/qcs/results/20260730-154500-challenge-noisy-c-online/`

