from __future__ import annotations

import numpy as np

from .exact import ThermoPoint
from .model import tfim_dense
from .pepo import FinitePEPO
from .trotter import second_order_gates


def evolve_exact_contraction(
    lx: int,
    ly: int,
    *,
    j: float,
    h: float,
    beta: float,
    delta_beta: float,
    max_bond: int,
) -> ThermoPoint:
    steps = round(beta / delta_beta)
    if not np.isclose(steps * delta_beta, beta):
        raise ValueError("beta must be an integer multiple of delta_beta")
    pepo = FinitePEPO.identity(lx, ly)
    log_scale = 0.0
    gates = second_order_gates(
        lx,
        ly,
        j=j,
        h=h,
        delta_beta=delta_beta,
    )
    for _ in range(steps):
        for gate in gates:
            pepo.apply_gate(gate, max_bond=max_bond)
        log_scale += pepo.renormalize_tensors()
    rho_scaled = pepo.to_dense()
    hmat = tfim_dense(lx, ly, j=j, h=h)
    z_scaled = float(np.trace(rho_scaled).real)
    if z_scaled <= 0:
        raise FloatingPointError("non-positive partition function")
    mean_e = float(np.trace(hmat @ rho_scaled).real / z_scaled)
    mean_e2 = float(np.trace(hmat @ hmat @ rho_scaled).real / z_scaled)
    nsites = lx * ly
    log_z = log_scale + np.log(z_scaled)
    return ThermoPoint(
        beta=beta,
        log_z=log_z,
        f=-log_z / (beta * nsites),
        u=mean_e / nsites,
        c=beta * beta * (mean_e2 - mean_e * mean_e) / nsites,
    )
