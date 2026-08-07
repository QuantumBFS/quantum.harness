# Overnight unattended reproduction protocol (authoritative)

This file is the goal. Execute it verbatim. Do NOT invent hypotheses, do NOT
add knobs not listed here, do NOT modify QMBCertify.

CONTEXT: our N=14 r-scan, run with rdm=false, saturated near -0.4473967, about
3e-7 below Table 3's displayed -0.4473964. QMBCertify's source-of-record 1D
Heisenberg example uses d=4, r=5, rdm=10, pso=3, lso=true, while GSB defaults
to rdm=false. Missing RDM positivity is therefore the leading, directly
testable explanation. It is NOT established as the cause. Steps 1-2 exist to
test it. Do not write it up as the cause before Step 2 returns.

## STEP 0 - provenance harness. Build this before any run.

Define ONE config object that both constructs the GSB call and serialises into
the result row. The config object is the source of truth; never hand-copy
parameters and never reconstruct them after the fact.

  cfg = (d=4, extra=4, rdm=10, pso=3, lso=true, lol=N,
         three_type=[1,1], SU2_symmetry=false, lattice="chain",
         Gram=false, correlation=false, J2=0,
         mosek_tol_pfeas=1e-8, mosek_tol_dfeas=1e-8, mosek_tol_relgap=1e-8)

H_supp/H_coe default to the supp/coe actually passed, so supp=[[1,4]],
coe=[3/4] and their sign in the GSB call are part of the effective config -
serialise them too.

Every result row also carries: protocol_sha256, harness_commit,
qmbcertify_commit, script_sha256, Project.toml_sha256, Manifest.toml_sha256,
julia_version, mosek_version, hostname, cpu_model, wall_s, solve_s,
peak_rss_gb, termination_status, primal_status, duality_gap, primal_residual.
A row missing any of these is invalid - discard it rather than interpret it.

## STEP 1 - gate

Run CONFIG A at N=10. Table 3 gives -0.4515446 in all three columns.
Pass criteria, in this order:
  (a) termination_status OPTIMAL and primal_status acceptable;
  (b) feasibility residuals within the declared tolerances;
  (c) round(opt, digits=7) == -0.4515446.
Table 3 prints only 7 decimals, so do NOT require exact float equality - a
difference beyond the 7th decimal that still rounds correctly is a PASS.
If the gate fails: STOP THE ENTIRE PLAN, write the discrepancy at the top of
LOG.md, do nothing else. Do not debug by guessing.

## STEP 2 - attribution

Run CONFIG A at N=14, and re-run the matched rdm=false arm (CONFIG B) in the
same session. Do NOT reuse the earlier r=5 number: it lacks the Step 0
provenance fields and cannot enter the ablation. Keep it in the log as
legacy_unverified_provenance, excluded from all conclusions. N=14 costs tens
of seconds; re-running is cheaper than arguing about it.

Define the marginal RDM improvement as

    delta_RDM = opt_A - opt_B

opt_A is rdm=10, opt_B is rdm=false, all else identical. These are LOWER
bounds: larger (less negative) is tighter, so a POSITIVE delta_RDM means RDM
positivity helped. Report the signed value, its magnitude, and opt_A's
deviation from -0.4473964.

## STEP 3 - one-factor ablation at N=14

CONFIG A with a single knob changed:
    C: pso=0        D: lso=false
Same sign convention. State explicitly in LOG.md that these are CONDITIONAL
marginals measured at CONFIG A, that they generally do NOT sum to the total
tightening, and that they must not be presented as a partition of it.

## STEP 4 - N-scaling under CONFIG A. The actual deliverable.

Run N = 18, 22, 26, 30, 34, 40, 46, 50 in ASCENDING order; every one is a
Table 3 row with a reference value.

Process model: one long-lived Julia driver for this whole sweep, warmed up on
a throwaway N=10 solve before any timing is recorded. Wrap each cell in
try/catch and flush its row to disk immediately. Record wall_s and solve_s
separately; only solve_s is comparable across cells.

Budgets, parameterised at the top of the script:
    MAX_WALL_S = 600
    MAX_RSS_GB = 18          # WSL has 24 GB; leave headroom for the OS
    MAX_PROC_SWAP_GB = 0.5
Monitor the Julia/MOSEK process group's own RSS and VmSwap, NOT total system
swap (which moves for unrelated reasons). Kill a cell on budget breach and
record WHICH budget it hit.
If a cell fails on memory, STOP the ascending sweep there and record the
resource frontier. Do not blindly continue to larger N.

Emit results.csv: all cfg fields, N, opt, table3_dmrg, table3_new,
dev_vs_dmrg, dev_vs_new, solve_s, wall_s, peak_rss_gb, limit_hit,
termination_status.

## STEP 5 - certification CAPABILITY AUDIT. Read-only. Run nothing.

Do NOT produce or claim an exact-rational certificate for CONFIG A.
The repo's certification example runs rdm=0, pso=0, lso=0, Gram=true, and
certify_qmb reads the main GramMat blocks. CONFIG A additionally carries
pso-generated PSD state-optimality blocks, rdm PSD blocks, and lso linear
constraints; and without Gram=true the Gram matrices are never saved.
From the source only, report:
  - which constraint families the rigorous rounding/projection path covers,
    and which it does not;
  - whether sGramMat and the RDM PSD blocks enter the Arblib eigenvalue bound;
  - what would have to be added to certify CONFIG A end to end.
Then stop. Extending the certifier is a separate methods task.

## OPERATING RULES

- Everything under tmux (session: overnight). Group the runs into two Julia
  processes: the N=14 ablations (Steps 2-3) in one, the N ladder (Step 4) in
  another. Within a group the process stays alive; between groups accept one
  startup cost and record it separately.
- On failure: record it, retry at most once, move to the next INDEPENDENT step.
- Do not scan three_type - it REPLACES a three-body geometry rather than
  adding one, so scanning it is a new-basis experiment, not reproduction.
  Do not set SU2_symmetry=true. Do not touch d. Those are tomorrow's questions.
- Write LOG.md as you go; one line whenever a result contradicts an expectation.
- Do not draw conclusions about the challenge targets. Produce the tables.
