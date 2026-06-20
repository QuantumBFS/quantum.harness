# SmoQyDQMC.jl — API + Examples Reference

Finite-temperature **determinant quantum Monte Carlo (DQMC)** in Julia for tight-binding
**Hubbard** and **electron–phonon** models. Auxiliary-field QMC in the grand canonical
ensemble: the partition function `Z = Tr[ exp(−βĤ) ]` is Trotter-decomposed onto an
imaginary-time grid `τ = Δτ·l` (l = 1…Lτ, Δτ = β/Lτ), Hubbard interactions are decoupled
by a Hubbard–Stratonovich (HS) transformation, and phonon fields are integrated out into a
fermion determinant `det Mσ`. Sampling: local HS-field updates, reflection/swap updates, and
**exact-Fourier-accelerated hybrid Monte Carlo (EFA-HMC)** for phonons (handles optical,
acoustic, anharmonic, nonlinear couplings). Scales as O(β·N³).

**Scope.** Arbitrary lattices/bases in 0–3D; intra/inter-orbital + extended Hubbard;
real/complex hopping (twisted boundary conditions); Holstein/Fröhlich and SSH (optical, bond,
acoustic) e-ph couplings; multiple phonon branches; anharmonic potentials up to 4th order;
dynamical chemical-potential tuning to a target density; spatial disorder in any parameter.
Scripting interface (à la ITensors.jl), not config files.

## Source links

- Docs (stable): https://smoqysuite.github.io/SmoQyDQMC.jl/stable/
- API index: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/api/
- Supported Hamiltonians: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/hamiltonian/
- Simulation output: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/simulation_output/
- Hubbard square tutorial: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/tutorials/hubbard_square/
- Holstein honeycomb tutorial: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/tutorials/holstein_honeycomb/
- Density tuning tutorial: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/tutorials/hubbard_square_density_tuning/
- SSH / Holstein-Hubbard examples: https://smoqysuite.github.io/SmoQyDQMC.jl/stable/examples/ (ossh_chain, bssh_chain, ossh_square, bssh_square, ossh_honeycomb, hubbard_ossh_square, hubbard_holstein_square, ossh_hubbard_honeycomb)
- GitHub: https://github.com/SmoQySuite/SmoQyDQMC.jl
- Lower-level packages: https://github.com/SmoQySuite/JDQMCFramework.jl , https://github.com/SmoQySuite/JDQMCMeasurements.jl
- Paper: SciPost Phys. Codebases 29 (2023), arXiv:2311.09395, DOI 10.21468/SciPostPhysCodeb.29

Install: `julia> ]` then `pkg> add SmoQyDQMC`.

Conventional imports used throughout the docs:

```julia
using SmoQyDQMC
import SmoQyDQMC.LatticeUtilities as lu      # UnitCell, Lattice, Bond, nsites
import SmoQyDQMC.JDQMCFramework as dqmcf      # FermionGreensCalculator, calculate_equaltime_greens!
import SmoQyDQMC.MuTuner as mt                # density tuning (only when used)
using Random, Printf
```

---

# Key API

Naming pattern: a **`*Model`** type defines the Hamiltonian abstractly; the paired
**`*Parameters`** type instantiates it on a finite lattice (sampling disorder via `rng`).
`measure_*` functions are the per-quantity measurement kernels (usually invoked internally
by the measurement container, not by hand).

## 1. Lattice & model geometry

```julia
# from LatticeUtilities (aliased lu)
lu.UnitCell(; lattice_vecs::Vector{Vector}, basis_vecs::Vector{Vector})
lu.Lattice(; L::Vector{Int}, periodic::Vector{Bool})
lu.Bond(; orbitals::Tuple{Int,Int}, displacement::Vector{Int})   # (orb_i, orb_j), unit-cell offset
lu.nsites(unit_cell, lattice)                                     # total orbitals N

ModelGeometry(unit_cell::UnitCell, lattice::Lattice)             # encapsulates geometry + bond table
add_bond!(model_geometry, bond::Bond) -> bond_id::Int            # register a bond, returns its ID
get_bond_id(model_geometry, bond::Bond) -> Int
```

## 2. Tight-binding model (kinetic energy + chemical potential)

```julia
TightBindingModel(;
    model_geometry::ModelGeometry,
    μ,                       # chemical potential
    ϵ_mean::Vector,          # mean on-site energy per orbital in unit cell
    ϵ_std::Vector = zeros,   # disorder std of on-site energy
    t_bonds::Vector{Bond} = [],   # bonds carrying hopping
    t_mean::Vector  = [],         # mean hopping amplitude per t_bond (real or complex)
    t_std::Vector   = zeros,      # disorder std of hopping
    η = nothing)             # twist / Peierls phase support
TightBindingParameters(; tight_binding_model, model_geometry, rng::AbstractRNG)
```

Hopping-energy measurement kernels: `measure_onsite_energy`, `measure_hopping_energy`,
`measure_bare_hopping_energy`, `measure_hopping_amplitude`, `measure_hopping_inversion`.

## 3. Hubbard & extended Hubbard interactions

```julia
HubbardModel(;
    ph_sym_form::Bool,             # true → particle-hole-symmetric U(n↑−½)(n↓−½) form (use at half filling)
    U_orbital::Vector{Int},        # which orbitals carry U
    U_mean::Vector,                # mean U per listed orbital (U<0 for attractive)
    U_std::Vector = zero)          # disorder std of U
HubbardParameters(; hubbard_model, model_geometry, rng)
measure_hubbard_energy(hubbard_parameters, Gup, Gdn, hubbard_id)

ExtendedHubbardModel(;
    model_geometry, ph_sym_form::Bool,
    V_bond::Vector{Bond}, V_mean::Vector, V_std::Vector = zero)   # V on (i,ν)-(j,γ); V(same site)=0
ExtendedHubbardParameters(; extended_hubbard_model, model_geometry, rng)
measure_ext_hub_energy(ext_hub_params, Gup, Gdn, ext_hub_id)
```

### Hubbard–Stratonovich (HS) transformations

Decouple the (extended) Hubbard term; the resulting HS fields are what local/reflection/swap
updates sample. Spin-channel = `AbstractAsymHST` (two-species path integral); density-channel =
`AbstractSymHST` (single shared path integral). Hirsch = discrete fields s=±1; Gauss-Hermite =
discrete s=±1,±2 (better at large U). All constructors take `; β, Δτ, hubbard_parameters, rng`.

| Type | Channel | Fields |
|---|---|---|
| `HubbardSpinHirschHST` | spin (asym) | ±1 — default for repulsive U |
| `HubbardSpinGaussHermiteHST` | spin (asym) | ±1,±2 |
| `HubbardDensityHirschHST` | density (sym) | ±1 — sign-problem-free for attractive U / PHS |
| `HubbardDensityGaussHermiteHST` | density (sym) | ±1,±2 |
| `ExtHubSpinHirschHST` | spin (asym) | extended Hubbard |
| `ExtHubDensityGaussHermiteHST` | density (sym) | extended Hubbard |

```julia
HubbardSpinHirschHST(; β, Δτ, hubbard_parameters, rng)   # representative constructor
init_renormalized_hubbard_parameters(; hubbard_parameters, hst_parameters, model_geometry)
```

## 4. Electron–phonon model

```julia
ElectronPhononModel(;
    model_geometry,
    tight_binding_model = nothing,        # or spin-resolved: tight_binding_model_up / _dn
    tight_binding_model_up = nothing, tight_binding_model_dn = nothing)

PhononMode(;
    basis_vec::Vector,    # which basis site the mode sits on
    Ω_mean, Ω_std = 0.,   # phonon frequency Ω₀ (Ω_mean = 0 → acoustic mode)
    M = 1.,               # mass
    Ω4_mean = 0., Ω4_std = 0.)   # quartic anharmonicity Ωₐ
add_phonon_mode!(; electron_phonon_model, phonon_mode) -> phonon_id::Int

# Holstein / Fröhlich: couples displacement to local density
HolsteinCoupling(;
    model_geometry, phonon_id::Int, orbital_id::Int,
    displacement::Vector{Int},                # offset from phonon site to coupled orbital
    α_mean, α_std = 0.,                        # linear coupling κ₁
    α2_mean = 0., α3_mean = 0., α4_mean = 0.,  # nonlinear orders (+ *_std)
    ph_sym_form::Bool = true)                  # density (n−½) vs n
add_holstein_coupling!(; model_geometry, electron_phonon_model,
    holstein_coupling = nothing,              # or holstein_coupling_up / _dn for spin-dependent
    holstein_coupling_up = nothing, holstein_coupling_dn = nothing) -> id::Int

# SSH: phonon displacement modulates a hopping (bond)
SSHCoupling(;
    model_geometry, tight_binding_model,
    phonon_ids::NTuple{2,Int},                # the two phonon modes on the bond's endpoints
    bond::Bond,
    α_mean, α_std = 0., α2_mean = 0., α3_mean = 0., α4_mean = 0.)
add_ssh_coupling!(; electron_phonon_model, tight_binding_model,
    ssh_coupling = nothing, ssh_coupling_up = nothing, ssh_coupling_dn = nothing) -> id::Int

# Dispersion: harmonic/anharmonic coupling between two displaced phonon modes (→ acoustic branches)
PhononDispersion(;
    model_geometry, phonon_ids::NTuple{2,Int}, displacement::Vector{Int},
    Ω_mean, Ω_std = 0., Ω4_mean = 0., Ω4_std = 0.,
    ζ::Int = 1)   # ξ = ±1: sign of dispersive coupling (acoustic vs optical character)
add_phonon_dispersion!(; electron_phonon_model, phonon_dispersion, model_geometry) -> id::Int

# instantiate on the finite lattice (allocates phonon field configuration)
ElectronPhononParameters(;
    β, Δτ, model_geometry, electron_phonon_model, rng,
    tight_binding_parameters = nothing,       # or _up / _dn
    tight_binding_parameters_up = nothing, tight_binding_parameters_dn = nothing)
```

Finite-lattice sub-parameter types: `PhononParameters`, `HolsteinParameters`, `SSHParameters`,
`DispersionParameters`. E-ph measurement kernels: `measure_phonon_kinetic_energy`,
`measure_phonon_potential_energy`, `measure_phonon_position_moment`, `measure_holstein_energy`,
`measure_ssh_energy`, `measure_dispersion_energy`.

**Recipes.** Single-band Holstein → one QHO mode/cell, only `HolsteinCoupling`. Optical SSH in
D dims → D modes/cell, only `SSHCoupling`. Bond SSH → pair a finite-mass and an infinite-mass
mode on a bond. Acoustic SSH → zero-frequency modes (`Ω_mean=0`) tied together by
`PhononDispersion`. Branches can be mixed freely.

## 5. Simulation parameters & bookkeeping

These are plain script-level numbers, not a config object (the tutorials thread them as
function keyword arguments):

| Symbol | Meaning |
|---|---|
| `β` | inverse temperature (β = 1/T) |
| `Δτ` | imaginary-time step (Lτ = β/Δτ); Trotter error O(Δτ²) |
| `N_therm` | thermalization sweeps (no measurements) |
| `N_measurements` | number of measurements after thermalization |
| `N_updates` | field updates between measurements |
| `N_bins` | measurement bins; `bin_size = N_measurements ÷ N_bins` |
| `n_stab` | numerical-stabilization interval (recompute G from scratch every n_stab time slices) |
| `δG_max` | max tolerated Green's-function error before stabilization frequency is bumped |
| `symmetric` | symmetric `B = exp(−Δτ/2·K) exp(−Δτ·V) exp(−Δτ/2·K)` (Eq.16) vs `exp(−Δτ·V) exp(−Δτ·K)` (Eq.17) |
| `checkerboard` | checkerboard approximation of `exp(−Δτ·K)` |

```julia
SimulationInfo(; datafolder_prefix::String, filepath::String=".",
               write_bins_concurrent::Bool=true, sID::Int=0, pID::Int=0)
initialize_datafolder(sim_info)                 # or initialize_datafolder(comm::MPI.Comm, sim_info)
model_summary(; simulation_info, β, Δτ, model_geometry, tight_binding_model, interactions)
   # interactions is a Tuple, e.g. (hubbard_model,) or (electron_phonon_model,)
save_simulation_info(simulation_info, metadata::Dict)
```

## 6. DQMC core: path integral, propagators, Green's-function calculator

```julia
FermionPathIntegral(; tight_binding_parameters, β, Δτ,
                    forced_complex_potential::Bool=false, forced_complex_kinetic::Bool=false)
initialize!(fpi_up, fpi_dn, hubbard_parameters)          # add Hubbard contribution (two-species)
initialize!(fpi_up, fpi_dn, hst_parameters)              # add current HS-field configuration
initialize!(fpi, electron_phonon_parameters)             # e-ph (single shared path integral)

B = initialize_propagators(fpi; symmetric, checkerboard) # Vector of B_l propagators
calculate_propagators!(B, fpi; calculate_exp_V, calculate_exp_K)
calculate_propagator!(B_l, fpi, l; calculate_exp_V, calculate_exp_K)

# from JDQMCFramework (aliased dqmcf):
fgc = dqmcf.FermionGreensCalculator(B, β, Δτ, n_stab)
fgc_alt = dqmcf.FermionGreensCalculator(fgc)             # copy, used by reflection/swap/HMC
logdetG, sgndetG = dqmcf.calculate_equaltime_greens!(G, fgc)

update_stabilization_frequency!(G, logdetG, sgndetG; fermion_greens_calculator, B,
                                δG, δθ, δG_max, δG_min=0.0, active=true, info=nothing)
   # (two-species variant takes Gup/Gdn and both calculators)
```

## 7. Updates

Each update returns updated `logdetG, sgndet G` (and `δG, δθ` for local/HMC). Two-species
(asymmetric HS, e-ph with spin-resolved hopping) variants take `Gup/Gdn` and both calculators;
single-species (symmetric HS) variants take `G`.

```julia
# Local sweep over every HS field on every (orbital, time slice):
local_updates!(Gup, logdetGup, sgndetGup, Gdn, logdetGdn, sgndetGdn, hst_parameters;
    fermion_path_integral_up, fermion_path_integral_dn,
    fermion_greens_calculator_up, fermion_greens_calculator_dn,
    Bup, Bdn, δG, δθ, rng, δG_max=1e-6, update_stabilization_frequency=true)
   # returns (acceptance_rate, logdetGup, sgndetGup, logdetGdn, sgndetGdn, δG, δθ)

# Reflection: flip an HS field (or phonon field) at a random site across all time slices:
reflection_update!(Gup, …, Gdn, …, hst_parameters_or_electron_phonon_parameters;
    …, fermion_greens_calculator_up_alt, fermion_greens_calculator_dn_alt, Bup, Bdn, rng)
   # returns (accepted, logdetG…, sgndet G…)

# Swap two random sites' fields:
swap_update!(…)                          # same call shape as reflection_update!

# Radial update (phonons): rescale displacement magnitude at a random mode:
radial_update!(…)

# EFA-HMC for phonon fields:
hmc_updater = EFAHMCUpdater(; electron_phonon_parameters, G, Nt::Int,
                            Δt = π/(2*Nt), reg = 0.0, δ = 0.05)
   # Nt = #leapfrog steps; Δt = step size (default tuned to the QHO period);
   # δ jitters Δt by (1+δ(2u−1)); reg regularizes acoustic/soft modes.
hmc_update!(G, logdetG, sgndetG, electron_phonon_parameters, hmc_updater;
    fermion_path_integral, fermion_greens_calculator, fermion_greens_calculator_alt, B,
    δG, δθ, rng, update_stabilization_frequency=false,
    δG_max=1e-5, δG_reject=1e-2, recenter!=identity,
    Nt=hmc_updater.Nt, Δt=hmc_updater.Δt, δ=hmc_updater.δ)
   # returns (accepted, logdetG, sgndetG, δG, δθ)
   # two-species variant takes Gup/Gdn + both fpi/calculators (+ _alt) and Bup/Bdn.
```

## 8. Measurements

```julia
mc = initialize_measurement_container(model_geometry, β, Δτ)
initialize_measurements!(mc, tight_binding_model)     # global + local energy measurements
initialize_measurements!(mc, hubbard_model)
initialize_measurements!(mc, electron_phonon_model)

initialize_correlation_measurements!(; measurement_container, model_geometry,
    correlation::String,            # one of CORRELATION_FUNCTIONS (table below)
    pairs::Vector{Tuple{Int,Int}},  # orbital pairs or bond-id pairs to correlate
    time_displaced::Bool = false,   # measure C(τ) vs only equal-time
    integrated::Bool = false)       # also report ∫dτ C(τ) (susceptibility)

initialize_composite_correlation_measurement!(; measurement_container, model_geometry,
    name::String, correlation::String,
    ids = …,                        # or id_pairs for two-point composites
    coefficients::Vector,           # linear combo, e.g. d-wave [0.5,0.5,-0.5,-0.5]
    displacement_vecs = …,          # optional, for cdw-style composites
    time_displaced = false, integrated = false)

# Called once per measurement; updates Green's functions internally and accumulates:
make_measurements!(mc,
    logdetGup, sgndetGup, Gup, Gup_ττ, Gup_τ0, Gup_0τ,
    logdetGdn, sgndetGdn, Gdn, Gdn_ττ, Gdn_τ0, Gdn_0τ;
    fermion_path_integral_up, fermion_path_integral_dn,
    fermion_greens_calculator_up, fermion_greens_calculator_dn,
    Bup, Bdn, δG_max, δG, δθ,
    model_geometry, tight_binding_parameters,
    coupling_parameters)            # Tuple, e.g. (hubbard_parameters, hst_parameters) or (electron_phonon_parameters,)
   # single-species form: make_measurements!(mc, logdetG, sgndetG, G, G_ττ, G_τ0, G_0τ; …)
   # returns (logdetG…, sgndet G…, δG, δθ)

write_measurements!(; measurement_container, simulation_info, model_geometry,
    measurement::Int, bin_size::Int, Δτ)   # flushes a bin average to disk every bin_size measurements
merge_bins(simulation_info)                # consolidate per-bin files into one HDF5
rm_bins(simulation_info)
```

Supported `correlation` strings (`CORRELATION_FUNCTIONS`):
`greens`, `greens_up`, `greens_dn`, `density`, `spin_z`, `spin_x`, `pair`, `bond`, `current`,
`phonon_greens`.

Global measurements (`GLOBAL_MEASUREMENTS`): `sgn`, `sgndetGup`, `sgndetGdn`, `density`,
`density_up`, `density_dn`, `double_occ`, `Nsqrd`, `chemical_potential`, `compressibility`.

Local measurements (`LOCAL_MEASUREMENTS`): per-orbital `density`, `double_occ`,
`onsite_energy`, `hubbard_energy`; per-bond `bare_hopping_energy`, `hopping_energy`,
`hopping_amplitude`, `hopping_inversion`; per-phonon `phonon_kin_energy`, `phonon_pot_energy`,
`X`, `X2`, `X3`, `X4`, `dispersion_energy`; e-ph `holstein_energy`, `ssh_energy`.

## 9. Processing & reading results

```julia
process_measurements(; datafolder = simulation_info.datafolder, n_bins::Int,
    export_to_csv::Bool = true, scientific_notation = false, decimals = 7, delimiter = " ")
   # binned-statistics analysis → mean + error bars; writes *_stats.csv / stats.h5.
   # Complex error: ΔC = √(ΔC_Re² + ΔC_Im²).

# Correlation ratios (order-parameter diagnostics) at an ordering wavevector q:
Rafm, ΔRafm = compute_correlation_ratio(; datafolder, correlation, type,    # type "equal-time"/"integrated"
    id_pairs, id_pair_coefficients, q_point::Tuple, q_neighbors::Vector{Tuple})
Rcdw, ΔRcdw = compute_composite_correlation_ratio(; datafolder, name, type, q_point, q_neighbors)
compute_function_of_correlations(…)   # propagate errors through a function of correlations

# CSV/HDF5 exporters:
export_global_stats_to_csv, export_global_bins_to_csv, export_global_bins_to_h5,
export_local_stats_to_csv,  export_local_bins_to_csv,  export_local_bins_to_h5,
export_correlation_stats_to_csv, export_correlation_bins_to_csv, export_correlation_bins_to_h5
```

Output folder layout: `model_summary.toml`, `simulation_info_*.toml`, binned data + `stats.h5`,
`global_stats.csv` / `local_stats.csv`, and correlation results split into
`equal-time/`, `time-displaced/`, `integrated/`.

## 10. Density / chemical-potential tuning

```julia
import SmoQyDQMC.MuTuner as mt
chemical_potential_tuner = mt.init_mutunerlogger(
    target_density = n,
    inverse_temperature = β,
    system_size = lu.nsites(unit_cell, lattice),
    initial_chemical_potential = μ,
    complex_sign_problem = false)

# call before each update sweep (thermalization AND measurement phases):
(logdetGup, sgndetGup, logdetGdn, sgndetGdn) = update_chemical_potential!(
    Gup, logdetGup, sgndetGup, Gdn, logdetGdn, sgndetGdn;
    chemical_potential_tuner = chemical_potential_tuner,
    tight_binding_parameters = tight_binding_parameters,
    fermion_path_integral_up = fermion_path_integral_up,
    fermion_path_integral_dn = fermion_path_integral_dn,
    fermion_greens_calculator_up = fermion_greens_calculator_up,
    fermion_greens_calculator_dn = fermion_greens_calculator_dn,
    Bup = Bup, Bdn = Bdn)
save_density_tuning_profile(simulation_info, chemical_potential_tuner)
```

It uses the measured density and compressibility to iteratively drive μ toward `target_density`.

## 11. Checkpointing & MPI

`write_jld2_checkpoint`, `read_jld2_checkpoint`, `rm_jld2_checkpoints`,
`rename_complete_simulation` (resumable runs). MPI: pass `MPI.Comm` to `initialize_datafolder`;
use distinct `pID` per rank; see the `*_mpi` tutorials. `write_bins_concurrent=true` is
recommended for larger L so ranks write bins concurrently.

---

# Worked example 1 — Square-lattice Hubbard (complete, verbatim)

From the official "1a) Square Hubbard Model" tutorial. A full repulsive-Hubbard DQMC run:
define model → params → measurements → loop → analyze (incl. AFM correlation ratio).

```julia
using SmoQyDQMC
import SmoQyDQMC.LatticeUtilities as lu
import SmoQyDQMC.JDQMCFramework as dqmcf

using Random
using Printf

# Top-level function to run simulation.
function run_simulation(;
    # KEYWORD ARGUMENTS
    sID, # Simulation ID.
    U, # Hubbard interaction.
    t′, # Next-nearest-neighbor hopping amplitude.
    μ, # Chemical potential.
    L, # System size.
    β, # Inverse temperature.
    N_therm, # Number of thermalization updates.
    N_measurements, # Total number of measurements.
    N_bins, # Number of measurement bins.
    N_updates, # Number of updates per measurement.
    Δτ = 0.05, # Discretization in imaginary time.
    n_stab = 10, # Numerical stabilization period in imaginary-time slices.
    δG_max = 1e-6, # Threshold for numerical error corrected by stabilization.
    symmetric = false, # Whether symmetric propagator definition is used.
    checkerboard = false, # Whether checkerboard approximation is used.
    seed = abs(rand(Int)), # Seed for random number generator.
    filepath = "." # Filepath to where data folder will be created.
)

    # Construct the foldername the data will be written to.
    datafolder_prefix = @sprintf "hubbard_square_U%.2f_tp%.2f_mu%.2f_L%d_b%.2f" U t′ μ L β

    # Initialize simulation info.
    simulation_info = SimulationInfo(
        filepath = filepath,
        datafolder_prefix = datafolder_prefix,
        write_bins_concurrent = (L > 10),
        sID = sID
    )

    # Initialize the directory the data will be written to.
    initialize_datafolder(simulation_info)

    # Initialize random number generator
    rng = Xoshiro(seed)

    # Initialize metadata dictionary
    metadata = Dict()

    # Record simulation parameters.
    metadata["N_therm"] = N_therm
    metadata["N_measurements"] = N_measurements
    metadata["N_updates"] = N_updates
    metadata["N_bins"] = N_bins
    metadata["n_stab_init"] = n_stab
    metadata["dG_max"] = δG_max
    metadata["symmetric"] = symmetric
    metadata["checkerboard"] = checkerboard
    metadata["seed"] = seed
    metadata["local_acceptance_rate"] = 0.0
    metadata["reflection_acceptance_rate"] = 0.0

    # Define unit cell.
    unit_cell = lu.UnitCell(
        lattice_vecs = [[1.0, 0.0],
                        [0.0, 1.0]],
        basis_vecs = [[0.0, 0.0]]
    )

    # Define finite lattice with periodic boundary conditions.
    lattice = lu.Lattice(
        L = [L, L],
        periodic = [true, true]
    )

    # Initialize model geometry.
    model_geometry = ModelGeometry(
        unit_cell, lattice
    )

    # Define the nearest-neighbor bond in +x direction.
    bond_px = lu.Bond(
        orbitals = (1,1),
        displacement = [1, 0]
    )

    # Add this bond definition to the model, by adding it the model_geometry.
    bond_px_id = add_bond!(model_geometry, bond_px)

    # Define the nearest-neighbor bond in +y direction.
    bond_py = lu.Bond(
        orbitals = (1,1),
        displacement = [0, 1]
    )

    # Add this bond definition to the model, by adding it the model_geometry.
    bond_py_id = add_bond!(model_geometry, bond_py)

    # Define the nearest-neighbor bond in -x direction.
    # Will be used to make measurements later in this tutorial.
    bond_nx = lu.Bond(
        orbitals = (1,1),
        displacement = [-1, 0]
    )

    # Add this bond definition to the model, by adding it the model_geometry.
    bond_nx_id = add_bond!(model_geometry, bond_nx)

    # Define the nearest-neighbor bond in -y direction.
    # Will be used to make measurements later in this tutorial.
    bond_ny = lu.Bond(
        orbitals = (1,1),
        displacement = [0, -1]
    )

    # Add this bond definition to the model, by adding it the model_geometry.
    bond_ny_id = add_bond!(model_geometry, bond_ny)

    # Define the next-nearest-neighbor bond in +x+y direction.
    bond_pxpy = lu.Bond(
        orbitals = (1,1),
        displacement = [1, 1]
    )

    # Add this bond definition to the model, by adding it the model_geometry.
    bond_pxpy_id = add_bond!(model_geometry, bond_pxpy)

    # Define the next-nearest-neighbor bond in +x-y direction.
    bond_pxny = lu.Bond(
        orbitals = (1,1),
        displacement = [1, -1]
    )

    # Add this bond definition to the model, by adding it the model_geometry.
    bond_pxny_id = add_bond!(model_geometry, bond_pxny)

    # Set nearest-neighbor hopping amplitude to unity,
    # setting the energy scale in the model.
    t = 1.0

    # Define the non-interacting tight-binding model.
    tight_binding_model = TightBindingModel(
        model_geometry = model_geometry,
        t_bonds = [bond_px, bond_py, bond_pxpy, bond_pxny], # defines hopping
        t_mean = [t, t, t′, t′], # defines corresponding mean hopping amplitude
        t_std = [0., 0., 0., 0.], # defines corresponding standard deviation in hopping amplitude
        ϵ_mean = [0.], # set mean on-site energy for each orbital in unit cell
        ϵ_std = [0.], # set standard deviation of on-site energy or each orbital in unit cell
        μ  = μ # set chemical potential
    )

    # Define the Hubbard interaction in the model.
    hubbard_model = HubbardModel(
        ph_sym_form = true, # if particle-hole symmetric form for Hubbard interaction is used.
        U_orbital = [1], # orbitals in unit cell with Hubbard interaction.
        U_mean = [U], # mean Hubbard interaction strength for corresponding orbital species in unit cell.
        U_std = [0.], # standard deviation of Hubbard interaction strength for corresponding orbital species in unit cell.
    )

    # Write model summary TOML file specifying Hamiltonian that will be simulated.
    model_summary(
        simulation_info = simulation_info,
        β = β, Δτ = Δτ,
        model_geometry = model_geometry,
        tight_binding_model = tight_binding_model,
        interactions = (hubbard_model,)
    )

    # Initialize tight-binding parameters.
    tight_binding_parameters = TightBindingParameters(
        tight_binding_model = tight_binding_model,
        model_geometry = model_geometry,
        rng = rng
    )

    # Initialize Hubbard interaction parameters.
    hubbard_parameters = HubbardParameters(
        model_geometry = model_geometry,
        hubbard_model = hubbard_model,
        rng = rng
    )

    # Apply Spin Hirsch Hubbard-Stratonovich (HS) transformation to decouple the Hubbard interaction,
    # and initialize the corresponding HS fields that will be sampled in the DQMC simulation.
    hst_parameters = HubbardSpinHirschHST(
        β = β, Δτ = Δτ,
        hubbard_parameters = hubbard_parameters,
        rng = rng
    )

    # Initialize the container that measurements will be accumulated into.
    measurement_container = initialize_measurement_container(model_geometry, β, Δτ)

    # Initialize the tight-binding model related measurements, like the hopping energy.
    initialize_measurements!(measurement_container, tight_binding_model)

    # Initialize the Hubbard interaction related measurements.
    initialize_measurements!(measurement_container, hubbard_model)

    # Initialize the single-particle electron Green's function measurement.
    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "greens",
        time_displaced = true,
        pairs = [(1, 1)]
    )

    # Initialize density correlation function measurement.
    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "density",
        time_displaced = false,
        integrated = true,
        pairs = [(1, 1)]
    )

    # Initialize the pair correlation function measurement.
    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "pair",
        time_displaced = false,
        integrated = true,
        pairs = [(1, 1)]
    )

    # Initialize the spin-z correlation function measurement.
    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "spin_z",
        time_displaced = false,
        integrated = true,
        pairs = [(1, 1)]
    )

    # Initialize the d-wave pair susceptibility measurement.
    initialize_composite_correlation_measurement!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        name = "d-wave",
        correlation = "pair",
        ids = [bond_px_id, bond_nx_id, bond_py_id, bond_ny_id],
        coefficients = [0.5, 0.5, -0.5, -0.5],
        time_displaced = false,
        integrated = true
    )

    # Allocate FermionPathIntegral type for spin-up electrons.
    fermion_path_integral_up = FermionPathIntegral(
        tight_binding_parameters = tight_binding_parameters, β = β, Δτ = Δτ,
        forced_complex_potential = (U < 0),
        forced_complex_kinetic = false
    )

    # Allocate FermionPathIntegral type for spin-down electrons.
    fermion_path_integral_dn = FermionPathIntegral(
        tight_binding_parameters = tight_binding_parameters, β = β, Δτ = Δτ,
        forced_complex_potential = (U < 0),
        forced_complex_kinetic = false
    )

    # Initialize FermionPathIntegral type for both the spin-up and spin-down electrons to account for Hubbard interaction.
    initialize!(fermion_path_integral_up, fermion_path_integral_dn, hubbard_parameters)

    # Initialize FermionPathIntegral type for both the spin-up and spin-down electrons to account for the current
    # Hubbard-Stratonovich field configuration.
    initialize!(fermion_path_integral_up, fermion_path_integral_dn, hst_parameters)

    # Initialize imaginary-time propagators for all imaginary-time slices for spin-up and spin-down electrons.
    Bup = initialize_propagators(fermion_path_integral_up, symmetric=symmetric, checkerboard=checkerboard)
    Bdn = initialize_propagators(fermion_path_integral_dn, symmetric=symmetric, checkerboard=checkerboard)

    # Initialize FermionGreensCalculator type for spin-up and spin-down electrons.
    fermion_greens_calculator_up = dqmcf.FermionGreensCalculator(Bup, β, Δτ, n_stab)
    fermion_greens_calculator_dn = dqmcf.FermionGreensCalculator(Bdn, β, Δτ, n_stab)

    # Initialize alternate FermionGreensCalculator type for performing reflection updates.
    fermion_greens_calculator_up_alt = dqmcf.FermionGreensCalculator(fermion_greens_calculator_up)
    fermion_greens_calculator_dn_alt = dqmcf.FermionGreensCalculator(fermion_greens_calculator_dn)

    # Allocate matrices for spin-up and spin-down electron Green's function matrices.
    Gup = zeros(eltype(Bup[1]), size(Bup[1]))
    Gdn = zeros(eltype(Bdn[1]), size(Bdn[1]))

    # Initialize the spin-up and spin-down electron Green's function matrices, also
    # calculating their respective determinants as the same time.
    logdetGup, sgndetGup = dqmcf.calculate_equaltime_greens!(Gup, fermion_greens_calculator_up)
    logdetGdn, sgndetGdn = dqmcf.calculate_equaltime_greens!(Gdn, fermion_greens_calculator_dn)

    # Allocate matrices for various time-displaced Green's function matrices.
    Gup_ττ = similar(Gup) # Gup(τ,τ)
    Gup_τ0 = similar(Gup) # Gup(τ,0)
    Gup_0τ = similar(Gup) # Gup(0,τ)
    Gdn_ττ = similar(Gdn) # Gdn(τ,τ)
    Gdn_τ0 = similar(Gdn) # Gdn(τ,0)
    Gdn_0τ = similar(Gdn) # Gdn(0,τ)

    # Initialize diagnostic parameters to asses numerical stability.
    δG = zero(logdetGup)
    δθ = zero(logdetGup)

    # Iterate over number of thermalization updates to perform.
    for n in 1:N_therm

        # Perform reflection update for HS fields with randomly chosen site.
        (accepted, logdetGup, sgndetGup, logdetGdn, sgndetGdn) = reflection_update!(
            Gup, logdetGup, sgndetGup, Gdn, logdetGdn, sgndetGdn,
            hst_parameters,
            fermion_path_integral_up = fermion_path_integral_up,
            fermion_path_integral_dn = fermion_path_integral_dn,
            fermion_greens_calculator_up = fermion_greens_calculator_up,
            fermion_greens_calculator_dn = fermion_greens_calculator_dn,
            fermion_greens_calculator_up_alt = fermion_greens_calculator_up_alt,
            fermion_greens_calculator_dn_alt = fermion_greens_calculator_dn_alt,
            Bup = Bup, Bdn = Bdn, rng = rng
        )

        # Record whether reflection update was accepted or not.
        metadata["reflection_acceptance_rate"] += accepted

        # Perform sweep all imaginary-time slice and orbitals, attempting an update to every HS field.
        (acceptance_rate, logdetGup, sgndetGup, logdetGdn, sgndetGdn, δG, δθ) = local_updates!(
            Gup, logdetGup, sgndetGup, Gdn, logdetGdn, sgndetGdn,
            hst_parameters,
            fermion_path_integral_up = fermion_path_integral_up,
            fermion_path_integral_dn = fermion_path_integral_dn,
            fermion_greens_calculator_up = fermion_greens_calculator_up,
            fermion_greens_calculator_dn = fermion_greens_calculator_dn,
            Bup = Bup, Bdn = Bdn, δG_max = δG_max, δG = δG, δθ = δθ, rng = rng,
            update_stabilization_frequency = false
        )

        # Record acceptance rate for sweep.
        metadata["local_acceptance_rate"] += acceptance_rate
    end

    # Reset diagnostic parameters used to monitor numerical stability to zero.
    δG = zero(logdetGup)
    δθ = zero(logdetGup)

    # Calculate the bin size.
    bin_size = N_measurements ÷ N_bins

    # Iterate over measurements.
    for measurement in 1:N_measurements

        # Iterate over updates between measurements.
        for update in 1:N_updates

            # Perform reflection update for HS fields with randomly chosen site.
            (accepted, logdetGup, sgndetGup, logdetGdn, sgndetGdn) = reflection_update!(
                Gup, logdetGup, sgndetGup, Gdn, logdetGdn, sgndetGdn,
                hst_parameters,
                fermion_path_integral_up = fermion_path_integral_up,
                fermion_path_integral_dn = fermion_path_integral_dn,
                fermion_greens_calculator_up = fermion_greens_calculator_up,
                fermion_greens_calculator_dn = fermion_greens_calculator_dn,
                fermion_greens_calculator_up_alt = fermion_greens_calculator_up_alt,
                fermion_greens_calculator_dn_alt = fermion_greens_calculator_dn_alt,
                Bup = Bup, Bdn = Bdn, rng = rng
            )

            # Record whether reflection update was accepted or not.
            metadata["reflection_acceptance_rate"] += accepted

            # Perform sweep all imaginary-time slice and orbitals, attempting an update to every HS field.
            (acceptance_rate, logdetGup, sgndetGup, logdetGdn, sgndetGdn, δG, δθ) = local_updates!(
                Gup, logdetGup, sgndetGup, Gdn, logdetGdn, sgndetGdn,
                hst_parameters,
                fermion_path_integral_up = fermion_path_integral_up,
                fermion_path_integral_dn = fermion_path_integral_dn,
                fermion_greens_calculator_up = fermion_greens_calculator_up,
                fermion_greens_calculator_dn = fermion_greens_calculator_dn,
                Bup = Bup, Bdn = Bdn, δG_max = δG_max, δG = δG, δθ = δθ, rng = rng,
                update_stabilization_frequency = false
            )

            # Record acceptance rate.
            metadata["local_acceptance_rate"] += acceptance_rate
        end

        # Make measurements.
        (logdetGup, sgndetGup, logdetGdn, sgndetGdn, δG, δθ) = make_measurements!(
            measurement_container,
            logdetGup, sgndetGup, Gup, Gup_ττ, Gup_τ0, Gup_0τ,
            logdetGdn, sgndetGdn, Gdn, Gdn_ττ, Gdn_τ0, Gdn_0τ,
            fermion_path_integral_up = fermion_path_integral_up,
            fermion_path_integral_dn = fermion_path_integral_dn,
            fermion_greens_calculator_up = fermion_greens_calculator_up,
            fermion_greens_calculator_dn = fermion_greens_calculator_dn,
            Bup = Bup, Bdn = Bdn, δG_max = δG_max, δG = δG, δθ = δθ,
            model_geometry = model_geometry, tight_binding_parameters = tight_binding_parameters,
            coupling_parameters = (hubbard_parameters, hst_parameters)
        )

        # Write the bin-averaged measurements to file if update ÷ bin_size == 0.
        write_measurements!(
            measurement_container = measurement_container,
            simulation_info = simulation_info,
            model_geometry = model_geometry,
            measurement = measurement,
            bin_size = bin_size,
            Δτ = Δτ
        )
    end

    # Merge binned data into a single HDF5 file.
    merge_bins(simulation_info)

    # Normalize acceptance rate.
    metadata["local_acceptance_rate"] /=  (N_therm + N_measurements * N_updates)
    metadata["reflection_acceptance_rate"] /= (N_therm + N_measurements * N_updates)

    # Record final stabilization period used at the end of the simulation.
    metadata["n_stab_final"] = fermion_greens_calculator_up.n_stab

    # Record largest numerical error.
    metadata["dG"] = δG

    # Write simulation summary TOML file.
    save_simulation_info(simulation_info, metadata)

    # Process the simulation results, calculating final error bars for all measurements.
    # writing final statistics to CSV files.
    process_measurements(
        datafolder = simulation_info.datafolder,
        n_bins = N_bins,
        export_to_csv = true,
        scientific_notation = false,
        decimals = 7,
        delimiter = " "
    )

    # Calculate AFM correlation ratio.
    Rafm, ΔRafm = compute_correlation_ratio(
        datafolder = simulation_info.datafolder,
        correlation = "spin_z",
        type = "equal-time",
        id_pairs = [(1, 1)],
        id_pair_coefficients = [1.0],
        q_point = (L÷2, L÷2),
        q_neighbors = [
            (L÷2+1, L÷2), (L÷2-1, L÷2),
            (L÷2, L÷2+1), (L÷2, L÷2-1)
        ]
    )

    # Record the AFM correlation ratio mean and standard deviation.
    metadata["Rafm_mean_real"] = real(Rafm)
    metadata["Rafm_mean_imag"] = imag(Rafm)
    metadata["Rafm_std"] = ΔRafm

    # Write simulation summary TOML file.
    save_simulation_info(simulation_info, metadata)

    return nothing
end # end of run_simulation function

# Only execute if the script is run directly from the command line.
if abspath(PROGRAM_FILE) == @__FILE__

    # Run the simulation, reading in command line arguments.
    run_simulation(;
        sID = parse(Int, ARGS[1]), # Simulation ID.
        U = parse(Float64, ARGS[2]), # Hubbard interaction strength.
        t′ = parse(Float64, ARGS[3]), # Next-nearest-neighbor hopping amplitude.
        μ = parse(Float64, ARGS[4]), # Chemical potential.
        L = parse(Int, ARGS[5]), # Lattice size.
        β = parse(Float64, ARGS[6]), # Inverse temperature.
        N_therm = parse(Int, ARGS[7]), # Number of thermalization sweeps.
        N_measurements = parse(Int, ARGS[8]), # Number of measurement to make.
        N_bins = parse(Int, ARGS[9]), # Number of measurement bins.
        N_updates = parse(Int, ARGS[10]) # Number of updates per measurement.
    )
end
```

Run: `julia hubbard_square.jl 1 6.0 0.0 0.0 4 4.0 5000 10000 100 10`
(sID U t′ μ L β N_therm N_measurements N_bins N_updates).

---

# Worked example 2 — Honeycomb Holstein electron–phonon (complete, verbatim)

From the official "2a) Honeycomb Holstein Model" tutorial. Two-orbital honeycomb cell, one
Holstein phonon per site, sampled with EFA-HMC + reflection + swap. Single shared
`FermionPathIntegral` (spin-symmetric). Ends with a CDW correlation ratio at q = Γ.

```julia
using SmoQyDQMC
import SmoQyDQMC.LatticeUtilities as lu
import SmoQyDQMC.JDQMCFramework as dqmcf

using Random
using Printf

# Top-level function to run simulation.
function run_simulation(;
    sID,
    Ω,
    α,
    μ,
    L,
    β,
    N_therm,
    N_measurements,
    N_bins,
    Nt = 8,
    Δτ = 0.05,
    n_stab = 10,
    δG_max = 1e-6,
    symmetric = false,
    checkerboard = false,
    seed = abs(rand(Int)),
    filepath = "."
)

    datafolder_prefix = @sprintf "holstein_honeycomb_w%.2f_a%.2f_mu%.2f_L%d_b%.2f" Ω α μ L β

    simulation_info = SimulationInfo(
        filepath = filepath,
        datafolder_prefix = datafolder_prefix,
        write_bins_concurrent = (L > 7),
        sID = sID
    )

    initialize_datafolder(simulation_info)

    rng = Xoshiro(seed)

    metadata = Dict()

    metadata["Nt"] = Nt
    metadata["N_therm"] = N_therm
    metadata["N_measurements"] = N_measurements
    metadata["N_bins"] = N_bins
    metadata["n_stab"] = n_stab
    metadata["dG_max"] = δG_max
    metadata["symmetric"] = symmetric
    metadata["checkerboard"] = checkerboard
    metadata["seed"] = seed

    metadata["hmc_acceptance_rate"] = 0.0
    metadata["reflection_acceptance_rate"] = 0.0
    metadata["swap_acceptance_rate"] = 0.0

    a1 = [+3/2, +√3/2]
    a2 = [+3/2, -√3/2]

    r1 = [0.0, 0.0]
    r2 = [1.0, 0.0]

    unit_cell = lu.UnitCell(
        lattice_vecs = [a1, a2],
        basis_vecs = [r1, r2]
    )

    lattice = lu.Lattice(
        L = [L, L],
        periodic = [true, true]
    )

    model_geometry = ModelGeometry(unit_cell, lattice)

    bond_1 = lu.Bond(orbitals = (1,2), displacement = [0,0])
    bond_1_id = add_bond!(model_geometry, bond_1)

    bond_2 = lu.Bond(orbitals = (1,2), displacement = [-1,0])
    bond_2_id = add_bond!(model_geometry, bond_2)

    bond_3 = lu.Bond(orbitals = (1,2), displacement = [0,-1])
    bond_3_id = add_bond!(model_geometry, bond_3)

    t = 1.0

    tight_binding_model = TightBindingModel(
        model_geometry = model_geometry,
        t_bonds = [bond_1, bond_2, bond_3],
        t_mean = [t, t, t],
        μ  = μ,
        ϵ_mean = [0.0, 0.0]
    )

    electron_phonon_model = ElectronPhononModel(
        model_geometry = model_geometry,
        tight_binding_model = tight_binding_model
    )

    phonon_1 = PhononMode(
        basis_vec = r1,
        Ω_mean = Ω
    )

    phonon_1_id = add_phonon_mode!(
        electron_phonon_model = electron_phonon_model,
        phonon_mode = phonon_1
    )

    phonon_2 = PhononMode(
        basis_vec = r2,
        Ω_mean = Ω
    )

    phonon_2_id = add_phonon_mode!(
        electron_phonon_model = electron_phonon_model,
        phonon_mode = phonon_2
    )

    holstein_coupling_1 = HolsteinCoupling(
        model_geometry = model_geometry,
        phonon_id = phonon_1_id,
        orbital_id = 1,
        displacement = [0, 0],
        α_mean = α,
        ph_sym_form = true,
    )

    holstein_coupling_1_id = add_holstein_coupling!(
        electron_phonon_model = electron_phonon_model,
        holstein_coupling = holstein_coupling_1,
        model_geometry = model_geometry
    )

    holstein_coupling_2 = HolsteinCoupling(
        model_geometry = model_geometry,
        phonon_id = phonon_2_id,
        orbital_id = 2,
        displacement = [0, 0],
        α_mean = α,
        ph_sym_form = true,
    )

    holstein_coupling_2_id = add_holstein_coupling!(
        electron_phonon_model = electron_phonon_model,
        holstein_coupling = holstein_coupling_2,
        model_geometry = model_geometry
    )

    model_summary(
        simulation_info = simulation_info,
        β = β, Δτ = Δτ,
        model_geometry = model_geometry,
        tight_binding_model = tight_binding_model,
        interactions = (electron_phonon_model,)
    )

    tight_binding_parameters = TightBindingParameters(
        tight_binding_model = tight_binding_model,
        model_geometry = model_geometry,
        rng = rng
    )

    electron_phonon_parameters = ElectronPhononParameters(
        β = β, Δτ = Δτ,
        electron_phonon_model = electron_phonon_model,
        tight_binding_parameters = tight_binding_parameters,
        model_geometry = model_geometry,
        rng = rng
    )

    measurement_container = initialize_measurement_container(model_geometry, β, Δτ)

    initialize_measurements!(measurement_container, tight_binding_model)

    initialize_measurements!(measurement_container, electron_phonon_model)

    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "greens",
        time_displaced = true,
        pairs = [
            (1, 1), (2, 2), (1, 2)
        ]
    )

    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "phonon_greens",
        time_displaced = true,
        pairs = [
            (1, 1), (2, 2), (1, 2)
        ]
    )

    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "density",
        time_displaced = false,
        integrated = true,
        pairs = [
            (1, 1), (2, 2),
        ]
    )

    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "pair",
        time_displaced = false,
        integrated = true,
        pairs = [
            (1, 1), (2, 2)
        ]
    )

    initialize_correlation_measurements!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        correlation = "spin_z",
        time_displaced = false,
        integrated = true,
        pairs = [
            (1, 1), (2, 2)
        ]
    )

    initialize_composite_correlation_measurement!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        name = "tr_greens",
        correlation = "greens",
        id_pairs = [(1,1), (2,2)],
        coefficients = [1.0, 1.0],
        time_displaced = true,
    )

    initialize_composite_correlation_measurement!(
        measurement_container = measurement_container,
        model_geometry = model_geometry,
        name = "cdw",
        correlation = "density",
        ids = [1, 2],
        coefficients = [1.0, -1.0],
        displacement_vecs = [[0.0, 0.0], [0.0, 0.0]],
        time_displaced = false,
        integrated = true
    )

    fermion_path_integral = FermionPathIntegral(tight_binding_parameters = tight_binding_parameters, β = β, Δτ = Δτ)

    initialize!(fermion_path_integral, electron_phonon_parameters)

    B = initialize_propagators(fermion_path_integral, symmetric=symmetric, checkerboard=checkerboard)

    fermion_greens_calculator = dqmcf.FermionGreensCalculator(B, β, Δτ, n_stab)

    fermion_greens_calculator_alt = dqmcf.FermionGreensCalculator(fermion_greens_calculator)

    G = zeros(eltype(B[1]), size(B[1]))

    logdetG, sgndetG = dqmcf.calculate_equaltime_greens!(G, fermion_greens_calculator)

    G_ττ = similar(G)
    G_τ0 = similar(G)
    G_0τ = similar(G)

    δG = zero(logdetG)
    δθ = zero(logdetG)

    hmc_updater = EFAHMCUpdater(
        electron_phonon_parameters = electron_phonon_parameters,
        G = G, Nt = Nt, Δt = π/(2*Nt)
    )

    for n in 1:N_therm

        (accepted, logdetG, sgndetG) = reflection_update!(
            G, logdetG, sgndetG, electron_phonon_parameters,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            fermion_greens_calculator_alt = fermion_greens_calculator_alt,
            B = B, rng = rng
        )

        metadata["reflection_acceptance_rate"] += accepted

        (accepted, logdetG, sgndetG) = swap_update!(
            G, logdetG, sgndetG, electron_phonon_parameters,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            fermion_greens_calculator_alt = fermion_greens_calculator_alt,
            B = B, rng = rng
        )

        metadata["swap_acceptance_rate"] += accepted

        (accepted, logdetG, sgndetG, δG, δθ) = hmc_update!(
            G, logdetG, sgndetG, electron_phonon_parameters, hmc_updater,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            fermion_greens_calculator_alt = fermion_greens_calculator_alt,
            B = B, δG_max = δG_max, δG = δG, δθ = δθ, rng = rng
        )

        metadata["hmc_acceptance_rate"] += accepted
    end

    δG = zero(logdetG)
    δθ = zero(logdetG)

    bin_size = N_measurements ÷ N_bins

    for measurement in 1:N_measurements

        (accepted, logdetG, sgndetG) = reflection_update!(
            G, logdetG, sgndetG, electron_phonon_parameters,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            fermion_greens_calculator_alt = fermion_greens_calculator_alt,
            B = B, rng = rng
        )

        metadata["reflection_acceptance_rate"] += accepted

        (accepted, logdetG, sgndetG) = swap_update!(
            G, logdetG, sgndetG, electron_phonon_parameters,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            fermion_greens_calculator_alt = fermion_greens_calculator_alt,
            B = B, rng = rng
        )

        metadata["swap_acceptance_rate"] += accepted

        (accepted, logdetG, sgndetG, δG, δθ) = hmc_update!(
            G, logdetG, sgndetG, electron_phonon_parameters, hmc_updater,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            fermion_greens_calculator_alt = fermion_greens_calculator_alt,
            B = B, δG_max = δG_max, δG = δG, δθ = δθ, rng = rng
        )

        metadata["hmc_acceptance_rate"] += accepted

        (logdetG, sgndetG, δG, δθ) = make_measurements!(
            measurement_container,
            logdetG, sgndetG, G, G_ττ, G_τ0, G_0τ,
            fermion_path_integral = fermion_path_integral,
            fermion_greens_calculator = fermion_greens_calculator,
            B = B, δG_max = δG_max, δG = δG, δθ = δθ,
            model_geometry = model_geometry, tight_binding_parameters = tight_binding_parameters,
            coupling_parameters = (electron_phonon_parameters,)
        )

        write_measurements!(
            measurement_container = measurement_container,
            simulation_info = simulation_info,
            model_geometry = model_geometry,
            measurement = measurement,
            bin_size = bin_size,
            Δτ = Δτ
        )
    end

    merge_bins(simulation_info)

    metadata["hmc_acceptance_rate"] /= (N_measurements + N_therm)
    metadata["reflection_acceptance_rate"] /= (N_measurements + N_therm)
    metadata["swap_acceptance_rate"] /= (N_measurements + N_therm)

    metadata["dG"] = δG

    save_simulation_info(simulation_info, metadata)

    process_measurements(
        datafolder = simulation_info.datafolder,
        n_bins = N_bins,
        export_to_csv = true,
        scientific_notation = false,
        decimals = 7,
        delimiter = " "
    )

    Rcdw, ΔRcdw = compute_composite_correlation_ratio(
        datafolder = simulation_info.datafolder,
        name = "cdw",
        type = "equal-time",
        q_point = (0, 0),
        q_neighbors = [
            (1,0),   (0,1),   (1,1),
            (L-1,0), (0,L-1), (L-1,L-1)
        ]
    )

    metadata["Rcdw_mean_real"] = real(Rcdw)
    metadata["Rcdw_mean_imag"] = imag(Rcdw)
    metadata["Rcdw_std"]       = ΔRcdw

    save_simulation_info(simulation_info, metadata)

    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__

    run_simulation(;
        sID = parse(Int, ARGS[1]),
        Ω = parse(Float64, ARGS[2]),
        α = parse(Float64, ARGS[3]),
        μ = parse(Float64, ARGS[4]),
        L = parse(Int, ARGS[5]),
        β = parse(Float64, ARGS[6]),
        N_therm = parse(Int, ARGS[7]),
        N_measurements = parse(Int, ARGS[8]),
        N_bins = parse(Int, ARGS[9])
    )
end
```

Run: `julia holstein_honeycomb.jl 1 1.0 1.5 0.0 3 4.0 2000 5000 50`
(sID Ω α μ L β N_therm N_measurements N_bins).

### EFA-HMC details (verbatim signatures)

```julia
EFAHMCUpdater(; electron_phonon_parameters, G, Nt::Int,
              Δt = π/(2*Nt), reg = 0.0, δ = 0.05)
   # Nt = leapfrog steps; Δt = step size (default = QHO quarter-period); δ jitters Δt;
   # reg regularizes near-zero-frequency (acoustic) modes.

hmc_update!(G, logdetG, sgndetG, electron_phonon_parameters, hmc_updater;
    fermion_path_integral, fermion_greens_calculator, fermion_greens_calculator_alt, B,
    δG, δθ, rng, update_stabilization_frequency=false,
    δG_max=1e-5, δG_reject=1e-2, recenter!=identity,
    Nt=hmc_updater.Nt, Δt=hmc_updater.Δt, δ=hmc_updater.δ)
```

---

# Pitfalls & tuning

- **Trotter error O(Δτ²).** Results carry a systematic bias ∝ Δτ². `Δτ = 0.05–0.1` is typical;
  for quantitative work extrapolate Δτ → 0. `symmetric=true` (Eq.16, B = e^(−Δτ/2 K) e^(−Δτ V)
  e^(−Δτ/2 K)) is preferred when e-ph modulates hopping with the checkerboard approximation;
  `symmetric=false` (Eq.17) is cheaper for static kinetic energy.
- **Fermion sign problem.** Weights `W = e^(−Re S_B) ∏σ |det Mσ|` are positive only by taking the
  absolute value; the average sign `⟨sgn⟩` (global measurement `sgn`) decays exponentially as
  β grows, away from half filling, or with frustration/complex hopping. Always report `⟨sgn⟩`:
  small `⟨sgn⟩` (≪ 1) means estimators are reweighted by a near-zero denominator and error bars
  blow up. Half-filled bipartite Hubbard and attractive-U (density-channel HS) are sign-free.
- **Thermalization & binning.** Make NO measurements during `N_therm`; the initial random field
  configuration is far from equilibrium. Bin size `N_measurements ÷ N_bins` must exceed the
  autocorrelation time, or error bars are underestimated — increase `N_updates` between
  measurements and/or `N_bins`. Errors come from binned statistics; complex-observable error is
  `ΔC = √(ΔC_Re² + ΔC_Im²)`.
- **Numerical stabilization interval `n_stab`.** The product of Lτ B-matrices is exponentially
  ill-conditioned; G is recomputed via stabilized factorization every `n_stab` slices.
  `n_stab ≈ 10` is typical. The `δG` / `δθ` diagnostics track the discrepancy between fast-updated
  and recomputed G; if `δG > δG_max` the stabilization frequency is increased automatically
  (`update_stabilization_frequency=true`). Monitor the final `δG` — large `δG` ⇒ untrustworthy run;
  lower `n_stab` (or `δτ` smaller). At large β/large U you may need `n_stab` ≈ 5.
- **Phonon HMC tuning.** Target HMC acceptance ≈ 0.6–0.9. Tune trajectory length via `Nt` and
  step `Δt` (default `Δt = π/(2·Nt)` matches the QHO quarter period); too-large `Δt·Nt` lowers
  acceptance, too-small wastes effort with high autocorrelation. `δ` jitters `Δt` to avoid
  resonances. For acoustic / near-zero-frequency modes raise `reg`. Combine HMC with
  `reflection_update!` and `swap_update!` (and `radial_update!`) to cross sign/displacement
  barriers HMC alone tunnels through slowly. `δG_reject` rejects trajectories whose
  Green's-function error exceeds the threshold rather than corrupting the chain.
- **`ph_sym_form` & complex flags.** Use `ph_sym_form=true` (particle-hole-symmetric form) at
  half filling. For attractive U (`U < 0`) set `forced_complex_potential = (U < 0)` on the
  `FermionPathIntegral` as the examples do. Complex hopping / twisted boundary conditions force
  complex arithmetic throughout.
- **Density tuning convergence.** When using `update_chemical_potential!`, μ drifts during
  thermalization; only the post-thermalization μ (logged via `save_density_tuning_profile`) is
  the converged value — verify the measured `density` global observable matches `target_density`
  within error before trusting other observables.
