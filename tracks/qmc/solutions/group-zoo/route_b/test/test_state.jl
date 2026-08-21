@testset "periodic kink parity and spin segments" begin
    state = WorldlineState(
        build_lattice(:honeycomb, 2),
        2.0;
        initial_spins=fill(Int8(1), 8),
    )
    @test validate_state(state)

    first = insert_kink!(state, 1, 0.75)
    @test kink_kind(state, first) == PairingKink
    @test !validate_state(state)

    second = insert_kink!(state, 1, 1.25)
    @test kink_kind(state, second) == PairingKink
    @test validate_state(state)
    @test spin_at(state, 1, 0.5) == 1
    @test spin_at(state, 1, 1.0) == -1
    @test spin_at(state, 1, 1.5) == 1

    delete_kink!(state, second)
    @test !validate_state(state)
    delete_kink!(state, first)
    @test validate_state(state)
end

@testset "hopping and pairing labels follow pre-kink spins" begin
    state = WorldlineState(
        build_lattice(:chain, 3),
        2.0;
        initial_spins=Int8[1, -1, 1],
    )
    first = insert_kink!(state, 1, 0.5)
    second = insert_kink!(state, 1, 1.5)
    @test kink_kind(state, first) == HoppingKink
    @test kink_kind(state, second) == HoppingKink
    @test validate_state(state)
end

@testset "defects and periodic segment flips preserve state invariants" begin
    state = WorldlineState(
        build_lattice(:chain, 3),
        2.0;
        initial_spins=fill(Int8(1), 3),
    )
    set_defects!(state, Defect(Ira, 1, 1.5), Defect(Masha, 1, 0.5))
    flip_periodic_segment!(state, 1, 1.5, 0.5)
    @test validate_state(state)
    @test spin_at(state, 1, 0.25) == -1
    @test spin_at(state, 1, 1.0) == 1
    @test spin_at(state, 1, 1.75) == -1

    flip_periodic_segment!(state, 1, 1.5, 0.5)
    clear_defects!(state)
    @test validate_state(state)
    @test all(spin_at(state, 1, tau) == 1 for tau in (0.25, 1.0, 1.75))
end

@testset "segment flips interchange incident kink labels" begin
    state = WorldlineState(
        build_lattice(:chain, 3),
        2.0;
        initial_spins=fill(Int8(1), 3),
    )
    inside = insert_kink!(state, 1, 0.75)
    outside = insert_kink!(state, 1, 1.25)
    @test validate_state(state)

    set_defects!(state, Defect(Ira, 1, 0.5), Defect(Masha, 1, 1.0))
    flip_periodic_segment!(state, 1, 0.5, 1.0)
    @test kink_kind(state, inside) == HoppingKink
    @test kink_kind(state, outside) == PairingKink
    @test validate_state(state)

    flip_periodic_segment!(state, 1, 0.5, 1.0)
    clear_defects!(state)
    @test kink_kind(state, inside) == PairingKink
    @test validate_state(state)
end

@testset "invalid state mutations are rejected" begin
    lattice = build_lattice(:chain, 3)
    @test_throws ArgumentError WorldlineState(
        lattice,
        0.0;
        initial_spins=fill(Int8(1), 3),
    )
    @test_throws ArgumentError WorldlineState(
        lattice,
        1.0;
        initial_spins=Int8[1, 0, -1],
    )

    state = WorldlineState(lattice, 1.0; initial_spins=fill(Int8(1), 3))
    @test_throws ArgumentError insert_kink!(state, 0, 0.5)
    @test_throws ArgumentError insert_kink!(state, 1, 1.0)
    @test_throws ArgumentError delete_kink!(state, 999)
    @test_throws ArgumentError set_defects!(
        state,
        Defect(Ira, 1, 0.2),
        Defect(Ira, 1, 0.8),
    )
end

@testset "seeded kink round trips preserve physical state" begin
    for lattice_name in (:chain, :honeycomb, :triangle)
        lattice = build_lattice(lattice_name, 3)
        state = WorldlineState(
            lattice,
            3.0;
            initial_spins=fill(Int8(1), lattice.nsites),
        )
        rng = CounterRNG(0x148)
        initial_spins = copy(state.base_spins)

        for _ in 1:1_000
            bond = rand_int!(rng, length(lattice.bonds))
            first_tau = 3rand_float!(rng)
            second_tau = 3rand_float!(rng)
            first_tau == second_tau && continue
            first = insert_kink!(state, bond, first_tau)
            second = insert_kink!(state, bond, second_tau)
            @test validate_state(state)
            delete_kink!(state, second)
            delete_kink!(state, first)
            @test validate_state(state)
            @test isempty(state.kinks)
            @test all(isempty, state.site_events)
            @test all(isempty, state.bond_events)
            @test state.base_spins == initial_spins
        end
    end
end
