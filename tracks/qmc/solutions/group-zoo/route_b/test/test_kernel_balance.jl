@testset "kernel family selection uses frozen probabilities" begin
    parameters = baseline_worm_parameters()
    @test select_family(false, 0.99, parameters) == CreateDefects
    @test select_family(true, 0.00, parameters) == AnnihilateDefects
    @test select_family(true, 0.25, parameters) == MoveDefect
    @test select_family(true, 0.50, parameters) == InsertKink
    @test select_family(true, 0.75, parameters) == DeleteKink
    @test select_family(true, prevfloat(1.0), parameters) == DeleteKink
end

@testset "seeded kernels preserve invariants and explore update families" begin
    for name in (:chain, :honeycomb, :triangle)
        state = closed_update_fixture(name)
        kernel = WormKernel(
            state,
            CounterRNG(0x148),
            1.0,
            0.3,
            baseline_worm_parameters(),
        )
        sectors = Set{Symbol}()
        kinds = Set{KinkKind}()
        for _ in 1:100_000
            step!(kernel; debug=true)
            push!(sectors, isempty(state.defects) ? :Z : :G)
            union!(kinds, (kink.kind for kink in values(state.kinks)))
        end
        @test sectors == Set((:Z, :G))
        @test HoppingKink in kinds
        @test PairingKink in kinds
        @test all(get(kernel.proposed, family, 0) > 0 for family in instances(ProposalFamily))
        @test all(get(kernel.accepted, family, 0) > 0 for family in instances(ProposalFamily))
        @test validate_state(state)
    end
end
