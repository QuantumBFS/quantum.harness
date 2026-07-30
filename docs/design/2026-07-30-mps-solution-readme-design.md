# MPS Challenge Solution README Design

## Goal and audience

Rewrite `tracks/mps/solutions/jhzhu/README.md` as the landing page for PR #218.
The primary reader is a challenge reviewer or researcher who has not followed
the calculation history. Within one minute, that reader should understand the
question, which results are reliable, which results are pilots, and where to
find the code and reproducible artifacts.

The report remains in English to match the repository and PR. It summarizes
existing evidence; it does not introduce new physics claims or copy raw cluster
outputs into Git.

## Information architecture

The README will use this reading order:

1. **Title and metadata**: team, issue #122, track, and PR scope.
2. **Executive summary**: the finite-size free-energy observable and four
   plainly labelled outcomes: clean Ising validation, RBIM Nishimori result,
   exact-state-vector Haar pilot, and dual-unitary MPS pilot/high-stat run.
3. **Result-status table**: quote the estimator, sizes/sample count, numerical
   value, uncertainty or stability range, and a status label for each stage.
4. **Method**: explain the common transfer/free-energy scaling relation, then
   distinguish matrix-free classical transfer, exact circuit trajectories, and
   finite-chi MPS contraction.
5. **Evidence and figures**: embed only tracked clean-Ising and RBIM figures and
   link the detailed Haar checkpoint. The ignored dual-unitary pilot is reported
   numerically with links to the committed analysis scripts, not to unavailable
   local files.
6. **Reproduction**: short commands grouped by experiment, with dependency
   files and output locations.
7. **Limitations and current status**: state explicitly that the Haar
   exact-state-vector checkpoint is statistically inconclusive, the
   dual-unitary L^-4 fit is unstable, and the 400-sample high-chi cluster run is
   in progress rather than a completed result.
8. **Repository map**: link the main scripts, tests, design/configuration files,
   detailed report, and machine-readable tracked results.

## Numerical claims and labels

The README will preserve the following distinctions:

- **Validation** — clean critical Ising, `L=8,10,12,16,20`, with reported
  fit-envelope midpoint `c=0.4999188` and half-width `9.94e-5`.
- **Completed finite-statistics result** — RBIM Nishimori two-hour run,
  `L=4,5,6,8,9,10,12`, primary `L^-2+L^-4` result `c=0.45846`, trajectory
  bootstrap standard error `0.00517`, and fit-window range
  `0.45788--0.50120`.
- **Inconclusive pilot** — exact-state-vector Haar circuit at `p=0.168`, 192
  trajectories, `c_eff=1.559` with bootstrap standard error `0.955`; this
  validates the workflow but is not a reproduction claim.
- **MPS pilot** — dual-unitary gates at `p=0.14`, 350 trajectories,
  chi-extrapolated `L^-2` result `c_eff=0.21996`, bootstrap standard error
  `0.04335`, and chi-threshold range `0.19199--0.22595`. The `L^-4` estimate is
  shown only as an instability diagnostic.
- **Running production** — 400 samples per `(L, chi)`, `chi<=256`, 5600
  trajectories packed into 400 resumable Slurm tasks. No numerical conclusion
  from this run appears until its artifacts are complete and analysed.

Uncertainties will always be named (fit envelope, bootstrap standard error, or
chi-threshold range) rather than combined into an ambiguous `+/-` value.

## Reproduction and verification

Commands will invoke committed scripts with explicit result directories and
will not contain usernames, hosts, passwords, or machine-specific paths.
Relative links will be checked against the repository tree. Python entry points
will be checked with `--help` or their focused tests; Markdown will be scanned
for placeholders and malformed local links.

## Non-goals

- Do not rewrite the repository root README.
- Do not turn the report into a chronological lab notebook.
- Do not commit ignored raw trajectories or the still-running cluster output.
- Do not claim a precise Haar MIPT central charge from the noisy pilot.
- Do not present the `L^-4` dual-unitary fit as a preferred estimate.
