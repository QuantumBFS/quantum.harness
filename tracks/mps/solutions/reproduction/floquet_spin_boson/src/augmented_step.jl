using LinearAlgebra

"""
Index layout for the augmented state `Liouville(system) ⊗ bond`.

An augmented vector is `vec(R)` for a `bond_dimension × 4` matrix `R`.
Consequently the bond index is fastest:
`i(a, s) = a + bond_dimension * (s - 1)`.
"""
struct AugmentedLayout
    bond_dimension::Int
    liouville_dimension::Int
    augmented_dimension::Int

    function AugmentedLayout(bond_dimension::Integer; liouville_dimension::Integer=4)
        bond_dimension > 0 || throw(ArgumentError("bond dimension must be positive"))
        liouville_dimension == 4 ||
            throw(ArgumentError("single-spin Liouville dimension must equal 4"))
        return new(Int(bond_dimension), 4, 4Int(bond_dimension))
    end
end

function composite_index(layout::AugmentedLayout, bond_index::Integer,
                         liouville_index::Integer)
    checkbounds(Bool, 1:layout.bond_dimension, bond_index) ||
        throw(BoundsError(1:layout.bond_dimension, bond_index))
    checkbounds(Bool, 1:layout.liouville_dimension, liouville_index) ||
        throw(BoundsError(1:layout.liouville_dimension, liouville_index))
    return Int(bond_index) + layout.bond_dimension * (Int(liouville_index) - 1)
end

struct StepOperator{T<:Number,QM<:AbstractMatrix{T},LC<:AbstractMatrix{T},RC<:AbstractMatrix{T}}
    layout::AugmentedLayout
    q_matrix::QM
    left_channel::LC
    right_channel::RC
end

function StepOperator(q::AbstractArray{<:Number,4}, left_channel::AbstractMatrix{<:Number},
                      right_channel::AbstractMatrix{<:Number})
    χ = size(q, 1)
    size(q) == (χ, 4, χ, 4) ||
        throw(DimensionMismatch("q must have shape (χ, 4, χ, 4)"))
    size(left_channel) == (4, 4) ||
        throw(DimensionMismatch("left half-step channel must be 4×4"))
    size(right_channel) == (4, 4) ||
        throw(DimensionMismatch("right half-step channel must be 4×4"))
    T = promote_type(eltype(q), eltype(left_channel), eltype(right_channel))
    q_data = Array{T,4}(q)
    left = Matrix{T}(left_channel)
    right = Matrix{T}(right_channel)
    return StepOperator(AugmentedLayout(χ), reshape(q_data, 4χ, 4χ), left, right)
end

mutable struct StepWorkspace{T<:Number}
    tmp1::Vector{T}
    tmp2::Vector{T}
    period1::Vector{T}
    period2::Vector{T}
end

function StepWorkspace(layout::AugmentedLayout, ::Type{T}=ComplexF64) where {T<:Number}
    n = layout.augmented_dimension
    return StepWorkspace(zeros(T, n), zeros(T, n), zeros(T, n), zeros(T, n))
end

StepWorkspace(step::StepOperator{T}) where {T} = StepWorkspace(step.layout, T)

function _check_augmented_vectors(y, x, layout::AugmentedLayout)
    length(x) == layout.augmented_dimension ||
        throw(DimensionMismatch("input augmented vector has the wrong length"))
    length(y) == layout.augmented_dimension ||
        throw(DimensionMismatch("output augmented vector has the wrong length"))
    return nothing
end

function _check_workspace(work::StepWorkspace, layout::AugmentedLayout)
    expected = layout.augmented_dimension
    length(work.tmp1) == expected && length(work.tmp2) == expected ||
        throw(DimensionMismatch("step workspace has the wrong layout"))
    return nothing
end

@inline function _apply_system_channel!(y::AbstractVector, x::AbstractVector,
                                        channel::AbstractMatrix,
                                        layout::AugmentedLayout)
    χ = layout.bond_dimension
    @inbounds for system_out in 1:4
        output_offset = χ * (system_out - 1)
        for bond in 1:χ
            value = zero(promote_type(eltype(y), eltype(x), eltype(channel)))
            for system_in in 1:4
                value += channel[system_out, system_in] *
                         x[bond + χ * (system_in - 1)]
            end
            y[bond + output_offset] = value
        end
    end
    return y
end

"""Apply one augmented step without forming its dense `4χ × 4χ` matrix."""
function apply_step!(y::AbstractVector, x::AbstractVector, step::StepOperator,
                     work::StepWorkspace)
    _check_augmented_vectors(y, x, step.layout)
    _check_workspace(work, step.layout)
    _apply_system_channel!(work.tmp1, x, step.left_channel, step.layout)
    mul!(work.tmp2, step.q_matrix, work.tmp1)
    _apply_system_channel!(y, work.tmp2, step.right_channel, step.layout)
    return y
end

"""Apply the Hermitian adjoint of one augmented step."""
function apply_step_adjoint!(y::AbstractVector, x::AbstractVector, step::StepOperator,
                             work::StepWorkspace)
    _check_augmented_vectors(y, x, step.layout)
    _check_workspace(work, step.layout)
    _apply_system_channel!(work.tmp1, x, adjoint(step.right_channel), step.layout)
    mul!(work.tmp2, adjoint(step.q_matrix), work.tmp1)
    _apply_system_channel!(y, work.tmp2, adjoint(step.left_channel), step.layout)
    return y
end
