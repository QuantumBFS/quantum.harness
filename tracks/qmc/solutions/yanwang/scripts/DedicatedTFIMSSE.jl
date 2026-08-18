module DedicatedTFIMSSE

using Carlo
using HDF5
using Random

const OP_IDENTITY = Int8(0)
const OP_BOND = Int8(1)
const OP_FIELD_CONSTANT = Int8(2)
const OP_FIELD_FLIP = Int8(3)

function lattice_edges(lattice_name::AbstractString, L::Integer)
    L >= 2 || throw(ArgumentError("L must be at least 2"))
    if lattice_name == "honeycomb"
        honey_site(x, y, sublattice) =
            1 + sublattice + 2 * (mod(x, L) + L * mod(y, L))
        edges = Tuple{Int,Int}[]
        for y in 0:L-1, x in 0:L-1
            push!(edges, (honey_site(x, y, 0), honey_site(x, y, 1)))
            push!(edges, (honey_site(x, y, 1), honey_site(x, y + 1, 0)))
            push!(edges, (honey_site(x, y, 1), honey_site(x + 1, y, 0)))
        end
        return 2 * L * L, edges, 3
    elseif lattice_name == "triangular"
        tri_site(x, y) = 1 + mod(x, L) + L * mod(y, L)
        edges = Tuple{Int,Int}[]
        for y in 0:L-1, x in 0:L-1
            push!(edges, (tri_site(x, y), tri_site(x, y + 1)))
            push!(edges, (tri_site(x, y), tri_site(x + 1, y)))
            push!(edges, (tri_site(x, y), tri_site(x + 1, y + 1)))
        end
        return L * L, edges, 6
    end
    throw(ArgumentError("unsupported lattice: $lattice_name"))
end

mutable struct MC <: AbstractMC
    T::Float64
    J::Float64
    h::Float64
    n_sites::Int
    edges::Vector{Tuple{Int,Int}}
    coordination::Int
    string_length::Int
    kinds::Vector{Int8}
    indices::Vector{Int32}
    spins::Vector{Int8}
    expansion_order::Int
    state_buffer::Vector{Int8}
    leg_spin_buffer::Vector{Int8}
    parent_buffer::Vector{Int}
    component_size_buffer::Vector{Int}
    vertex_legs_buffer::Vector{NTuple{4,Int}}
    first_in_buffer::Vector{Int}
    last_out_buffer::Vector{Int}
    flip_component_buffer::Vector{Int8}
    flip_epoch_buffer::Vector{Int}
    flip_generation::Int
end

function MC(params::AbstractDict)
    lattice_name = String(params[:lattice_name])
    L = Int(params[:L])
    n_sites, edges, coordination = lattice_edges(lattice_name, L)
    T = Float64(params[:T])
    J = Float64(params[:J])
    h = Float64(params[:h])
    string_length = Int(get(params, :string_length, 256))
    T > 0 || throw(ArgumentError("T must be positive"))
    J > 0 || throw(ArgumentError("J must be positive"))
    h > 0 || throw(ArgumentError("h must be positive"))
    string_length > 0 || throw(ArgumentError("string_length must be positive"))
    maximum_legs = 4 * string_length
    return MC(
        T,
        J,
        h,
        n_sites,
        edges,
        coordination,
        string_length,
        fill(OP_IDENTITY, string_length),
        zeros(Int32, string_length),
        ones(Int8, n_sites),
        0,
        Vector{Int8}(undef, n_sites),
        Vector{Int8}(undef, maximum_legs),
        Vector{Int}(undef, maximum_legs),
        Vector{Int}(undef, maximum_legs),
        Vector{NTuple{4,Int}}(undef, string_length),
        Vector{Int}(undef, n_sites),
        Vector{Int}(undef, n_sites),
        Vector{Int8}(undef, maximum_legs),
        zeros(Int, maximum_legs),
        0,
    )
end

function Carlo.init!(mc::MC, ctx::MCContext, ::AbstractDict)
    mc.kinds .= OP_IDENTITY
    mc.indices .= 0
    mc.spins .= ifelse.(rand(ctx.rng, Bool, mc.n_sites), Int8(1), Int8(-1))
    mc.expansion_order = 0
    return nothing
end

@inline function candidate_weight(mc::MC)
    return mc.n_sites * mc.h + 2 * mc.J * length(mc.edges)
end

function diagonal_update!(mc::MC, rng::AbstractRNG)
    beta = 1 / mc.T
    total_weight = candidate_weight(mc)
    state = mc.state_buffer
    copyto!(state, mc.spins)
    n = mc.expansion_order
    M = mc.string_length

    @inbounds for position in eachindex(mc.kinds)
        kind = mc.kinds[position]
        if kind == OP_IDENTITY
            insertion_probability = min(1.0, beta * total_weight / (M - n))
            if rand(rng) < insertion_probability
                draw = rand(rng) * total_weight
                if draw < mc.n_sites * mc.h
                    site = rand(rng, 1:mc.n_sites)
                    mc.kinds[position] = OP_FIELD_CONSTANT
                    mc.indices[position] = site
                    n += 1
                else
                    bond = rand(rng, eachindex(mc.edges))
                    first, second = mc.edges[bond]
                    if state[first] == state[second]
                        mc.kinds[position] = OP_BOND
                        mc.indices[position] = bond
                        n += 1
                    end
                end
            end
        elseif kind == OP_BOND || kind == OP_FIELD_CONSTANT
            removal_probability = min(1.0, (M - n + 1) / (beta * total_weight))
            if rand(rng) < removal_probability
                mc.kinds[position] = OP_IDENTITY
                mc.indices[position] = 0
                n -= 1
            end
        elseif kind == OP_FIELD_FLIP
            site = Int(mc.indices[position])
            state[site] = -state[site]
        else
            error("invalid operator kind $kind")
        end
    end
    state == mc.spins || error("operator string violates imaginary-time periodicity")
    mc.expansion_order = n
    return nothing
end

@inline function find_root!(parent, item)
    @inbounds begin
        root = item
        while parent[root] != root
            root = parent[root]
        end
        while parent[item] != item
            next = parent[item]
            parent[item] = root
            item = next
        end
        return root
    end
end

@inline function union!(parent, size, first, second)
    root_first = find_root!(parent, first)
    root_second = find_root!(parent, second)
    root_first == root_second && return root_first
    @inbounds begin
        if size[root_first] < size[root_second]
            root_first, root_second = root_second, root_first
        end
        parent[root_second] = root_first
        size[root_first] += size[root_second]
    end
    return root_first
end

@inline function new_leg!(
    leg_spin,
    parent,
    component_size,
    leg_count,
    spin,
)
    @inbounds begin
        leg_count += 1
        leg_spin[leg_count] = spin
        parent[leg_count] = leg_count
        component_size[leg_count] = 1
    end
    return leg_count
end

@inline function site_pair!(
    state,
    first_in,
    last_out,
    leg_spin,
    parent,
    component_size,
    leg_count,
    site,
    out_spin,
)
    @inbounds begin
        leg_count = new_leg!(
            leg_spin,
            parent,
            component_size,
            leg_count,
            state[site],
        )
        incoming = leg_count
        if last_out[site] == 0
            first_in[site] = incoming
        else
            union!(parent, component_size, last_out[site], incoming)
        end
        leg_count = new_leg!(
            leg_spin,
            parent,
            component_size,
            leg_count,
            out_spin,
        )
        outgoing = leg_count
        last_out[site] = outgoing
        return incoming, outgoing, leg_count
    end
end

function cluster_update!(mc::MC, rng::AbstractRNG)
    if mc.expansion_order == 0
        @inbounds for site in eachindex(mc.spins)
            rand(rng, Bool) && (mc.spins[site] = -mc.spins[site])
        end
        return nothing
    end

    leg_spin = mc.leg_spin_buffer
    parent = mc.parent_buffer
    component_size = mc.component_size_buffer
    vertex_legs = mc.vertex_legs_buffer
    first_in = mc.first_in_buffer
    last_out = mc.last_out_buffer
    flip_component = mc.flip_component_buffer
    flip_epoch = mc.flip_epoch_buffer
    fill!(first_in, 0)
    fill!(last_out, 0)
    state = mc.state_buffer
    copyto!(state, mc.spins)
    leg_count = 0

    @inbounds for position in eachindex(mc.kinds)
        kind = mc.kinds[position]
        kind == OP_IDENTITY && continue
        if kind == OP_BOND
            first, second = mc.edges[Int(mc.indices[position])]
            first_in_leg, first_out_leg, leg_count = site_pair!(
                state,
                first_in,
                last_out,
                leg_spin,
                parent,
                component_size,
                leg_count,
                first,
                state[first],
            )
            second_in_leg, second_out_leg, leg_count = site_pair!(
                state,
                first_in,
                last_out,
                leg_spin,
                parent,
                component_size,
                leg_count,
                second,
                state[second],
            )
            legs = (first_in_leg, second_in_leg, first_out_leg, second_out_leg)
            vertex_legs[position] = legs
            union!(parent, component_size, legs[1], legs[2])
            union!(parent, component_size, legs[1], legs[3])
            union!(parent, component_size, legs[1], legs[4])
        else
            site = Int(mc.indices[position])
            out_spin = kind == OP_FIELD_FLIP ? Int8(-state[site]) : state[site]
            incoming, outgoing, leg_count = site_pair!(
                state,
                first_in,
                last_out,
                leg_spin,
                parent,
                component_size,
                leg_count,
                site,
                out_spin,
            )
            vertex_legs[position] = (incoming, outgoing, 0, 0)
            state[site] = out_spin
        end
    end
    state == mc.spins || error("operator string violates imaginary-time periodicity")

    @inbounds for site in 1:mc.n_sites
        if first_in[site] != 0
            union!(parent, component_size, last_out[site], first_in[site])
        end
    end

    if mc.flip_generation == typemax(Int)
        fill!(flip_epoch, 0)
        mc.flip_generation = 1
    else
        mc.flip_generation += 1
    end
    generation = mc.flip_generation
    @inbounds for leg in 1:leg_count
        root = find_root!(parent, leg)
        if flip_epoch[root] != generation
            flip_epoch[root] = generation
            flip_component[root] = rand(rng, Bool) ? Int8(2) : Int8(1)
        end
        flip_component[root] == 2 && (leg_spin[leg] = -leg_spin[leg])
    end

    @inbounds for position in eachindex(mc.kinds)
        kind = mc.kinds[position]
        kind == OP_IDENTITY && continue
        legs = vertex_legs[position]
        if kind == OP_BOND
            leg_spin[legs[1]] == leg_spin[legs[3]] ||
                error("bond worldline mismatch")
            leg_spin[legs[2]] == leg_spin[legs[4]] ||
                error("bond worldline mismatch")
            leg_spin[legs[1]] == leg_spin[legs[2]] ||
                error("forbidden ferromagnetic bond state")
        else
            mc.kinds[position] =
                leg_spin[legs[1]] == leg_spin[legs[2]] ? OP_FIELD_CONSTANT :
                OP_FIELD_FLIP
        end
    end

    @inbounds for site in 1:mc.n_sites
        if first_in[site] == 0
            rand(rng, Bool) && (mc.spins[site] = -mc.spins[site])
        else
            mc.spins[site] = leg_spin[first_in[site]]
        end
    end
    return nothing
end

function Carlo.sweep!(mc::MC, ctx::MCContext)
    diagonal_update!(mc, ctx.rng)
    cluster_update!(mc, ctx.rng)
    return nothing
end

function propagated_moments(mc::MC)
    state = mc.state_buffer
    copyto!(state, mc.spins)
    magnetization_sum = sum(state)
    m2_sum = 0.0
    m4_sum = 0.0
    @inbounds for position in eachindex(mc.kinds)
        m = magnetization_sum / mc.n_sites
        m2 = m * m
        m2_sum += m2
        m4_sum += m2 * m2
        if mc.kinds[position] == OP_FIELD_FLIP
            site = Int(mc.indices[position])
            old_spin = state[site]
            state[site] = -old_spin
            magnetization_sum -= 2 * old_spin
        end
    end
    state == mc.spins || error("measurement propagation is not periodic")
    return m2_sum / mc.string_length, m4_sum / mc.string_length
end

function dirichlet_time_average_moments(magnetizations::AbstractVector)
    isempty(magnetizations) &&
        throw(ArgumentError("at least one time interval is required"))
    p1 = sum(magnetizations)
    p2 = sum(value -> value^2, magnetizations)
    p3 = sum(value -> value^3, magnetizations)
    p4 = sum(value -> value^4, magnetizations)
    K = length(magnetizations)
    K_float = Float64(K)
    denominator2 = K_float * (K_float + 1)
    denominator4 =
        denominator2 * (K_float + 2) * (K_float + 3)
    m2 = (p1^2 + p2) / denominator2
    m4 = (
        p1^4 +
        6 * p1^2 * p2 +
        3 * p2^2 +
        8 * p1 * p3 +
        6 * p4
    ) / denominator4
    return m2, m4
end

function spacetime_moments(mc::MC)
    state = mc.state_buffer
    copyto!(state, mc.spins)
    magnetization_sum = sum(state)
    m = magnetization_sum / mc.n_sites
    p1 = Float64(m)
    p2 = Float64(m^2)
    p3 = Float64(m^3)
    p4 = Float64(m^4)
    interval_count = 1
    observed_order = 0

    @inbounds for position in eachindex(mc.kinds)
        kind = mc.kinds[position]
        kind == OP_IDENTITY && continue
        observed_order += 1
        if kind == OP_FIELD_FLIP
            site = Int(mc.indices[position])
            old_spin = state[site]
            state[site] = -old_spin
            magnetization_sum -= 2 * old_spin
        end
        m = magnetization_sum / mc.n_sites
        p1 += m
        p2 += m^2
        p3 += m^3
        p4 += m^4
        interval_count += 1
    end

    observed_order == mc.expansion_order ||
        error("expansion-order mismatch during spacetime measurement")
    state == mc.spins ||
        error("spacetime measurement propagation is not periodic")
    interval_count_float = Float64(interval_count)
    denominator2 =
        interval_count_float * (interval_count_float + 1)
    denominator4 =
        denominator2 *
        (interval_count_float + 2) *
        (interval_count_float + 3)
    m2 = (p1^2 + p2) / denominator2
    m4 = (
        p1^4 +
        6 * p1^2 * p2 +
        3 * p2^2 +
        8 * p1 * p3 +
        6 * p4
    ) / denominator4
    return m2, m4
end

function combined_observables(mc::MC)
    state = mc.state_buffer
    copyto!(state, mc.spins)
    magnetization_sum = sum(state)
    initial_m = magnetization_sum / mc.n_sites
    propagated_m2_sum = 0.0
    propagated_m4_sum = 0.0
    p1 = Float64(initial_m)
    p2 = Float64(initial_m^2)
    p3 = Float64(initial_m^3)
    p4 = Float64(initial_m^4)
    interval_count = 1
    observed_order = 0
    field_flips = 0
    field_constants = 0
    bond_operators = 0

    @inbounds for position in eachindex(mc.kinds)
        m = magnetization_sum / mc.n_sites
        m2 = m * m
        propagated_m2_sum += m2
        propagated_m4_sum += m2 * m2

        kind = mc.kinds[position]
        if kind == OP_IDENTITY
            continue
        elseif kind == OP_FIELD_FLIP
            field_flips += 1
            site = Int(mc.indices[position])
            old_spin = state[site]
            state[site] = -old_spin
            magnetization_sum -= 2 * old_spin
        elseif kind == OP_FIELD_CONSTANT
            field_constants += 1
        elseif kind == OP_BOND
            bond_operators += 1
        else
            error("invalid operator kind $kind")
        end
        observed_order += 1
        m = magnetization_sum / mc.n_sites
        p1 += m
        p2 += m^2
        p3 += m^3
        p4 += m^4
        interval_count += 1
    end

    observed_order == mc.expansion_order ||
        error("expansion-order mismatch during combined measurement")
    state == mc.spins ||
        error("combined measurement propagation is not periodic")
    interval_count_float = Float64(interval_count)
    denominator2 =
        interval_count_float * (interval_count_float + 1)
    denominator4 =
        denominator2 *
        (interval_count_float + 2) *
        (interval_count_float + 3)
    spacetime_m2 = (p1^2 + p2) / denominator2
    spacetime_m4 = (
        p1^4 +
        6 * p1^2 * p2 +
        3 * p2^2 +
        8 * p1 * p3 +
        6 * p4
    ) / denominator4
    return (
        propagated_m2_sum / mc.string_length,
        propagated_m4_sum / mc.string_length,
        spacetime_m2,
        spacetime_m4,
        field_flips,
        field_constants,
        bond_operators,
    )
end

function Carlo.measure!(mc::MC, ctx::MCContext)
    beta = 1 / mc.T
    physical_energy =
        (-mc.expansion_order / beta + mc.h * mc.n_sites + mc.J * length(mc.edges)) /
        mc.n_sites
    (
        m2,
        m4,
        spacetime_m2,
        spacetime_m4,
        field_flips,
        field_constants,
        bond_operators,
    ) = combined_observables(mc)
    measure!(ctx, :Sign, 1.0)
    measure!(ctx, :Energy, physical_energy)
    measure!(ctx, :Mag2, m2)
    measure!(ctx, :Mag4, m4)
    measure!(ctx, :SpaceTimeMag2, spacetime_m2)
    measure!(ctx, :SpaceTimeMag4, spacetime_m4)
    measure!(ctx, :ExpansionOrder, float(mc.expansion_order))
    measure!(ctx, :FieldFlipCount, float(field_flips))
    measure!(ctx, :FieldConstantCount, float(field_constants))
    measure!(ctx, :BondOperatorCount, float(bond_operators))
    measure!(ctx, :StringFillFraction, mc.expansion_order / mc.string_length)
    return nothing
end

function Carlo.register_evaluables(::Type{MC}, eval::AbstractEvaluator, ::AbstractDict)
    evaluate!(eval, :BinderRatio, (:Mag2, :Mag4)) do m2, m4
        return m2^2 / m4
    end
    evaluate!(
        eval,
        :SpaceTimeBinderRatio,
        (:SpaceTimeMag2, :SpaceTimeMag4),
    ) do m2, m4
        return m2^2 / m4
    end
    return nothing
end

function Carlo.write_checkpoint(mc::MC, out::HDF5.Group)
    out["kinds"] = mc.kinds
    out["indices"] = mc.indices
    out["spins"] = mc.spins
    out["expansion_order"] = mc.expansion_order
    return nothing
end

function Carlo.read_checkpoint!(mc::MC, input::HDF5.Group)
    mc.kinds .= read(input, "kinds")
    mc.indices .= read(input, "indices")
    mc.spins .= read(input, "spins")
    mc.expansion_order = Int(read(input, "expansion_order"))
    return nothing
end

end
