#!/usr/bin/env julia

include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(@__DIR__, "..", "src", "CoreMGK.jl"))
using .CoreMGK

function component_map(components, name)
    component = only(filter(record -> record.component == name, components))
    return Dict(
        coefficient.row => coefficient.coefficient
        for coefficient in component.coefficients
    )
end

function assert_hermitian(forward, reverse, component)
    left = component_map(forward, component)
    right = component_map(reverse, component)
    keys(left) == keys(right) || error("$component row targets fail swapped check")
    all(right[row] == conj(value) for (row, value) in left) ||
        error("$component coefficients fail swapped check")
end

function register_rows!(rows, components)
    count = 0
    for component in components, coefficient in component.coefficients
        push!(rows, scalar_moment_string(coefficient.row))
        count += 1
    end
    return count
end

function main(args=ARGS)
    isempty(args) || error("check_square_core_mgk.jl takes no arguments")
    problem = GapProblem(
        square_patch_geometry(1),
        square_j1j2_model(1//2),
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    plan = core_mgk_plan(problem)
    rows = Set{String}()
    coefficient_count = 0
    positive_pairs = 0
    gap_pairs = 0
    component_records = 0
    elapsed = @elapsed begin
        positive = plan.positive_basis.entries
        for j in eachindex(positive), k in j:length(positive)
            forward = positive_pair_components(positive[j], positive[k])
            reverse = positive_pair_components(positive[k], positive[j])
            assert_hermitian(forward, reverse, :M)
            j == k && any(!iszero ∘ imag ∘ (record -> record.coefficient),
                          only(forward).coefficients) &&
                error("M diagonal has a non-real coefficient")
            coefficient_count += register_rows!(rows, forward)
            positive_pairs += 1
            component_records += 1
            if positive_pairs % 50_000 == 0
                println("progress_positive_pairs\t", positive_pairs)
                flush(stdout)
            end
        end

        gap = plan.gap_basis.entries
        for j in eachindex(gap), k in j:length(gap)
            forward = gap_pair_components(plan.hamiltonian_terms, gap[j], gap[k])
            reverse = gap_pair_components(plan.hamiltonian_terms, gap[k], gap[j])
            for component in (:K, :G_moment, :G_product)
                assert_hermitian(forward, reverse, component)
            end
            if j == k
                for component in forward, coefficient in component.coefficients
                    iszero(imag(coefficient.coefficient)) ||
                        error("$(component.component) diagonal has a non-real coefficient")
                end
            end
            coefficient_count += register_rows!(rows, forward)
            gap_pairs += 1
            component_records += 3
        end
    end

    expected_positive_pairs = div(
        length(plan.positive_basis.entries) *
        (length(plan.positive_basis.entries) + 1),
        2,
    )
    expected_gap_pairs = div(
        length(plan.gap_basis.entries) *
        (length(plan.gap_basis.entries) + 1),
        2,
    )
    positive_pairs == expected_positive_pairs || error("positive pair coverage incomplete")
    gap_pairs == expected_gap_pairs || error("gap pair coverage incomplete")
    component_records == positive_pairs + 3gap_pairs ||
        error("component coverage incomplete")

    println("model\tsquare-j1-j2")
    println("hamiltonian\tJ1=1;g=1/2;S=sigma/2")
    println("patch\tL=1;outer=3x3;inner=1x1;no finite-volume boundary")
    println("degree\t2")
    println("gamma_for_source_problem\t1/10")
    println("state_class\t", plan.state_class)
    println("hamiltonian_terms\t", length(plan.hamiltonian_terms))
    println("positive_basis_rows\t", length(plan.positive_basis.entries))
    println("positive_basis_sha256\t", plan.positive_basis.sha256)
    println("gap_basis_rows\t", length(plan.gap_basis.entries))
    println("gap_basis_sha256\t", plan.gap_basis.sha256)
    println("source_problem_sha256\t", plan.source_plan.problem_sha256)
    println("positive_upper_pairs\t", positive_pairs)
    println("gap_upper_pairs\t", gap_pairs)
    println("component_records\t", component_records)
    println("nonzero_row_coefficients\t", coefficient_count)
    println("referenced_scalar_rows\t", length(rows))
    println("independent_swapped_hermitian_check\tpass")
    println("elapsed_seconds\t", elapsed)
    println("solver_invoked\tfalse")
    flush(stdout)
    return 0
end

exit(main())
