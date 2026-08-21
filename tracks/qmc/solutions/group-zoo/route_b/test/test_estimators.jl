@testset "exact all-up observables" begin
    state = WorldlineState(
        build_lattice(:chain, 3),
        2.0;
        initial_spins=fill(Int8(1), 3),
    )
    obs = measure(state; h=3.0)
    @test obs.R_down == 0.0
    @test obs.I_wrap_any == 0
    @test obs.kink_count == 0
    @test obs.mz_rotated == 1.0
    @test obs.mx_original == 1.0
    @test obs.field_energy_per_site == -3.0
    @test obs.bond_energy_per_site == 0.0
    @test obs.total_energy_per_site == -3.0
    @test obs.m2 == 1.0
    @test obs.m4 == 1.0
end

@testset "closed winding and kink estimators" begin
    state = hopping_loop_state(build_lattice(:chain, 3), 1, [1, 2, 3])
    obs = measure(state; h=0.5)
    @test obs.R_down == 0.5
    @test obs.I_wrap_any == 1
    @test obs.kink_count == 3
    @test obs.bond_energy_per_site == -1.0
    @test isfinite(obs.total_energy_per_site)
    @test 0.0 <= obs.m2 <= 1.0
    @test 0.0 <= obs.m4 <= 1.0
end
