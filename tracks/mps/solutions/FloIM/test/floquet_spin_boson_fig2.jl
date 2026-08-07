# Reproduce Fig. 2 of Mickiewicz, Link & Strunz, PRL 136, 200201 (2026)
# Driven spin-boson model, transversal driving H_drive = ε_d cos(ω_d t) σ_z
# Exact uniTEMPO Floquet-IF dynamics vs Redfield-Magnus master equation
#
# Usage: julia --project=<env> floquet_spin_boson_fig2.jl <run_dir> [tol]
# <run_dir> must contain zenodo/ with the authors' fig_2 CSVs for validation.

using UniformTEMPO
using LinearAlgebra
using Printf
using DelimitedFiles
using SpecialFunctions
using Plots

const RUN_DIR = length(ARGS) >= 1 ? ARGS[1] : "."
const TOL = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 1e-7

# ---------- model parameters (paper Fig. 2 + Zenodo fig_2.jl) ----------
const Ω = 1       # qubit splitting, sets the unit
const ϵd = 1.0       # driving amplitude
const α = 0.05       # dimensionless coupling, J(ω) = α ω exp(-ω/ω_c)
const ωc = 2.5       # bath cutoff
const δt = π / 60    # Trotter step (paper)
const t_max = 200.0  # authors' data range; figure shows [0, 60]
const n = floor(Int, t_max / δt)

const σz = ComplexF64[1 0; 0 -1]
const σx = ComplexF64[0 1; 1 0]

# zero-temperature Ohmic bath with exponential cutoff:
# α(t) = ∫_0^∞ dω J(ω) e^{-iωt} = α ω_c^2 / (1 + i ω_c t)^2
bcf(t) = α * (ωc / (1 + im * ωc * t))^2

# ---------- 1. exact uniTEMPO influence functional (shared by both panels) ----------
println("=== uniTEMPO: contracting influence functional (tol = $TOL) ===")
flush(stdout)
t_if = @elapsed pt = uniTEMPO(σz, δt, bcf, TOL)
χ = bond_dim(pt)
@printf("influence functional built in %.1f s, bond dimension χ = %d (paper: 235)\n", t_if, χ)
flush(stdout)

ρ0 = ComplexF64[1 0; 0 0]  # |↑z><↑z|

function exact_dynamics(ωd)
    h_s(t) = Ω / 2 * σx + ϵd * cos(ωd * t) * σz
    t_ev = @elapsed ρ_t = evolve(pt, ρ0, n; h_s=h_s)
    sz = [real(tr(σz * ρ)) for ρ in ρ_t]
    @printf("  exact dynamics ωd=%.1f done in %.1f s\n", ωd, t_ev)
    flush(stdout)
    return sz
end

# ---------- 2. Redfield-Magnus ----------
# Drive commutes with coupling S = σ_z. First-order Floquet-Magnus: the O(1/ω_d)
# commutator term [H_{-1}, H_1]/(2ω_d) vanishes (H_{±1} ∝ σ_z), so the effective
# Hamiltonian is the plain time average H_F = Ω/2 σ_x (NO tunneling renormalization —
# validated against the authors' Redfield-Magnus data, max|Δ| = 1.2e-5; a Bessel
# J_0-renormalized Ω̃ is ruled out at |Δ| = 0.54). The micromotion kick
# ~ exp(-i (ε_d/ω_d) sin(ω_d t) σ_z) leaves <σ_z> invariant.

# one-sided Fourier transform of the bath correlation, Γ(ω) = ∫_0^∞ ds e^{iωs} α(s)
function bath_Gamma(ω)
    re = ω > 0 ? π * α * ω * exp(-ω / ωc) : 0.0
    g = if ω > 0
        exp(-ω / ωc) * expinti(ω / ωc)          # PV ∫ e^{-x/ωc}/(ω-x) dx = e^{-ω/ωc} Ei(ω/ωc)
    elseif ω < 0
        -exp(abs(ω) / ωc) * expint(abs(ω) / ωc) # = -e^{|ω|/ωc} E_1(|ω|/ωc)
    else
        0.0
    end
    return re + 1im * α * (-ωc + ω * g)
end

function redfield_magnus(ωd)
    Ω̃ = Ω  # first-order Magnus: no renormalization (see comment above)
    # energy basis of H_eff = Ω̃/2 σ_x: τ_z = σ_x, coupling S = σ_z = τ_x
    E = [Ω̃ / 2, -Ω̃ / 2]
    S = ComplexF64[0 1; 1 0]  # σ_z in the energy basis
    Hs = Diagonal(E)

    Γ = [bath_Gamma(E[a] - E[b]) for a in 1:2, b in 1:2]
    A = [S[m, n] * Γ[n, m] for m in 1:2, n in 1:2]        # ∫ α(s) S(-s) ds
    B = [S[m, n] * conj(Γ[m, n]) for m in 1:2, n in 1:2]  # ∫ α*(s) S(-s) ds

    # Redfield superoperator (column-major vec convention, vec(AXB) = (Bᵀ ⊗ A) vec X):
    # Rρ = -[S, Aρ] + [S, ρB],  A = ∫ α(s) S(-s) ds,  B = ∫ α*(s) S(-s) ds
    SA = S * A
    BS = B * S
    R = -kron(I(2), SA) + kron(transpose(S), A) + kron(transpose(B), S) - kron(transpose(BS), I(2))
    L = -1im * (kron(I(2), Hs) - kron(transpose(Hs), I(2))) + R

    ρ0_en = ComplexF64[0.5 0.5; 0.5 0.5]  # |↑z> = (|+>_x + |->_x)/√2
    sz = Vector{Float64}(undef, n + 1)
    for k in 0:n
        ρ = reshape(exp(L * (k * δt)) * vec(ρ0_en), 2, 2)
        sz[k+1] = real(tr([0 1; 1 0] * ρ))  # <σ_z> = tr(τ_x ρ)
    end
    @printf("  Redfield-Magnus ωd=%.1f: Ω̃ = %.5f, down-rate γ = %.5f\n",
            ωd, Ω̃, 2 * π * α * Ω̃ * exp(-Ω̃ / ωc))
    flush(stdout)
    return sz
end

# ---------- 3. run both panels + validate against authors' CSVs ----------
panels = [(2.5, "left"), (10.0, "right")]
t_eval = collect(0:n) .* δt
mkpath(RUN_DIR)

results = Dict{Float64,Dict{String,Vector{Float64}}}()
for (ωd, _) in panels
    results[ωd] = Dict("exact" => exact_dynamics(ωd), "rm" => redfield_magnus(ωd))
end

println("\n=== validation vs authors' Zenodo CSVs (max |Δ| over Ωt ∈ [0, 60]) ===")
mask = t_eval .<= 60 .+ 1e-12
for (ωd, _) in panels
    for (kind, tag) in [("exact", "exact"), ("rm", "Redfield_Magnus")]
        f = joinpath(RUN_DIR, "zenodo",
            @sprintf("dynamics_%s_Ω_1_ϵ_d_1_ω_d_%s_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv",
                     tag, ωd == 2.5 ? "2.5" : "10"))
        ref = readdlm(f, Float64)[:]
        ours = results[ωd][kind]
        m = min(length(ref), length(ours), count(mask))
        dev = maximum(abs.(ours[1:m] .- ref[1:m]))
        @printf("  ωd=%4.1f %-16s max|Δ| = %.4e  (ref ⟨σz⟩(t=60) = %+.4f, ours = %+.4f)\n",
                ωd, kind, dev, ref[m], ours[m])
    end
end
flush(stdout)

# ---------- 4. figure: two panels like Fig. 2 ----------
gr()
plots = map(panels) do (ωd, side)
    p = plot(xlabel="time Ωt", ylabel="⟨σz(t)⟩", xlim=(0, 60), ylim=(-1, 1),
             framestyle=:box, legend=(side == "right" ? :topright : false),
             title=@sprintf("ω_d = %sΩ", ωd == 2.5 ? "2.5" : "10"), titlefontsize=10)
    plot!(p, t_eval[mask], results[ωd]["exact"][mask], lw=1.6, color="#0C7BDC", label="exact (ours)")
    plot!(p, t_eval[mask], results[ωd]["rm"][mask], lw=1.4, ls=:dash, color="#fb6d72", label="Redfield-Magnus (ours)")
    # authors' data as thin overlay
    for (kind, tag) in [("exact", "exact"), ("rm", "Redfield_Magnus")]
        f = joinpath(RUN_DIR, "zenodo",
            @sprintf("dynamics_%s_Ω_1_ϵ_d_1_ω_d_%s_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv",
                     tag, ωd == 2.5 ? "2.5" : "10"))
        ref = readdlm(f, Float64)[:]
        plot!(p, t_eval[1:length(ref)][mask[1:length(ref)]], ref[mask[1:length(ref)]],
              lw=0.8, color=:gray70, alpha=0.7, label=kind == "exact" ? "authors (Zenodo)" : "")
    end
    return p
end
fig = plot(plots..., layout=(1, 2), size=(900, 380), margin=5Plots.mm)
savefig(fig, joinpath(RUN_DIR, "fig2_reproduction.png"))

# save our curves
for (ωd, _) in panels
    writedlm(joinpath(RUN_DIR, @sprintf("ours_omega_d_%s.csv", ωd)),
             hcat(t_eval, results[ωd]["exact"], results[ωd]["rm"]))
end
println("\nfigure + data written to $RUN_DIR")
