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

## Current leading method

`train_posterior_replay.py` combines four formula-agnostic ingredients:

1. an online Bayesian teacher that accumulates only fresh noisy observations;
2. all generic Boolean parity features of degree one through three;
3. confidence-times-disagreement replay with a 20% random exploration reserve;
4. an ensemble of independently initialized students.

With 25% independent output-bit flips, four 72,844-parameter students first
recover all 4,096 clean inputs at step 1,400 in the main run. A different seed
first reaches full recovery at step 1,600. The main run remains exact at all 17
checkpoints from step 1,400 through 3,000. The replication has one transient
word error at step 1,700 and finishes exact at step 2,000.

The committed `posterior_replay_p25_summary.json` contains compact curves,
configuration, final metrics and SHA-256 hashes for the bulk artifacts.
`verify_posterior_replay.py` reloads the saved student checkpoints and checks
the recorded final metrics over the complete 4,096-input domain.

Representative rerun:

```powershell
python train_posterior_replay.py --steps 3000 --batch-size 100 --replay-batch-size 100 --noise-rate 0.25 --ensemble-size 4 --architecture parity3 --hidden 128 --depth 3 --replay-strategy active --candidate-multiplier 8 --active-exploration 0.20 --learning-rate 0.001 --minimum-learning-rate 0.00005 --eval-every 100 --base-seed 37100 --threads 12 --device cpu --output-dir <run-directory>
python verify_posterior_replay.py --run-dir <run-directory>
```

This is a recovery result, not yet a small Boolean circuit. The teacher retains
per-input posteriors during training, and each student still contains 72,844
continuous parameters. Subsequent experiments target pruning, teacher removal
and gate-level discretization.

Bulk checkpoints and raw trajectories belong under:

`tracks/qcs/results/20260730-154500-challenge-noisy-c-online/`
