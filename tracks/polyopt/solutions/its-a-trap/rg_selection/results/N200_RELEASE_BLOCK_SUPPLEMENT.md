# N200 RELEASE/BLOCK SUPPLEMENT (terminal ruling, 2026-07-30 02:40 +08)

## RULING: BLOCKED (mechanical, timing law amendment 4)

The resource probe did not reach a terminal state by the 02:30 hard
deadline (n200probe64 = 23013383: RUNNING 2h57 at check, still in the
construction stage, no n200_probe.json; the 128c probe 23009659 never
started — AssocGrpCpuLimit). Per the pre-authorized branch: probe
incomplete at 02:30 → BLOCK. No blind release. Pair 23009660 remains
HELD; the frozen cebb8da snapshot on the cluster is untouched.

## Gate table at ruling

Machine-readable: n200_release_gate.csv (this directory). Summary:
all correctness gates (G4, G4b, vcheck incl. strengthened V3 with
newwords=1 and a red mutation) PASS; snapshot equivalence PASS
(validation-only local changes; production hashes identical); BOTH
resource gates NOT EVALUABLE at the deadline — which is precisely the
case the no-blind-release rule exists for.

## What the probe's non-completion itself measures

The V_{S*}(200) build (r=24 mandatory basis + S* closures, 64c) exceeds
2h57 wall in construction alone. Combined with v200hi (CONFIG A
construction > 11.7h) and e49p0v2 (r=50 solve intractable at 11.7h on a
full node), the N=200 deployment cost sits at or beyond the overnight
resource frontier for every formulation attempted this week. This is a
measured frontier statement, not a method verdict; the small-N method
chapter stands on its own gates.

## Standing state

- 23013383 left RUNNING (6h wall cap self-terminates; its state file /
  eventual JSON will be harvested Thursday as a frontier datum).
- 23009659 will be cancelled Thursday morning (queue hygiene).
- 23009660 stays HELD pending an explicit arbiter decision Thursday
  (the whitelist's kill-switch branch: the small-N study + holdout is
  the method chapter; a daytime run remains possible if the arbiter
  re-authorizes with fresh wall budget — NOT tonight's decision).
