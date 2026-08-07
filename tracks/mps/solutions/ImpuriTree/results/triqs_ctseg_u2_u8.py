from h5 import HDFArchive
from triqs.gfs import Gf, MeshImFreq, SemiCircular, make_gf_from_fourier
from triqs.operators import n
from triqs_ctseg import Solver


beta, half_bandwidth, n_tau = 16.0, 2.0, 1601
mesh = MeshImFreq(beta=beta, statistic="Fermion", n_iw=800)
delta_iw = Gf(mesh=mesh, target_shape=[1, 1])
delta_iw << (half_bandwidth / 2) ** 2 * SemiCircular(half_bandwidth)
delta_tau = make_gf_from_fourier(delta_iw, n_tau)
n_up, n_down = n("up", 0), n("down", 0)

for interaction, seed in ((2.0, 34788), (8.0, 834788)):
    solver = Solver(
        beta=beta,
        gf_struct=[("up", 1), ("down", 1)],
        n_tau=n_tau,
    )
    solver.Delta_tau["up"] << delta_tau
    solver.Delta_tau["down"] << delta_tau
    solver.solve(
        h_loc0=-interaction / 2 * (n_up + n_down),
        h_int=interaction * n_up * n_down,
        n_warmup_cycles=20_000,
        n_cycles=200_000,
        random_seed=seed,
    )
    with HDFArchive(f"ctseg_u{int(interaction)}.h5", "w") as archive:
        archive["G_tau"] = solver.results.G_tau
