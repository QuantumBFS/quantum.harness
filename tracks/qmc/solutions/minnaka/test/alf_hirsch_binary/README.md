# ALF 2.4 binary-Hirsch projector-QMC test

This directory implements and tests an exact two-valued Hirsch spin
Hubbard--Stratonovich field in the ALF 2.4
`Hubbard_Plain_Vanilla` Hamiltonian.  The pinned upstream source is
`ALF-QMC/ALF@ff5600df97877ef1d080432d0068e157ff520ecd`.

The runtime switch is:

```fortran
Hirsch_binary = .T.
```

It selects field type 1, `s = +/-1`, with
`lambda = acosh(exp(Dtau*U/2))`, `g_up = +lambda`, and
`g_down = -lambda`.  Omitting the parameter retains ALF's original
four-valued discrete field.

## Fixed calculation

- 4x4 square lattice, periodic in both directions;
- `t=1`, `U=4`, `N_up=N_down=8`;
- projector mode, `Theta=10`, `Beta=1`;
- symmetric Trotter decomposition, `Dtau=0.05`, 420 time slices;
- ALF's stock real noninteracting trial determinant with `Delta=0.01`;
- six independent single-rank, single-thread chains;
- 7 bins per chain and 2000 sweeps per bin.

ALF 2.4's Plain Vanilla module has no adiabatic-switching input or code path,
so binary mode is nonadiabatic by construction.  It explicitly rejects
`U <= 0`.

## Commands

Run from this directory.

Build the pinned checkout, apply the patch, and freeze the executable:

```bash
./scripts/build.sh
```

Run the analytical identity, real executable, invalid-input, and stock-path
regressions:

```bash
./scripts/test.sh
```

Run a short grouped six-rank smoke test:

```bash
./scripts/run_smoke.sh
```

Run the production calculation as six concurrent, physically pinned,
single-rank chains:

```bash
./scripts/run_six_chains.sh
```

Merge the 42 raw bins, omit the first bin of each chain, and write the result
artifacts and energy diagnostic plot:

```bash
/usr/bin/python3 ./scripts/analyze.py
```

The input-preparation scripts refuse to overwrite a directory containing raw
run output.  Move an existing `run/binary/smoke` or
`run/binary/production` directory aside before repeating that calculation.

## Why production uses six single-rank directories

Within one `mpirun -np 6` ALF group, ALF reduces the six walkers before
writing each observable bin.  Thus `NBin=7` produces seven six-walker-average
rows, not 42 inspectable rows.  The production runner instead launches six
independent `mpirun -np 1` jobs with distinct seeds and binds them to physical
CPUs 0, 2, 4, 6, 8, and 10.  This preserves all 42 chain-level bins while
keeping the same aggregate 84,000 sweeps.

## Layout

- `ALF/`: local pinned upstream checkout on `codex/hirsch-binary`;
- `patches/hirsch-binary.patch`: reproducible source patch;
- `tests/`: analytical and real-executable regressions;
- `scripts/`: build, test, input, run, and analysis entry points;
- `run/`: raw inputs, frozen executables, logs, and ALF output;
- `results/`: merged CSV, summaries, diagnostics, timing, and provenance.
