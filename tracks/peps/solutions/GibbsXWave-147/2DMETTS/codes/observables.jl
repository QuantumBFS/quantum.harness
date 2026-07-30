function expectation_insertions(
    state::DenseFinitePEPS,
    insertions::AbstractDict;
    chi::Integer,
    norm_value=nothing,
)
    normalization = norm_value === nothing ? boundary_mps_contract(state; chi).value : norm_value
    numerator = boundary_mps_contract(state; chi, insertions).value
    return numerator / normalization
end

function expectation_one_site(
    state::DenseFinitePEPS,
    operator::AbstractMatrix,
    site::CartesianIndex{2};
    chi::Integer,
    norm_value=nothing,
)
    return expectation_insertions(
        state,
        Dict{CartesianIndex{2},Any}(site => operator);
        chi,
        norm_value,
    )
end

function expectation_product_two_site(
    state::DenseFinitePEPS,
    operator1::AbstractMatrix,
    operator2::AbstractMatrix,
    site1::CartesianIndex{2},
    site2::CartesianIndex{2};
    chi::Integer,
    norm_value=nothing,
)
    site1 == site2 && throw(ArgumentError("two-site expectation requires distinct sites"))
    return expectation_insertions(
        state,
        Dict{CartesianIndex{2},Any}(site1 => operator1, site2 => operator2);
        chi,
        norm_value,
    )
end

function metts_observables(state::DenseFinitePEPS, para::AbstractDict; chi::Integer=para[:chi])
    norm_result = boundary_mps_contract(state; chi)
    normalization = norm_result.value
    zz_sum = 0.0
    bond_count = 0
    for y in 1:state.Ly, x in 1:(state.Lx - 1)
        zz_sum += real(expectation_product_two_site(
            state,
            Z,
            Z,
            CartesianIndex(x, y),
            CartesianIndex(x + 1, y);
            chi,
            norm_value=normalization,
        ))
        bond_count += 1
    end
    for x in 1:state.Lx, y in 1:(state.Ly - 1)
        zz_sum += real(expectation_product_two_site(
            state,
            Z,
            Z,
            CartesianIndex(x, y),
            CartesianIndex(x, y + 1);
            chi,
            norm_value=normalization,
        ))
        bond_count += 1
    end

    x_sum = 0.0
    z_sum = 0.0
    for y in 1:state.Ly, x in 1:state.Lx
        site = CartesianIndex(x, y)
        x_sum += real(expectation_one_site(state, X, site; chi, norm_value=normalization))
        z_sum += real(expectation_one_site(state, Z, site; chi, norm_value=normalization))
    end

    correlations = Float64[]
    if get(para, :measure_correlations, true)
        center = CartesianIndex(cld(state.Lx, 2), cld(state.Ly, 2))
        max_distance = state.Lx - center[1]
        for distance in 1:max_distance
            target = CartesianIndex(center[1] + distance, center[2])
            push!(correlations, real(expectation_product_two_site(
                state,
                Z,
                Z,
                center,
                target;
                chi,
                norm_value=normalization,
            )))
        end
    end

    site_count = state.Lx * state.Ly
    energy = -para[:J] * zz_sum - para[:h] * x_sum
    return (;
        energy,
        energy_per_site=energy / site_count,
        x_magnetization=x_sum / site_count,
        z_magnetization=z_sum / site_count,
        zz_nearest_neighbor=zz_sum / bond_count,
        correlations,
        norm=real(normalization),
        boundary_mps_truncation_error=norm_result.max_truncation_error,
    )
end
