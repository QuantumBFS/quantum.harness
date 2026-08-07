# Normalization probe: what does expectation_value(peps, H, env) return
# for the (2,2) composite-site cell on the exact state?
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf

ψ = exact_peps()
env, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, envspace(16)), ψ;
                          tol = 1e-9, maxiter = 300, verbosity = 0)
lat = fill(PSPACE, 2, 2)

# per-term expectations: 4 stars + 4 plaquettes, term op = −stabilizer
s_op, p_op = star_op(), plaq_op()
star_vals = ComplexF64[]
plaq_vals = ComplexF64[]
for r in 1:2, c in 1:2
    Hs = empty_localoperator(lat)
    PEPSKit.add_term!(Hs, [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)], s_op)
    push!(star_vals, expectation_value(ψ, Hs, env))
    Hp = empty_localoperator(lat)
    PEPSKit.add_term!(Hp, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)], p_op)
    push!(plaq_vals, expectation_value(ψ, Hp, env))
end
println("star term values (term = −A):  ", join([@sprintf("%+.6f", real(v)) for v in star_vals], " "))
println("plaquette term values (term = −B): ", join([@sprintf("%+.6f", real(v)) for v in plaq_vals], " "))
E_terms_sum = sum(star_vals) + sum(plaq_vals)

H0, table = toric_code_hamiltonian(0.0, 0.0)
println("term count in H0: ", length(H0.terms), " (stars ",
        count(t -> t.kind == :star, table), ", plaquettes ",
        count(t -> t.kind == :plaquette, table), ", fields ",
        count(t -> t.kind == :field, table), ")")
E_raw = expectation_value(ψ, H0, env)
@printf("raw expectation_value(H0)      = %+.12f\n", real(E_raw))
@printf("sum of single-term evaluations = %+.12f\n", real(E_terms_sum))
@printf("E_cell (raw)                   = %+.12f\n", real(E_raw))
@printf("E / composite site (raw / 4)   = %+.12f\n", real(E_raw) / 4)
@printf("E / edge spin (raw / 8)        = %+.12f\n", real(E_raw) / 8)
