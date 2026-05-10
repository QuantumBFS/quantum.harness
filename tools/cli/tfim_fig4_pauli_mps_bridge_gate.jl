# Small-scale gate for the Fig.4 Pauli-MPS bridge estimator.
#
# This is intentionally a gate, not a production plotter: it compares the
# compressed Pauli-MPS normalizer ratio and batched bridge samples against the
# ED/WHT exact c_L at small L.

using Printf
using JSON

include(joinpath(@__DIR__, "..", "..", "scripts", "tfim_fig4_paper_grade.jl"))
include(joinpath(@__DIR__, "pauli_mps_sampler.jl"))
include(joinpath(@__DIR__, "tfim_fig4_diagnose_eq24.jl"))

function exact_cL_from_wht(L::Int, h::Float64)
    _, psi_L = ed_groundstate(L, h; pbc=true)
    _, psi_H = ed_groundstate(L ÷ 2, h; pbc=true)
    abs4_L = pauli_abs4_table(psi_L, L)
    abs4_H = pauli_abs4_table(psi_H, L ÷ 2)
    return log(sum(abs4_L) / sum(abs4_H)^2)
end

function exact_cL_reference(L::Int, h::Float64)
    ref_env = strip(get(ENV, "FIG4_GATE_REFERENCE", ""))
    ref_path = !isempty(ref_env) ? ref_env :
        (L == 16 && isapprox(h, 0.80; atol=1e-12) ?
         joinpath(@__DIR__, "..", "..", "results", "tfim_fig4_paper_grade",
                  "trusted_reference_L16_h0.80.json") : "")
    if !isempty(ref_path) && isfile(ref_path)
        ref = JSON.parsefile(ref_path)
        return Float64(ref["cL_exact"])
    end
    return exact_cL_from_wht(L, h)
end

function main()
    L = parse(Int, get(ENV, "FIG4_GATE_L", "8"))
    h = parse(Float64, get(ENV, "FIG4_GATE_H", "0.80"))
    chi = parse(Int, get(ENV, "FIG4_GATE_CHI", "16"))
    pauli_chi = parse(Int, get(ENV, "FIG4_GATE_PAULI_CHI", "16"))
    pauli_chi_check = parse(Int, get(ENV, "FIG4_GATE_PAULI_CHI_CHECK", string(2 * pauli_chi)))
    n_samples = parse(Int, get(ENV, "FIG4_GATE_NSAMPLES", "0"))
    tol = parse(Float64, get(ENV, "FIG4_GATE_TOL", "0.05"))
    @assert iseven(L)

    @printf("Fig4 Pauli-MPS normalizer gate: L=%d h=%.3f chi=%d pauli_chi=%d→%d samples=%d\n",
            L, h, chi, pauli_chi, pauli_chi_check, n_samples)
    flush(stdout)

    exact = exact_cL_reference(L, h)
    @printf("  exact ED/WHT c_L = %+.8f\n", exact)
    flush(stdout)

    E_L, psi_L, sites_L = dmrg_groundstate(L, h, chi; nsweeps=20, pbc=true)
    E_H, psi_H, sites_H = dmrg_groundstate(L ÷ 2, h, chi; nsweeps=20, pbc=true)
    @printf("  DMRG energies: E_L=%.10f E_H=%.10f\n", E_L, E_H)
    flush(stdout)

    B_L_raw = pauli_mps_tensors(psi_L, sites_L)
    B_H_raw = pauli_mps_tensors(psi_H, sites_H)
    B_L_low, _ = compress_pauli_mps(B_L_raw, pauli_chi, 1e-12)
    B_H_low, _ = compress_pauli_mps(B_H_raw, pauli_chi, 1e-12)
    low_L = SquaredPauliMPSSampler(B_L_low)
    low_H = SquaredPauliMPSSampler(B_H_low)
    cL_low = log(pauli_squared_mps_norm(low_L) / pauli_squared_mps_norm(low_H)^2)
    B_L, trunc_L = compress_pauli_mps(B_L_raw, pauli_chi_check, 1e-12)
    B_H, trunc_H = compress_pauli_mps(B_H_raw, pauli_chi_check, 1e-12)
    sampler_L = SquaredPauliMPSSampler(B_L)
    sampler_H = SquaredPauliMPSSampler(B_H)
    cL_norm = log(pauli_squared_mps_norm(sampler_L) / pauli_squared_mps_norm(sampler_H)^2)
    cL_compression_error = abs(cL_norm - cL_low)
    @printf("  compressed norm c_L = %+.8f  exact_diff=%+.3e  χP_diff=%.3e  trunc=(%.3e, %.3e)\n",
            cL_norm, cL_norm - exact, cL_compression_error, trunc_L, trunc_H)
    flush(stdout)

    pass = abs(cL_norm - exact) <= tol && cL_compression_error <= tol
    if n_samples > 0
        bridge = pauli_mps_bridge_cL(B_L, B_H; n_samples=n_samples, seed=0xF164)
        @printf("  bridge sampled c_L  = %+.8f ± %.8f  diff=%+.3e\n",
                bridge.cL, bridge.se, bridge.cL - exact)
        pass &= abs(bridge.cL - exact) <= max(tol, 3 * bridge.se)
    else
        println("  bridge sampled c_L  = skipped (FIG4_GATE_NSAMPLES=0)")
    end
    println(pass ? "  verdict = PASS" : "  verdict = FAIL")
    pass || exit(1)
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
