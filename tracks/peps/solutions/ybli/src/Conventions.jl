"""
    ModelConvention

Machine-readable convention object that every executable prints before running.
Encodes all normalization, boundary, sector, and sign conventions so that
normalization ambiguity cannot spread silently into later modules.

Design rationale (workflow §2): in arXiv:2502.14034 a symbol Z(e,m) is used
for a single-layer Ising amplitude while the physical probability is
proportional to Z(e,m)^2.  A missing square changes Metropolis ratios and
shifts the fitted Casimir term.  Similarly, E[log Z_m] ≠ log E[Z_m].
"""
struct ModelConvention
    # What the local object called Z represents
    #   :amplitude       — single-layer wave-function amplitude
    #   :partition       — classical partition function
    #   :squared_norm    — ⟨ψ(m)|ψ(m)⟩ (double-layer Born weight)
    #   :probability     — already normalized P(m) = Z_m / Z_total
    ztype::Symbol

    # Exponent κ in P(m) ∝ |Z_raw(m)|^κ
    #   κ = 1  for classical partition / single-layer amplitude
    #   κ = 2  for Born probability from a real amplitude  (Z^2)
    #   κ = 1  for Born probability from a squared-norm weight
    kappa::Float64

    # Multiplicative prefactor in Z = prefactor × ∏_y T_y
    prefactor::Float64

    # Additive constant added to log Z (e.g. from normalization or gauge fixing)
    log_offset::Float64

    # Boundary conditions
    #   bc_x: transverse direction (circumference)  — :periodic / :antiperiodic / :open
    #   bc_y: transfer direction (longitudinal)     — :periodic / :open
    bc_x::Symbol
    bc_y::Symbol

    # Global flux sector (for toric-code / class-D models)
    #   Integer winding number, or `nothing` if not applicable
    flux_sector::Union{Int,Nothing}

    # Fermion-parity sector (+1 even, -1 odd, `nothing` if not applicable)
    parity_sector::Union{Int,Nothing}

    # Spacetime anisotropy factor α (workflow §6.1)
    #   α = 1 for isotropic lattice; fit independently otherwise
    anisotropy::Float64

    # Critical coupling (β_c for Ising, p_c for Nishimori, etc.)
    critical_coupling::Float64

    # Disorder distribution
    #   :clean       — deterministic bonds
    #   :nishimori   — ±J at Nishimori point
    #   :custom      — user-defined
    disorder::Symbol

    # Sign convention for free energy
    #   :standard  → Φ_L = −(1/L_y) log Z_m   (free energy per row)
    #   :negative  → Φ_L = +(1/L_y) log Z_m
    sign_convention::Symbol

    # Human-readable model name
    model_name::String
end

"""Default convention for the clean 2D Ising model (test case)."""
function ClassicalIsingConvention(; beta::Float64 = log(1+sqrt(2))/2,
                                     J::Float64 = 1.0,
                                     bc_y::Symbol = :periodic)
    ModelConvention(
        :partition,        # ztype
        1.0,               # kappa (classical weight, P ∝ Z)
        1.0,               # prefactor
        0.0,               # log_offset
        :periodic,         # bc_x (cylinder circumference)
        bc_y,              # bc_y (transfer direction)
        nothing,           # flux_sector
        nothing,           # parity_sector
        1.0,               # anisotropy α (isotropic)
        beta,              # critical_coupling (= β_c for Ising)
        :clean,            # disorder
        :standard,         # sign_convention
        "ClassicalIsing(J=$J, β=$(round(beta, digits=4)), bc_y=$bc_y)"
    )
end

"""Convention for the ±J RBIM at the Nishimori multicritical point."""
function NishimoriConvention(; p::Float64 = 0.8899,  # prob of ferro bond
                                J::Float64 = 1.0)
    # Nishimori line: exp(-2βJ) = (1-p)/p  →  β = (1/2J) log(p/(1-p))
    beta_N = 0.5 * log(p / (1 - p)) / J
    ModelConvention(
        :partition,
        1.0,               # kappa
        1.0,               # prefactor
        0.0,
        :periodic,
        :open,             # open in transfer direction (long cylinder)
        nothing,
        nothing,
        1.0,               # α (isotropic at Nishimori point)
        beta_N,            # critical coupling
        :nishimori,
        :standard,
        "NishimoriRBIM(p=$(round(p, digits=4)), β_N=$(round(beta_N, digits=4)))"
    )
end

"""Convention for the measured toric code → Born-weight tensor network."""
function MeasuredToricCodeConvention(; measurement_rate::Float64 = 1.0,
                                        sector::String = "W+1_even")
    parts = split(sector, "_")
    flux_part = length(parts) >= 1 ? parts[1] : sector
    flux = startswith(flux_part, "W") ? parse(Int, flux_part[2:end]) : nothing
    parity = occursin("even", sector) ? 1 : (occursin("odd", sector) ? -1 : nothing)
    ModelConvention(
        :squared_norm,     # Z_m = ⟨ψ(m)|ψ(m)⟩
        1.0,               # kappa (already a squared norm)
        1.0,
        0.0,
        :periodic,
        :open,
        flux,
        parity,
        1.0,               # α = 1 at self-dual point
        1.0,               # critical coupling (self-dual measurement rate)
        :custom,
        :standard,
        "MeasuredToricCode(rate=$measurement_rate, sector=$sector)"
    )
end

function Base.show(io::IO, conv::ModelConvention)
    println(io, "═══ ModelConvention: $(conv.model_name) ═══")
    println(io, "  Z type          : $(conv.ztype)")
    println(io, "  κ (Born exponent): $(conv.kappa)")
    println(io, "  Prefactor       : $(conv.prefactor)")
    println(io, "  Log offset      : $(conv.log_offset)")
    println(io, "  BC (x, y)       : ($(conv.bc_x), $(conv.bc_y))")
    println(io, "  Flux sector     : $(conv.flux_sector)")
    println(io, "  Parity sector   : $(conv.parity_sector)")
    println(io, "  Anisotropy α    : $(conv.anisotropy)")
    println(io, "  Critical coupling: $(conv.critical_coupling)")
    println(io, "  Disorder        : $(conv.disorder)")
    println(io, "  Sign convention : $(conv.sign_convention)")
end

"""Compute the free-energy per row from log Z_m given the convention."""
function free_energy_per_row(conv::ModelConvention, logZ::Real, Ly::Integer)
    if conv.sign_convention == :standard
        return -(logZ + conv.log_offset) / Ly
    else
        return (logZ + conv.log_offset) / Ly
    end
end
