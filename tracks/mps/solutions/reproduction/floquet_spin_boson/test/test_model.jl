using Test

@testset "commensurate Floquet period grid" begin
    grid = period_grid(2.5, π / 60)
    @test grid.T == 2π / 2.5
    @test grid.M == 48
    @test grid.dt == grid.T / grid.M
    @test isapprox(grid.M * grid.dt, grid.T; atol=16eps(grid.T), rtol=0)

    @test_throws ArgumentError period_grid(0.0, π / 60)
    @test_throws ArgumentError period_grid(2.5, 0.0)
end

@testset "fixed transverse Fig. 2 physics" begin
    model = SpinBosonModel()
    @test model.coupling_operator == SIGMA_Z
    @test system_hamiltonian(model, 0.0) == 0.5 * SIGMA_X + SIGMA_Z
    @test drive_hamiltonian(SpinBosonModel(drive=:longitudinal), 0.0) == SIGMA_X
    @test_throws ArgumentError SpinBosonModel(drive=:diagonal)
end
