function physical_state_snapshot(state::WorldlineState)
    kinks = sort([
        (kink.bond, kink.tau, UInt8(kink.kind)) for kink in values(state.kinks)
    ])
    defects = sort([
        (UInt8(defect.role), defect.site, defect.tau) for defect in state.defects
    ])
    return (
        base_spins=copy(state.base_spins),
        kinks=kinks,
        site_events=[sort([state.kinks[id].tau for id in ids]) for ids in state.site_events],
        bond_events=[sort([state.kinks[id].tau for id in ids]) for ids in state.bond_events],
        defects=defects,
    )
end

baseline_worm_parameters() = WormParameters(0.25, 0.25, 0.25, 1.0, 1.0, 1.0)

function closed_update_fixture(name::Symbol=:chain)
    lattice = build_lattice(name, 3)
    return WorldlineState(
        lattice,
        2.0;
        initial_spins=fill(Int8(1), lattice.nsites),
    )
end

function open_update_fixture(name::Symbol=:chain)
    state = closed_update_fixture(name)
    proposal = propose_create(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        site=1,
        tau_i=0.4,
        delta=0.4,
        uniform=0.0,
    )
    apply_proposal!(state, proposal)
    @assert validate_state(state)
    return state
end

@testset "create and annihilate are exact state reverses" begin
    state = closed_update_fixture()
    before = physical_state_snapshot(state)
    create = propose_create(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        site=1,
        tau_i=0.4,
        delta=0.4,
        uniform=0.0,
    )
    @test create.record.family == CreateDefects
    @test create.record.accepted
    apply_proposal!(state, create)
    @test validate_state(state)
    @test length(state.defects) == 2

    annihilate = propose_annihilate(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        uniform=0.0,
    )
    @test annihilate.record.family == AnnihilateDefects
    @test create.record.log_acceptance_ratio ≈
          -annihilate.record.log_acceptance_ratio atol=5e-13 rtol=0
    apply_proposal!(state, annihilate)
    @test validate_state(state)
    @test physical_state_snapshot(state) == before
end

@testset "temporal defect moves reverse exactly" begin
    state = open_update_fixture()
    before = physical_state_snapshot(state)
    forward = propose_move(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        delta=0.2,
        uniform=0.0,
    )
    apply_proposal!(state, forward)
    @test validate_state(state)
    reverse = propose_move(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        delta=-0.2,
        uniform=0.0,
    )
    @test forward.record.log_acceptance_ratio ≈
          -reverse.record.log_acceptance_ratio atol=5e-13 rtol=0
    apply_proposal!(state, reverse)
    @test validate_state(state)
    @test physical_state_snapshot(state) == before
end

@testset "kink insertion and deletion reverse exactly" begin
    state = open_update_fixture()
    before = physical_state_snapshot(state)
    insertion = propose_insert(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        bond=1,
        delta=0.2,
        uniform=0.0,
    )
    apply_proposal!(state, insertion)
    @test validate_state(state)
    @test length(state.kinks) == 1
    inserted_id = only(keys(state.kinks))

    deletion = propose_delete(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        bond=1,
        kink_id=inserted_id,
        uniform=0.0,
    )
    @test insertion.record.log_acceptance_ratio ≈
          -deletion.record.log_acceptance_ratio atol=5e-13 rtol=0
    apply_proposal!(state, deletion)
    @test validate_state(state)
    @test physical_state_snapshot(state) == before
end

@testset "rejected and illegal proposals do not mutate state" begin
    state = closed_update_fixture()
    before = physical_state_snapshot(state)
    rejected = propose_create(
        state,
        baseline_worm_parameters();
        J=1.0,
        h=10.0,
        site=1,
        tau_i=0.4,
        delta=0.4,
        uniform=0.999999,
    )
    @test !rejected.record.accepted
    apply_proposal!(state, rejected)
    @test physical_state_snapshot(state) == before

    open_state = open_update_fixture()
    open_before = physical_state_snapshot(open_state)
    illegal = propose_delete(
        open_state,
        baseline_worm_parameters();
        J=1.0,
        h=0.3,
        bond=1,
        kink_id=nothing,
        uniform=0.0,
    )
    @test illegal isa IllegalProposal
    apply_proposal!(open_state, illegal)
    @test physical_state_snapshot(open_state) == open_before
end
