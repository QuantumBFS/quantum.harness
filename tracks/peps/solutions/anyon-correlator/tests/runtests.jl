# M1 acceptance testset — re-runnable in seconds, no CSV output.
# Gates G1–G6 are defined in scripts/ed_checks.jl (acceptance_gates()); see PLAN.md §6 M1.
# Usage: julia --project=julia-env tracks/peps/solutions/anyon-correlator/tests/runtests.jl

using Test

include(joinpath(@__DIR__, "..", "scripts", "ed_checks.jl"))

@testset "M1 — toric-code Hamiltonian, 2×2 ED" begin
    for g in acceptance_gates()
        @test g.passed
        println(@sprintf("[%s] %s — %s", g.passed ? "PASS" : "FAIL", g.gate, g.detail))
        flush(stdout)
    end
end
