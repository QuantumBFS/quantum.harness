# Huang worm equation ledger

Route B follows Huang, Liu, Jiang, and Deng, *Worm-algorithm-type Simulation
of Quantum Transverse-Field Ising Model*, Phys. Rev. B 102, 094101 (2020),
[arXiv:2005.10066](https://arxiv.org/abs/2005.10066). Equation numbers below
refer to that paper.

## Basis and weight

The Challenge Hamiltonian is rotated globally by 90 degrees in spin space:

```text
original: H = -J sum_<ij> sigma_z(i) sigma_z(j) - h sum_i sigma_x(i)
Route B:  H = -J sum_<ij> sigma_x(i) sigma_x(j) - h sum_i sigma_z(i)
```

This is Eq. (2). Equation (3) decomposes each bond operator into hopping and
pairing terms with identical matrix element `J`. Equation (5) expands the
partition function in continuous imaginary time, and Eq. (6) gives its
integrand:

```text
F(J,J,h) = J^(N_h) J^(N_p)
           * exp(-integral U(tau) d tau)
U(tau) = -h sum_i s_i(tau)
log F = (N_h + N_p) log J + h integral sum_i s_i(tau) d tau.
```

`log_weight` implements the last line. `log_ratio` implements the local
difference

```text
log(F_new/F_old) = delta_N_kink log J + h delta_spin_time.
```

Both functions require positive `J` and finite inputs. Route B evaluates all
acceptance ratios in this log domain. A nonfinite log ratio is treated as an
invalid proposal rather than silently accepted or rejected.

Equation (7) supplies the closed-sector measure `W_Z`. Equations (8) and (9)
define the two-defect Green-function sector and `W_G`, including its
`d tau_I d tau_M / omega_G` measure. Route B fixes `omega_G=beta*N` as
recommended immediately after Eq. (11).

## Reversible update measures

Equation (10) is the create/annihilate detailed-balance identity. Equation
(11) yields

```text
P_create = min(1, A_a tau_a (beta N / omega_G) F_new/F_old)
P_annih  = min(1, (1/A_a) (1/tau_a) (omega_G/(beta N)) F_new/F_old).
```

The following displayed equation, Eq. (12), gives
`P_move=min(1,F_new/F_old)`. Equation (13) is the insert/delete
detailed-balance identity, and Eq. (14) yields

```text
P_insert = min(1, tau_c/(n_k+1) F_new/F_old)
P_delete = min(1, n_k/tau_c F_new/F_old).
```

The mutation kernel will implement these ratios through named pure functions;
this ledger does not authorize embedding proposal densities or Jacobians as
unexplained constants. The frozen family probabilities are
`A_a=A_b=A_c=1/4`, so `A_a+A_b+2A_c=1`.

## Extended-ensemble normalization

Section IV C of Huang et al. identifies the worm-return time with the relative
weight of the Green and partition-function sectors. With `omega_G=beta*N`,

```text
T_w = W_G/W_Z
    = <(integral_0^beta d tau sum_i sigma_x(i,tau))^2> / (beta*N)
    = chi_xx.
```

Route B estimates this ratio as `G_visits/Z_visits`. A fixed-parameter Markov
chain does not determine the absolute partition function `log Z`; the ED gate
therefore compares `T_w=chi_xx`, rather than relabelling the sector ratio.
