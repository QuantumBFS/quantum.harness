function hopping_loop_state(
    lattice::Lattice,
    initial_down_site::Int,
    bond_sequence::Vector{Int},
)
    spins = fill(Int8(1), lattice.nsites)
    spins[initial_down_site] = -1
    state = WorldlineState(lattice, 1.0; initial_spins=spins)
    for (index, bond) in enumerate(bond_sequence)
        id = insert_kink!(state, bond, index / (length(bond_sequence) + 1))
        @assert kink_kind(state, id) == HoppingKink
    end
    @assert validate_state(state)
    return state
end

@testset "contractible and signed chain windings" begin
    lattice = build_lattice(:chain, 3)
    contractible = WorldlineState(
        lattice,
        1.0;
        initial_spins=Int8[-1, 1, 1],
    )
    @test winding_vectors(contractible) == [(0, 0)]

    forward = hopping_loop_state(lattice, 1, [1, 2, 3])
    reverse = hopping_loop_state(lattice, 1, [3, 2, 1])
    @test winding_vectors(forward) == [(1, 0)]
    @test winding_vectors(reverse) == [(-1, 0)]
end

@testset "triangular and honeycomb primitive-cell windings" begin
    triangle = hopping_loop_state(build_lattice(:triangle, 3), 1, [1, 4, 7])
    @test winding_vectors(triangle) == [(1, 0)]
    triangle_wrap = wrapping_observables(triangle)
    @test (triangle_wrap.I_wrap_1, triangle_wrap.I_wrap_2) == (1, 0)
    @test triangle_wrap.I_wrap_any == 1
    @test triangle_wrap.R_down == 0.5
    @test triangle_wrap.signed_winding == (1, 0)

    honeycomb = hopping_loop_state(
        build_lattice(:honeycomb, 3),
        1,
        [2, 7, 8, 4, 5, 1],
    )
    @test winding_vectors(honeycomb) == [(-1, 0)]
    honeycomb_wrap = wrapping_observables(honeycomb)
    @test honeycomb_wrap.I_wrap_any == 1
    @test honeycomb_wrap.loop_count == 1
end

@testset "winding requires a closed valid sector" begin
    state = hopping_loop_state(build_lattice(:chain, 3), 1, [1, 2, 3])
    set_defects!(state, Defect(Ira, 1, 0.05), Defect(Masha, 1, 0.95))
    @test_throws ArgumentError winding_vectors(state)

    invalid = WorldlineState(
        build_lattice(:chain, 3),
        1.0;
        initial_spins=fill(Int8(1), 3),
    )
    insert_kink!(invalid, 1, 0.5)
    @test_throws ArgumentError winding_vectors(invalid)
end

@testset "winding is deterministic on sampled closed sectors" begin
    for name in (:chain, :honeycomb, :triangle)
        lattice = build_lattice(name, 3)
        state = WorldlineState(
            lattice,
            2.0;
            initial_spins=fill(Int8(1), lattice.nsites),
        )
        kernel = WormKernel(
            state,
            CounterRNG(0x149),
            1.0,
            0.3,
            WormParameters(0.25, 0.25, 0.25, 1.0, 1.0, 1.0),
        )
        closed_samples = 0
        steps = 0
        while closed_samples < 10_000 && steps < 1_000_000
            step!(kernel; debug=true)
            steps += 1
            isempty(state.defects) || continue
            first = winding_vectors(state)
            @test winding_vectors(state) == first
            @test all(winding isa Tuple{Int,Int} for winding in first)
            closed_samples += 1
        end
        @test closed_samples == 10_000
    end
end

@testset "primitive-cell origin shifts retain winding" begin
    lattice = build_lattice(:triangle, 3)
    base_origin = hopping_loop_state(lattice, 1, [1, 4, 7])
    shifted_origin = hopping_loop_state(lattice, 4, [10, 13, 16])
    @test winding_vectors(base_origin) == winding_vectors(shifted_origin) == [(1, 0)]
end
