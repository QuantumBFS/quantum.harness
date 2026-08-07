# Channel-reflection round closeout

Date: 2026-07-29

This note closes the user-limited channel-reflection round. No new sampler,
large-size sentinel, Stage 5 calculation, or literature search is released.
The Windows control host was used only for orchestration, file inspection and
Git; it ran no numerical calculation.

## Final decision

- Independent review: complete; no unresolved Critical or Important finding.
- Clean remote verification: `73 passed` on both approved compute hosts.
- Mandatory `m=3` ED gate: **PASS**.
- The single pre-registered `m=8,beta=8` A/B: **STOP**.
- Stage 5 release: **not granted**.

The `m=8` arms are mutually consistent, but the reflection proposal fails its
frozen usefulness gates: one replica has reflection acceptance below `0.05`,
median worst tau increases by `8.77%`, and CPU seconds per effective sample
increase by `81.7%`. This is an algorithm stop, not a physics no-go.

## Immutable provenance

- Experiment ID: `stage4-channel-reflection-20260729-v1`.
- Numerical source revision:
  `db0d1144a3ae954b4276137e9d6094340cb76e5f`.
- Both retained remote source trees were clean and at that revision when
  audited.
- m=3 release artifact SHA-256:
  `572a663b7a2d17852c1a44995e535bb40cf98cf7d5c0e09cdaf559cd99fb2ec6`.
- The CPU recovery copy of the m=3 release artifact has the identical digest.

### Frozen run fingerprints

| Phase | Arm | Replica | Run fingerprint | State |
|---|---|---:|---|---|
| m3_ed | control | 0 | `8845183180dc82a385fad42cbb73d5c373c1e04370d4962a62f273d68a9eeea9` | complete |
| m3_ed | control | 1 | `708d10d0635d7477336eaf9ef5c6607fe993baa7fbd0187eb9e72491996c27ed` | complete |
| m3_ed | control | 2 | `028752f4a2cf7b81256e07e16752e6e875a4fb4746d7412d54aa771478e7955c` | complete |
| m3_ed | control | 3 | `0a332ae4365b9c632e422aa381759596b9d150d960f856ba0b1aa65bcc5c8bf4` | complete |
| m3_ed | channel_reflection | 0 | `23cc511f38d46821ac756f0b699221c170f836288c5e59a6c13ce11b41b0e6bb` | complete |
| m3_ed | channel_reflection | 1 | `ab4d73b18609a26df079e2e51ad8aecc4fdc6d9893676ae4e82fd9a793c1a6ae` | complete |
| m3_ed | channel_reflection | 2 | `b979244ce63332c9fa693ae1429893248ded4d4ec2fdcdf7f90c9a07bc6cffce` | complete |
| m3_ed | channel_reflection | 3 | `febec93a8c36f28a0ede479059f1f69731df0da512714861ffd683bc297e5d5a` | complete |
| stage4_ab | control | 0 | `6f5c444bde5f298c8e5ee91396441054c2d4895dbe8c160a362234f002ca811e` | complete |
| stage4_ab | control | 1 | `86cda57865644ae0cc1bd713b17db69bbb1fff5b2c3a36f371db1adaa9763ab1` | complete |
| stage4_ab | channel_reflection | 0 | `d2fd171d83723deb56804e7c7af7ff98cf62210c341037bf9e58e923bd03d8a5` | complete |
| stage4_ab | channel_reflection | 1 | `f1de5e7e97a081d4ce205e956b63a4adbdc61ffbfa372d50ba5c23c400d8387d` | complete |

## Retained remote state

The large/raw state remains off Git.

- WSL clean source:
  `/home/zibojin/code/nnv-phase-reflection-db0d114-bundle`.
- WSL m=3 data:
  `/home/zibojin/data/tensor-square-reflection-db0d114/m3_ed`.
  It contains eight complete chain summaries and eight checkpoints.
- CPU clean source:
  `/home/jzb/code/nnv-phase-reflection-db0d114`.
- CPU m=8 data:
  `/home/jzb/data/tensor-square-reflection-db0d114/stage4_ab`.
  It contains four complete chain summaries and four checkpoints.
- CPU fixed m=3 release copy:
  `/home/jzb/data/tensor-square-reflection-db0d114/m3_release.aggregate.json`.

At `2026-07-29T17:23:44Z`, a read-only process-table audit found zero
tensor-square/DQMC/Stage-4 runner processes on WSL and zero on the CPU
machine. No remote calculation was left running.

## Sole recovery entry

First pull the personal branch and verify its final closeout commit. Then,
before invoking either runner, confirm that both clean source trees remain at
the numerical source revision above, list the retained checkpoints, and
compare every `run_fingerprint` in `chains/*/replica_*.json` with the frozen
table above. Also verify the m=3 release artifact with:

```bash
sha256sum /home/zibojin/data/tensor-square-reflection-db0d114/m3_ed/aggregate.json
sha256sum /home/jzb/data/tensor-square-reflection-db0d114/m3_release.aggregate.json
```

Both outputs must equal the frozen m=3 digest. If every summary is present,
the round is complete and **must not be rerun**. Only if a summary is missing
and its matching fingerprint/checkpoint audit succeeds may the following
same-revision command recover that missing chain.

WSL m=3 recovery, from the WSL host:

```bash
cd /home/zibojin/code/nnv-phase-reflection-db0d114-bundle
test "$(git rev-parse HEAD)" = db0d1144a3ae954b4276137e9d6094340cb76e5f
test -z "$(git status --porcelain)"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$PWD/tracks/qmc/solutions/no-negative-vibes/tensor-square-phase-diagram/src"
/home/zibojin/miniforge3/envs/quantum_harness/bin/python \
  tracks/qmc/solutions/no-negative-vibes/tensor-square-phase-diagram/scripts/run_channel_reflection_validation.py \
  --phase m3_ed \
  --output-dir /home/zibojin/data/tensor-square-reflection-db0d114/m3_ed \
  --machine wsl --workers 8
```

CPU m=8 recovery, from the CPU host:

```bash
cd /home/jzb/code/nnv-phase-reflection-db0d114
test "$(git rev-parse HEAD)" = db0d1144a3ae954b4276137e9d6094340cb76e5f
test -z "$(git status --porcelain)"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$PWD/tracks/qmc/solutions/no-negative-vibes/tensor-square-phase-diagram/src"
/home/jzb/miniforge3/envs/quantum-harness/bin/python \
  tracks/qmc/solutions/no-negative-vibes/tensor-square-phase-diagram/scripts/run_channel_reflection_validation.py \
  --phase stage4_ab \
  --output-dir /home/jzb/data/tensor-square-reflection-db0d114/stage4_ab \
  --machine cpu --workers 4 \
  --m3-result /home/jzb/data/tensor-square-reflection-db0d114/m3_release.aggregate.json
```

The runner rejects a summary or checkpoint fingerprint mismatch. Never
delete a complete summary to force a retry, and never change the experiment
ID, seed, budget, threshold or source revision when recovering this round.
