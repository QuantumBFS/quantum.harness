# SCNet compute-node environment setup (Julia + Mosek for the Square-gap SDP)

Purpose: record how a working Julia + Mosek environment is laid out on an SCNet
compute/login node, so it can be replicated on a new node/district (e.g. the
Kunshan `scnet2` pool) without re-deriving it. Everything below was verified
live on 2026-07-29 across the `scnet` (xh5 district) and `scnet2` (Kunshan
district) hosts.

## 1. Directory layout (all under `$HOME`)

```text
~/julia-1.11.5/                     # relocatable official Julia 1.11.5 tarball, extracted
~/mosek/
  mosek/11.2/tools/platform/linux64x86/bin/mosek   # Mosek 11.2 binary
  mosek.lic                                        # portable license (see §4)
~/.julia/                           # package depot (JuMP, MosekTools, Mosek, ...). See §5.
~/quantum.harness/                  # the repo, on branch challenge/polyopt-sdp-gap
  julia-env/Project.toml            # the Julia project used by the scripts
  julia-env/Manifest.toml
  .external/SpectralGap/            # local path-dep (gitignored; needed only by the
                                    #   legacy TFIM/kagome certifiers, NOT by SquareGapConic)
```

`~/julia-1.11.5` and `~/mosek` are plain `tar czf` archives of the extracted
trees from a working node; both are relocatable across same-arch (x86_64 linux)
hosts. Julia and Mosek are NOT installed via a package manager or `module`.

## 2. Required environment variables

```bash
export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
# CRITICAL — see §3:
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:${LD_LIBRARY_PATH:-}"
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
```

`solve_square_primal_mof.jl` reads `MOSEKBINDIR` indirectly through `Mosek_jll`,
and the sbatch scripts already export the block above, so jobs submitted via
`sbatch` pick it up automatically.

## 3. The libstdc++ gotcha (most important)

On several SCNet nodes the **system** `/lib64/libstdc++.so.6` is too old for
Mosek 11.2: Mosek's bundled `libtbb.so.12` requires `CXXABI_1.3.8` and
`GLIBCXX_3.4.21`, which the system libstdc++ lacks, so `mosek` fails at startup
with:

```text
mosek: /lib64/libstdc++.so.6: version `CXXABI_1.3.8' not found
       (required by .../bin/libtbb.so.12)
```

The fix: **Julia 1.11.5 ships a new-enough `libstdc++.so.6` inside its own
`lib/julia/` directory**, and putting that directory first on
`LD_LIBRARY_PATH` satisfies Mosek. Verify it has the symbols:

```bash
strings ~/julia-1.11.5/lib/julia/libstdc++.so.6 | grep -E 'CXXABI_1.3.8|GLIBCXX_3.4.21'
```

So `LD_LIBRARY_PATH=$HOME/julia-1.11.5/lib/julia:...` is mandatory on any node
whose system libstdc++ is older than GCC 5.1. Do NOT rely on `devtoolset` — on
the Kunshan nodes `devtoolset-7` has the `gcc` binary but its runtime
`libstdc++.so.6` is absent, so it does not fix the loader.

## 4. Mosek license

The license is a **portable `mosek.lic` file** at `~/mosek/mosek.lic` (~1 KB).
It is **not node-locked**: the same file has been used on a laptop and on the
xh5 login/compute nodes, and it validates on Kunshan too. No `MOSEKLM` license
server is used. Just make sure `~/mosek/mosek.lic` is present; Mosek finds it
by default relative to `MOSEKBINDIR`/`~/mosek`.

Quick license + binary check (no Julia needed):

```bash
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:${LD_LIBRARY_PATH:-}"
$MOSEKBINDIR/mosek ~/mosek/mosek/11.2/tools/examples/data/lo1.mps
# expect: "Problem status : PRIMAL_AND_DUAL_FEASIBLE" / "OPTIMAL"
```

## 5. The Julia package depot (the part that hangs if you try to build it fresh)

`Pkg.instantiate()` on these nodes **hangs** partway through precompilation
(this was hit when configuring the original xh5 node too). The working approach
is to **copy the already-instantiated `~/.julia` depot from a working node**
rather than instantiate from the registry. Two caveats:

- Copying the *entire* `~/.julia` is large (~1.1 GB) and drags in packages only
  the legacy TFIM/kagome path needs (`SpectralGap`, `QMBCertify`, `NCTSSoS`,
  `Clarabel`). For a node that will only run the **SquareGapConic** path, a
  smaller transfer is enough: the runtime needs just `JuMP`, `Mosek`,
  `MosekTools` (+ transitive deps + the `Mosek_jll` artifact, which carries the
  Mosek shared library) and the local `src/` modules. Everything else
  (`Dates`, `SHA`, `TOML`, `LinearAlgebra`) is Julia stdlib.
- If a *minimal* env is preferred on the new node, write a fresh
  `julia-env/Project.toml` listing only `JuMP`, `Mosek`, `MosekTools` (drop the
  path-deps `SpectralGap`/`QMBCertify`/`NCTSSoS` from both `Project.toml` and
  `Manifest.toml`) and copy the corresponding package dirs out of a working
  `~/.julia/packages` + `~/.julia/compiled` + the `Mosek_jll` artifact.

The depot is keyed on Julia version (1.11.5) and package source content, not on
`$HOME` path or the Julia binary location, so a copied depot works as-is; at
worst Julia recompiles a stale cache on first use (slow first run, still works).

## 6. Network constraints (why direct install is painful)

From the Kunshan login node (and similarly on xh5): `github.com`,
`julialang-s3.julialang.org`, and `pkg.julialang.org` are **blocked**. The
Tsinghua TUNA mirror (`mirrors.tuna.tsinghua.edu.cn`) answers HTTPS but its
Julia binary tarball path 302-redirects to a 404/403, and `raw.githubusercontent.com`
is reachable but GitHub release downloads are not. Conclusion: do not plan on
downloading Julia/Mosek/packages from the public internet on-node; copy them
from a working node instead (see §7).

## 7. Copying the stack between districts

The two districts are mutually isolated at the network layer, but a one-way ssh
alias can be configured. On the Kunshan node we set:

```text
# ~/.ssh/config on scnet2 (Kunshan)
Host scnet
    HostName xh5.hpccube.com
    Port 65061            # NOTE: not the default 22
    User iint_sjds
```

Then the new node can pull the stack directly from the working node
(cluster-to-cluster, fast), e.g.:

```bash
# from scnet2, pull each piece from scnet1 (already tarred in $HOME, not /tmp):
scp scnet:julia-relay.tar.gz scnet:mosek-relay.tar.gz scnet:qh-repo-relay.tar.gz ~/
tar xzf julia-relay.tar.gz   # -> ~/julia-1.11.5
tar xzf mosek-relay.tar.gz   # -> ~/mosek  (includes mosek.lic)
tar xzf qh-repo-relay.tar.gz # -> ~/quantum.harness
```

Keep the tarballs in `$HOME`, not `/tmp` — `/tmp` is periodically purged on
these servers. (The `.julia` depot is the bulky one; see §5 for minimizing it.)

## 8. Running a job on the new node

The sbatch `square_conic_solve.sbatch` is district-agnostic except for the
`#SBATCH --partition=` line. Override the partition at submission time and set
the district's memory limit accordingly:

```bash
# Kunshan CPU partition (kshcnormal, 32-core / ~123 GB nodes):
CONIC_BASIS=bare_weight_one CONIC_G=1//2 CONIC_GAMMA=0//1 \
CONIC_POS_DIM=28 CONIC_GAP_DIM=4 CONIC_LABEL=rung-a-validate \
sbatch --partition=kshcnormal --cpus-per-task=4 \
  tracks/polyopt/solutions/sdp-gap-seekers/scripts/square_conic_solve.sbatch
```

Memory note: the Kunshan `kshcnormal` nodes are ~123 GB. The 352/4 "Rung B"
relaxation needs >250 GB and a >30-min first interior-point iteration, so it is
**not** runnable on Kunshan — only the small (`bare_weight_one`, 28/4) runs and
future small formulations fit there. Rung B and larger must stay on the xh5
501 GB nodes.

## 9. End-to-end verification on the new node

1. `~/julia-1.11.5/bin/julia --version` → `1.11.5`.
2. Mosek license/binary (§4) → `PRIMAL_AND_DUAL_FEASIBLE`.
3. Full pipeline (after the depot is in place): submit the Rung A
   `bare_weight_one` smoke above; expect `classification = "feasible_candidate"`
   in ~2 s, matching the xh5 result (`evidence/square-conic-rung-a-validate-22994039/`).
