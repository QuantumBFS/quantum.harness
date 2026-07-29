module SquareGapConic

using JuMP
using LinearAlgebra
using SHA
using ..SquareJ1J2Prototype: PauliWord, enumerate_pauli_words, multiply_words
using ..GenericGapModel:
    GapProblem,
    BasisManifest,
    StateMonomial,
    NoStateSymmetry,
    basis_manifest,
    validate_basis_manifest,
    instantiate_terms,
    assembly_plan,
    canonical_word_string
using ..CoreMGK:
    CoreMGKPlan,
    ExactPairWiring,
    ExactComponent,
    ExactRowCoefficient,
    GammaAffineCoefficient,
    GaussianRational,
    ScalarMoment,
    a_gamma_coefficients,
    core_mgk_pair,
    core_mgk_plan,
    positive_pair_components,
    gap_pair_components,
    scalar_moment_string,
    commutator_polynomial,
    scalarize,
    add_coefficient!
using ..SquareSymmetryD4: apply_site_perm
using ..SquareSymmetryBlock:
    D4SymmetryBasis

export ConicStationaritySpec,
       ConicAssembly,
       ConicJuMPModel,
       D4ConicJuMPModel,
       D4MomentQuotient,
       d4_moment_quotient,
       stationarity_candidates_conic,
       canonical_stationarity_equalities_conic,
       assemble_square_conic,
       build_square_conic_jump,
       build_square_d4_conic_jump,
       square_conic_moment_degree

const BigRational = Rational{BigInt}
const CONIC_ASSEMBLY_SCHEMA = "square-gap-conic-assembly-v1"
const ComplexAffineExpression = JuMP.GenericAffExpr{ComplexF64,JuMP.VariableRef}

const BARE_INNER_STATIONARITY_RULE_CONIC =
    "all bare Pauli operator words through degree 2d-2 on the inner patch; " *
    "identity and exact-zero commutators removed; complex equations split " *
    "into normalized real equations; no scalar state-symbol multipliers; " *
    "no symmetry quotient; commutator engine is CoreMGK.commutator_polynomial"

struct ConicStationaritySpec
    family::Symbol
    version::Int

    function ConicStationaritySpec(
        family::Symbol = :bare_inner_pauli,
        version::Int = 1,
    )
        family == :bare_inner_pauli ||
            throw(ArgumentError("unsupported stationarity family"))
        version == 1 ||
            throw(ArgumentError("unsupported stationarity family version"))
        new(family, version)
    end
end

struct ConicAssembly{P}
    schema::String
    plan::CoreMGKPlan
    gamma::BigRational
    stationarity_spec::ConicStationaritySpec
    stationarity_selection_rule::String
    stationarity_candidates_sha256::String
    stationarity_equalities::Vector{Dict{ScalarMoment,BigRational}}
    stationarity_equalities_sha256::String
    moments::Vector{ScalarMoment}
    moments_sha256::String
    coefficient_map_sha256::String
    assembly_sha256::String
    problem_sha256::String
    source_plan::P
end

struct ConicJuMPModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    stationarity_constraints::Vector{JuMP.ConstraintRef}
    positive_constraint::JuMP.ConstraintRef
    gap_constraint::JuMP.ConstraintRef
    assembly_sha256::String
end

function gamma_big(problem::GapProblem)
    return BigRational(problem.gamma)
end

function checked_float(value::BigRational)
    iszero(value) && return 0.0
    converted = Float64(value)
    isfinite(converted) ||
        throw(ArgumentError("exact coefficient overflows Float64"))
    iszero(converted) &&
        throw(ArgumentError("nonzero exact coefficient underflows Float64"))
    return converted
end

function checked_complex_float(coefficient::GaussianRational)
    return ComplexF64(
        checked_float(real(coefficient)),
        checked_float(imag(coefficient)),
    )
end

function square_conic_moment_degree(moment::ScalarMoment)
    return sum(length, moment.state_symbol_multiset; init = 0)
end

function moment_sort_key(moment::ScalarMoment)
    return (square_conic_moment_degree(moment), scalar_moment_string(moment))
end

function remap_word(word::PauliWord, site_ids::Vector{Int})
    return PauliWord([(site_ids[site], axis) for (site, axis) in word.ops])
end

function write_framed!(io::IO, value)
    serialized = string(value)
    write(io, string(ncodeunits(serialized)), ":", serialized)
    return io
end

function fingerprint_records(schema::String, records)
    io = IOBuffer()
    write_framed!(io, schema)
    for record in records
        write_framed!(io, record)
    end
    return bytes2hex(sha256(take!(io)))
end

function stationarity_candidates_conic(
    problem::GapProblem,
    spec::ConicStationaritySpec = ConicStationaritySpec(),
)
    spec.family == :bare_inner_pauli && spec.version == 1 ||
        error("validated stationarity spec has no implementation")
    site_ids = sort!(copy(problem.patch.inner_ids))
    isempty(site_ids) &&
        throw(ArgumentError("stationarity needs at least one inner site"))
    local_words = enumerate_pauli_words(length(site_ids), 2 * problem.d - 2)
    return [remap_word(word, site_ids) for word in local_words]
end

function stationarity_row_coefficients(hamiltonian_terms, candidate::PauliWord)
    commutator = commutator_polynomial(hamiltonian_terms, candidate)
    coefficients = Dict{ScalarMoment,GaussianRational}()
    for (word, coefficient) in commutator
        iszero(coefficient) && continue
        row = scalarize(PauliWord[], word)
        add_coefficient!(coefficients, row, coefficient)
    end
    return coefficients
end

function normalize_real_equality(coeffs::Dict{ScalarMoment,BigRational})
    isempty(coeffs) && return copy(coeffs)
    ordered = sort!(collect(coeffs); by = pair -> scalar_moment_string(pair[1]))
    first_coeff = ordered[1][2]
    iszero(first_coeff) && error("leading stationarity coefficient is zero")
    normalized = Dict{ScalarMoment,BigRational}()
    for (moment, value) in ordered
        normalized[moment] = value // first_coeff
    end
    return normalized
end

function equality_canonical_string(coeffs::Dict{ScalarMoment,BigRational})
    ordered = sort!(collect(coeffs); by = pair -> scalar_moment_string(pair[1]))
    parts = String[
        scalar_moment_string(moment) * "=" *
        string(numerator(value)) * "/" * string(denominator(value))
        for (moment, value) in ordered
    ]
    return "eq[" * join(parts, ";") * "]=0"
end

function canonical_stationarity_equalities_conic(
    candidates::Vector{PauliWord},
    hamiltonian_terms,
)
    by_serialization = Dict{String,Dict{ScalarMoment,BigRational}}()
    for candidate in candidates
        complex_coeffs = stationarity_row_coefficients(
            hamiltonian_terms,
            candidate,
        )
        isempty(complex_coeffs) && continue
        for projector in (real, imag)
            real_coeffs = Dict{ScalarMoment,BigRational}()
            for (moment, coefficient) in complex_coeffs
                component = projector(coefficient)
                iszero(component) && continue
                real_coeffs[moment] = component
            end
            isempty(real_coeffs) && continue
            normalized = normalize_real_equality(real_coeffs)
            by_serialization[equality_canonical_string(normalized)] = normalized
        end
    end
    serializations = sort!(collect(keys(by_serialization)))
    return Dict{ScalarMoment,BigRational}[
        by_serialization[serialization] for serialization in serializations
    ]
end

function candidate_records(candidates::Vector{PauliWord})
    return String[
        "candidate[" * string(index) * "]=" * canonical_word_string(candidate)
        for (index, candidate) in enumerate(candidates)
    ]
end

function equality_records(equalities)
    return String[
        "equality[" * string(index) * "]=" * equality_canonical_string(eq)
        for (index, eq) in enumerate(equalities)
    ]
end

function moment_inventory_records(moments::Vector{ScalarMoment})
    return String[
        string(index) * "=" * scalar_moment_string(moment) *
        ";degree=" * string(square_conic_moment_degree(moment))
        for (index, moment) in enumerate(moments)
    ]
end

function collect_positive_moments!(moments::Set{ScalarMoment}, plan::CoreMGKPlan)
    basis = plan.positive_basis.entries
    for j in eachindex(basis), k in j:length(basis)
        components = positive_pair_components(basis[j], basis[k])
        for component in components, record in component.coefficients
            push!(moments, record.row)
        end
    end
    return moments
end

function collect_gap_moments!(
    moments::Set{ScalarMoment},
    plan::CoreMGKPlan,
    gamma::BigRational,
)
    basis = plan.gap_basis.entries
    for j in eachindex(basis), k in j:length(basis)
        wiring = core_mgk_pair(plan, :gap, j, k)
        affine = a_gamma_coefficients(wiring)
        for (moment, coefficient) in affine
            evaluated = coefficient.constant + gamma * coefficient.gamma
            iszero(evaluated) || push!(moments, moment)
        end
    end
    return moments
end

function collect_stationarity_moments!(
    moments::Set{ScalarMoment},
    equalities::Vector{Dict{ScalarMoment,BigRational}},
)
    for equality in equalities
        union!(moments, keys(equality))
    end
    return moments
end

function upper_triangle_coefficient_records(
    plan::CoreMGKPlan,
    gamma::BigRational,
)
    records = String[]
    positive = plan.positive_basis.entries
    for j in eachindex(positive), k in j:length(positive)
        components = positive_pair_components(positive[j], positive[k])
        m_component = only([
            component for component in components if component.component == :M
        ])
        push!(
            records,
            "positive[" * string(j) * "," * string(k) * "]=" *
            component_coefficient_sha(m_component),
        )
    end
    gap = plan.gap_basis.entries
    for j in eachindex(gap), k in j:length(gap)
        wiring = core_mgk_pair(plan, :gap, j, k)
        affine = a_gamma_coefficients(wiring)
        push!(
            records,
            "gap[" * string(j) * "," * string(k) * "]=" *
            gamma_coefficient_sha(affine, gamma),
        )
    end
    return records
end

function component_coefficient_sha(component::ExactComponent)
    io = IOBuffer()
    write_framed!(io, string(component.component))
    write_framed!(io, string(component.status))
    for record in sort(component.coefficients; by = r -> scalar_moment_string(r.row))
        write_framed!(io, scalar_moment_string(record.row))
        write_framed!(io, coeff_string(record.coefficient))
    end
    return bytes2hex(sha256(take!(io)))
end

function gamma_coefficient_sha(
    affine::Dict{ScalarMoment,GammaAffineCoefficient},
    gamma::BigRational,
)
    io = IOBuffer()
    write_framed!(io, "A_gamma")
    write_framed!(io, string(gamma))
    for moment in sort!(collect(keys(affine)); by = scalar_moment_string)
        coefficient = affine[moment]
        evaluated = coefficient.constant + gamma * coefficient.gamma
        write_framed!(io, scalar_moment_string(moment))
        write_framed!(io, coeff_string(evaluated))
    end
    return bytes2hex(sha256(take!(io)))
end

function coeff_string(value::GaussianRational)
    re = real(value)
    im_part = imag(value)
    return string(
        numerator(re),
        "/",
        denominator(re),
        "+",
        numerator(im_part),
        "/",
        denominator(im_part),
        "i",
    )
end

function assemble_square_conic(
    problem::GapProblem;
    stationarity_spec::ConicStationaritySpec = ConicStationaritySpec(),
)
    problem.basis_mode == :structured ||
        throw(ArgumentError("conic assembly requires :structured mode"))
    problem.symmetry isa NoStateSymmetry ||
        throw(ArgumentError(
            "state-symmetry metadata is not implemented by conic assembly",
        ))

    plan = core_mgk_plan(problem)
    gamma = gamma_big(problem)

    candidates = stationarity_candidates_conic(problem, stationarity_spec)
    candidates_sha256 = fingerprint_records(
        "conic-stationarity-candidates-v1",
        candidate_records(candidates),
    )
    equalities = canonical_stationarity_equalities_conic(
        candidates,
        plan.hamiltonian_terms,
    )
    equalities_sha256 = fingerprint_records(
        "conic-stationarity-real-equalities-v1",
        equality_records(equalities),
    )

    moments_set = Set{ScalarMoment}([ScalarMoment(PauliWord[])])
    collect_positive_moments!(moments_set, plan)
    collect_gap_moments!(moments_set, plan, gamma)
    collect_stationarity_moments!(moments_set, equalities)

    ordered_moments = sort!(collect(moments_set); by = moment_sort_key)
    first(ordered_moments) == ScalarMoment(PauliWord[]) ||
        error("identity scalar moment must be first")
    moments_sha256 = fingerprint_records(
        "conic-moment-inventory-v1",
        moment_inventory_records(ordered_moments),
    )
    coefficient_records = upper_triangle_coefficient_records(plan, gamma)
    coefficient_map_sha256 = fingerprint_records(
        "conic-upper-triangle-coefficients-v1",
        coefficient_records,
    )

    assembly_records = String[
        "schema=" * CONIC_ASSEMBLY_SCHEMA,
        "problem_sha256=" * plan.source_plan.problem_sha256,
        "gamma=" * string(gamma),
        "positive_basis_sha256=" * plan.positive_basis.sha256,
        "gap_basis_sha256=" * plan.gap_basis.sha256,
        "stationarity_family=" * string(stationarity_spec.family),
        "stationarity_version=" * string(stationarity_spec.version),
        "stationarity_candidates_sha256=" * candidates_sha256,
        "stationarity_equalities_sha256=" * equalities_sha256,
        "moments_sha256=" * moments_sha256,
        "coefficient_map_sha256=" * coefficient_map_sha256,
    ]
    assembly_sha256 = fingerprint_records(
        "square-gap-conic-fingerprint-v1",
        assembly_records,
    )

    return ConicAssembly(
        CONIC_ASSEMBLY_SCHEMA,
        plan,
        gamma,
        stationarity_spec,
        BARE_INNER_STATIONARITY_RULE_CONIC,
        candidates_sha256,
        equalities,
        equalities_sha256,
        ordered_moments,
        moments_sha256,
        coefficient_map_sha256,
        assembly_sha256,
        plan.source_plan.problem_sha256,
        plan.source_plan,
    )
end

function moment_index_map(moments::Vector{ScalarMoment})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("conic moment inventory contains duplicates"))
    return Dict(moment => index for (index, moment) in enumerate(moments))
end

function affine_from_positive(
    component::ExactComponent,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{ScalarMoment,Int},
)
    expression = ComplexAffineExpression(0.0 + 0.0im)
    for record in component.coefficients
        index = moment_indices[record.row]
        JuMP.add_to_expression!(
            expression,
            checked_complex_float(record.coefficient),
            moment_variables[index],
        )
    end
    return expression
end

function affine_from_gap(
    affine::Dict{ScalarMoment,GammaAffineCoefficient},
    gamma::BigRational,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{ScalarMoment,Int},
)
    expression = ComplexAffineExpression(0.0 + 0.0im)
    for (moment, coefficient) in affine
        evaluated = coefficient.constant + gamma * coefficient.gamma
        iszero(evaluated) && continue
        index = moment_indices[moment]
        JuMP.add_to_expression!(
            expression,
            checked_complex_float(evaluated),
            moment_variables[index],
        )
    end
    return expression
end

function require_real_diagonal(
    expression::ComplexAffineExpression,
    role::Symbol,
    index::Int,
)
    all(iszero ∘ imag, values(expression.terms)) ||
        error("$role matrix diagonal $index has a non-real variable coefficient")
    iszero(imag(expression.constant)) ||
        error("$role matrix diagonal $index has a non-real constant")
    return expression
end

function conic_hermitian_matrix(
    role::Symbol,
    assembly::ConicAssembly,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{ScalarMoment,Int},
)
    role in (:positive, :gap) ||
        throw(ArgumentError("matrix role must be :positive or :gap"))
    plan = assembly.plan
    basis = role == :positive ? plan.positive_basis.entries : plan.gap_basis.entries
    dimension = length(basis)
    matrix = Matrix{ComplexAffineExpression}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        expression = if role == :positive
            components = positive_pair_components(basis[row], basis[column])
            m_component = only([
                component for component in components
                if component.component == :M
            ])
            affine_from_positive(m_component, moment_variables, moment_indices)
        else
            wiring = core_mgk_pair(plan, :gap, row, column)
            affine_from_gap(
                a_gamma_coefficients(wiring),
                assembly.gamma,
                moment_variables,
                moment_indices,
            )
        end
        if row == column
            require_real_diagonal(expression, role, row)
        end
        matrix[row, column] = expression
        if row != column
            matrix[column, row] = conj(expression)
        end
    end
    return matrix
end

function name_constraint!(constraint::JuMP.ConstraintRef, name::String)
    JuMP.set_name(constraint, name)
    return constraint
end

function build_square_conic_jump(
    assembly::ConicAssembly;
    model::JuMP.Model = JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    first(assembly.moments) == ScalarMoment(PauliWord[]) ||
        error("conic assembly identity moment is not first")

    moment_indices = moment_index_map(assembly.moments)
    moment_variables = JuMP.@variable(
        model,
        [1:length(assembly.moments)],
        base_name = "moment",
    )
    normalization = name_constraint!(
        JuMP.@constraint(model, moment_variables[1] == 1.0),
        "normalization",
    )

    stationarity_constraints = JuMP.ConstraintRef[]
    for (index, equality) in enumerate(assembly.stationarity_equalities)
        expression = JuMP.AffExpr(0.0)
        for (moment, coefficient) in equality
            variable_index = moment_indices[moment]
            JuMP.add_to_expression!(
                expression,
                checked_float(coefficient),
                moment_variables[variable_index],
            )
        end
        push!(
            stationarity_constraints,
            name_constraint!(
                JuMP.@constraint(model, expression == 0.0),
                "stationarity[$index]",
            ),
        )
    end

    positive_matrix = conic_hermitian_matrix(
        :positive,
        assembly,
        moment_variables,
        moment_indices,
    )
    positive_constraint = name_constraint!(
        JuMP.@constraint(
            model,
            Hermitian(positive_matrix) in JuMP.HermitianPSDCone(),
        ),
        "positive_psd",
    )

    gap_matrix = conic_hermitian_matrix(
        :gap,
        assembly,
        moment_variables,
        moment_indices,
    )
    gap_constraint = name_constraint!(
        JuMP.@constraint(
            model,
            Hermitian(gap_matrix) in JuMP.HermitianPSDCone(),
        ),
        "gap_psd",
    )

    return ConicJuMPModel(
        model,
        moment_variables,
        normalization,
        stationarity_constraints,
        positive_constraint,
        gap_constraint,
        assembly.assembly_sha256,
    )
end

struct D4ConicJuMPModel
    model::JuMP.Model
    moment_variables::Vector{JuMP.VariableRef}
    normalization_constraint::JuMP.ConstraintRef
    stationarity_constraints::Vector{JuMP.ConstraintRef}
    positive_block_constraints::Vector{JuMP.ConstraintRef}
    positive_block_irreps::Vector{Symbol}
    gap_constraint::JuMP.ConstraintRef
    assembly_sha256::String
end

"""Build a complex affine from a flat ScalarMoment -> GaussianRational map."""
function affine_from_coefficients(
    coeffs::Dict{ScalarMoment,GaussianRational},
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{ScalarMoment,Int},
)
    expression = ComplexAffineExpression(0.0 + 0.0im)
    for (moment, coefficient) in coeffs
        iszero(coefficient) && continue
        index = moment_indices[moment]
        JuMP.add_to_expression!(
            expression,
            checked_complex_float(coefficient),
            moment_variables[index],
        )
    end
    return expression
end

"""
One D4 irrep block of the positive moment matrix: `(Q_lambda' M Q_lambda)[a,b]`
where only the sparse support of the Q columns is visited, so each entry costs
~(|supp_a| * |supp_b|) CoreMGK pair evaluations. Upper triangle built directly;
lower triangle is the explicit conjugate; diagonal reality is checked.
"""
function d4_positive_block_matrix(
    assembly::ConicAssembly,
    d4_basis::D4SymmetryBasis,
    block_idx::Int,
    moment_variables::Vector{JuMP.VariableRef},
    moment_indices::Dict{ScalarMoment,Int},
)
    plan = assembly.plan
    entries = plan.positive_basis.entries
    Q = d4_basis.Q
    range = d4_basis.block_ranges[block_idx]
    irrep = d4_basis.block_irreps[block_idx]
    block_dim = length(range)
    supports = Vector{Tuple{Int,Rational{BigInt}}}[
        [(j, Q[j, a]) for j in axes(Q, 1) if !iszero(Q[j, a])] for a in range
    ]
    matrix = Matrix{ComplexAffineExpression}(undef, block_dim, block_dim)
    for ai in 1:block_dim
        for bi in ai:block_dim
            coeffs = Dict{ScalarMoment,GaussianRational}()
            for (j, qj) in supports[ai]
                for (k, qk) in supports[bi]
                    components = positive_pair_components(entries[j], entries[k])
                    m_component = only([
                        component for component in components
                        if component.component == :M
                    ])
                    weight = qj * qk
                    for record in m_component.coefficients
                        add_coefficient!(coeffs, record.row, weight * record.coefficient)
                    end
                end
            end
            matrix[ai, bi] = affine_from_coefficients(coeffs, moment_variables, moment_indices)
        end
        require_real_diagonal(matrix[ai, ai], Symbol("positive_d4_$irrep"), ai)
        for bi in (ai + 1):block_dim
            matrix[bi, ai] = conj(matrix[ai, bi])
        end
    end
    return matrix
end

"""
D4 action on a scalar moment: relabel every Pauli word in its multiset.
"""
function apply_perm_to_scalar_moment(perm::Vector{Int}, moment::ScalarMoment)
    return ScalarMoment([apply_site_perm(perm, w) for w in moment.state_symbol_multiset])
end

struct D4MomentQuotient
    representative_moments::Vector{ScalarMoment}
    moment_to_variable::Dict{ScalarMoment,Int}
    original_count::Int
    quotient_count::Int
    orbit_histogram::Dict{Int,Int}
end

"""
Collapse the scalar-moment variable set by D4-orbit: a D4-invariant functional
has L(m) = L(g.m), so all moments in one D4 orbit share a single variable.
Returns the ordered representative-moment list (identity first) and a map from
every original moment to its representative's variable index. This is the
exactly-equivalent moment-coordinate quotient (Sihan's lever 2).
"""
function d4_moment_quotient(
    moments::Vector{ScalarMoment},
    perms::Vector{Vector{Int}},
)
    moment_to_rep = Dict{ScalarMoment,ScalarMoment}()
    orbit_seen = Set{ScalarMoment}()
    histogram = Dict{Int,Int}()
    for moment in moments
        haskey(moment_to_rep, moment) && continue
        orbit = Set{ScalarMoment}([moment])
        for perm in perms
            push!(orbit, apply_perm_to_scalar_moment(perm, moment))
        end
        rep = sort!(collect(orbit); by = m -> scalar_moment_string(m))[1]
        haskey(histogram, length(orbit)) || (histogram[length(orbit)] = 0)
        histogram[length(orbit)] += 1
        for m in orbit
            moment_to_rep[m] = rep
            push!(orbit_seen, m)
        end
    end
    reps = sort!(
        collect(Set(values(moment_to_rep)));
        by = m -> (sum(length, m.state_symbol_multiset; init = 0), scalar_moment_string(m)),
    )
    isempty(reps) || first(reps) == ScalarMoment(PauliWord[]) ||
        error("identity moment is not first after quotient ordering")
    rep_to_var = Dict(rep => i for (i, rep) in enumerate(reps))
    moment_to_variable = Dict{ScalarMoment,Int}(
        m => rep_to_var[moment_to_rep[m]] for m in moments
    )
    return D4MomentQuotient(reps, moment_to_variable, length(moments), length(reps), histogram)
end

"""
Build the D4-blocked primal JuMP feasibility model: one HermitianPSDCone per
positive irrep block (A1/A2/B1/B2/E) instead of one 352-dim cone, plus the
unchanged 4-dim gap cone (the gap basis is entirely on the D4-fixed centre site,
so it is all A1 and does not split). Normalization and stationarity are
unchanged from the unsymmetrized assembly.
"""
function build_square_d4_conic_jump(
    assembly::ConicAssembly,
    d4_basis::D4SymmetryBasis,
    perms::Vector{Vector{Int}};
    model::JuMP.Model = JuMP.Model(),
)
    JuMP.num_variables(model) == 0 ||
        throw(ArgumentError("target JuMP model must be empty"))
    isempty(JuMP.list_of_constraint_types(model)) ||
        throw(ArgumentError("target JuMP model must be empty"))
    first(assembly.moments) == ScalarMoment(PauliWord[]) ||
        error("conic assembly identity moment is not first")
    length(d4_basis.entries) == length(assembly.plan.positive_basis.entries) ||
        error("D4 basis does not match the positive basis")

    quotient = d4_moment_quotient(assembly.moments, perms)
    moment_indices = quotient.moment_to_variable
    moment_variables = JuMP.@variable(
        model,
        [1:quotient.quotient_count],
        base_name = "moment",
    )
    normalization = name_constraint!(
        JuMP.@constraint(model, moment_variables[1] == 1.0),
        "normalization",
    )

    stationarity_constraints = JuMP.ConstraintRef[]
    for (index, equality) in enumerate(assembly.stationarity_equalities)
        expression = JuMP.AffExpr(0.0)
        for (moment, coefficient) in equality
            variable_index = moment_indices[moment]
            JuMP.add_to_expression!(
                expression,
                checked_float(coefficient),
                moment_variables[variable_index],
            )
        end
        push!(
            stationarity_constraints,
            name_constraint!(
                JuMP.@constraint(model, expression == 0.0),
                "stationarity[$index]",
            ),
        )
    end

    positive_block_constraints = JuMP.ConstraintRef[]
    positive_block_irreps = Symbol[]
    for block_idx in eachindex(d4_basis.block_irreps)
        irrep = d4_basis.block_irreps[block_idx]
        block_matrix = d4_positive_block_matrix(
            assembly,
            d4_basis,
            block_idx,
            moment_variables,
            moment_indices,
        )
        push!(
            positive_block_constraints,
            name_constraint!(
                JuMP.@constraint(
                    model,
                    Hermitian(block_matrix) in JuMP.HermitianPSDCone(),
                ),
                "positive_psd_d4_$irrep",
            ),
        )
        push!(positive_block_irreps, irrep)
    end

    gap_matrix = conic_hermitian_matrix(:gap, assembly, moment_variables, moment_indices)
    gap_constraint = name_constraint!(
        JuMP.@constraint(
            model,
            Hermitian(gap_matrix) in JuMP.HermitianPSDCone(),
        ),
        "gap_psd",
    )

    return D4ConicJuMPModel(
        model,
        moment_variables,
        normalization,
        stationarity_constraints,
        positive_block_constraints,
        positive_block_irreps,
        gap_constraint,
        assembly.assembly_sha256,
    )
end

end
