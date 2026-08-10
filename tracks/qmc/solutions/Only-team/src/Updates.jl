mutable struct UpdateDiagnostics
    local_attempts::Int
    local_accepts::Int
    cluster_size_sum::Int
    cluster_count::Int
end

mutable struct SimulationState
    spins::Matrix{Int8}
    diagnostics::UpdateDiagnostics
end

function reset_diagnostics!(diagnostics::UpdateDiagnostics)::Nothing
    diagnostics.local_attempts = 0
    diagnostics.local_accepts = 0
    diagnostics.cluster_size_sum = 0
    diagnostics.cluster_count = 0
    return nothing
end

function initialize_state(
    config::SimulationConfig,
    lattice::Lattice,
    rng,
)::SimulationState
    spins = if config.initial_state === :ordered
        fill(Int8(1), lattice.N, config.LTrot)
    else
        random_spins = Matrix{Int8}(undef, lattice.N, config.LTrot)
        for index in eachindex(random_spins)
            random_spins[index] = rand(rng, Bool) ? Int8(1) : Int8(-1)
        end
        random_spins
    end

    diagnostics = UpdateDiagnostics(0, 0, 0, 0)
    return SimulationState(spins, diagnostics)
end

function local_sweep!(
    state::SimulationState,
    lattice::Lattice,
    config::SimulationConfig,
    rng,
)::Nothing
    for tau in 1:config.LTrot
        for site in 1:lattice.N
            IsSpin, Rtp0 =
                local_terms(state.spins, site, tau, lattice, config)
            delta_log_weight = -2 * IsSpin * Rtp0

            state.diagnostics.local_attempts += 1
            if delta_log_weight >= 0 ||
               rand(rng) < exp(delta_log_weight)
                state.spins[site, tau] = -IsSpin
                state.diagnostics.local_accepts += 1
            end
        end
    end
    return nothing
end

@inline function should_add(
    candidate_spin::Int8,
    cluster_spin::Int8,
    visited::Bool,
    probability::Float64,
    uniform_draw::Float64,
)::Bool
    return !visited &&
           candidate_spin == cluster_spin &&
           uniform_draw < probability
end

function build_cluster(
    state::SimulationState,
    lattice::Lattice,
    config::SimulationConfig,
    rng,
)::Vector{Int}
    seed_index = rand(rng, 1:length(state.spins))
    cluster_spin = state.spins[seed_index]
    visited = falses(size(state.spins))
    visited[seed_index] = true
    stack = Int[seed_index]
    members = Int[seed_index]

    while !isempty(stack)
        current_index = pop!(stack)
        site = mod1(current_index, lattice.N)
        tau = fld(current_index - 1, lattice.N) + 1

        for neighbor in lattice.neighbors[site]
            candidate_index = neighbor + (tau - 1) * lattice.N
            if !visited[candidate_index] &&
               state.spins[candidate_index] == cluster_spin &&
               should_add(
                   state.spins[candidate_index],
                   cluster_spin,
                   false,
                   config.p_space,
                   rand(rng),
               )
                visited[candidate_index] = true
                push!(stack, candidate_index)
                push!(members, candidate_index)
            end
        end

        for tau_neighbor in (
            tau_minus(tau, config.LTrot),
            tau_plus(tau, config.LTrot),
        )
            candidate_index = site + (tau_neighbor - 1) * lattice.N
            if !visited[candidate_index] &&
               state.spins[candidate_index] == cluster_spin &&
               should_add(
                   state.spins[candidate_index],
                   cluster_spin,
                   false,
                   config.p_tau,
                   rand(rng),
               )
                visited[candidate_index] = true
                push!(stack, candidate_index)
                push!(members, candidate_index)
            end
        end
    end

    return members
end

function wolff_update!(
    state::SimulationState,
    lattice::Lattice,
    config::SimulationConfig,
    rng,
)::Int
    members = build_cluster(state, lattice, config, rng)
    for index in members
        state.spins[index] = -state.spins[index]
    end

    cluster_size = length(members)
    state.diagnostics.cluster_size_sum += cluster_size
    state.diagnostics.cluster_count += 1
    return cluster_size
end

function update_cycle!(
    state::SimulationState,
    lattice::Lattice,
    config::SimulationConfig,
    rng,
)::Nothing
    for _ in 1:config.nLocal
        local_sweep!(state, lattice, config, rng)
    end
    for _ in 1:config.nWolff
        wolff_update!(state, lattice, config, rng)
    end
    return nothing
end
