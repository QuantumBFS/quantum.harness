"""
    SquareLatticeTFIM(Lx, Ly; J=1.0, h=1.0)

Open-boundary square-lattice transverse-field Ising model

`H = -J Σ⟨ij⟩ σᶻᵢσᶻⱼ - h Σᵢ σˣᵢ`,

where the Pauli operators have eigenvalues `±1`.
"""
struct SquareLatticeTFIM
    Lx::Int
    Ly::Int
    J::Float64
    h::Float64
    bonds::Vector{NTuple{2,Int}}

    function SquareLatticeTFIM(Lx::Integer, Ly::Integer;
                               J::Real=1.0, h::Real=1.0)
        Lx > 0 || throw(ArgumentError("Lx must be positive"))
        Ly > 0 || throw(ArgumentError("Ly must be positive"))
        J >= 0 || throw(ArgumentError("the validated SSE decomposition requires J ≥ 0"))
        h >= 0 || throw(ArgumentError("the validated SSE decomposition requires h ≥ 0"))

        lx = Int(Lx)
        ly = Int(Ly)
        bonds = NTuple{2,Int}[]
        sizehint!(bonds, (lx - 1) * ly + lx * (ly - 1))

        # Horizontal bonds, then vertical bonds. This order is part of the
        # reproducible model convention documented in notes/models/.
        for y in 1:ly, x in 1:(lx - 1)
            push!(bonds, (site_index(x, y, lx), site_index(x + 1, y, lx)))
        end
        for y in 1:(ly - 1), x in 1:lx
            push!(bonds, (site_index(x, y, lx), site_index(x, y + 1, lx)))
        end

        new(lx, ly, Float64(J), Float64(h), bonds)
    end
end

site_index(x::Integer, y::Integer, Lx::Integer) = Int(x + (y - 1) * Lx)
nsites(model::SquareLatticeTFIM) = model.Lx * model.Ly
nbonds(model::SquareLatticeTFIM) = length(model.bonds)

function Base.show(io::IO, model::SquareLatticeTFIM)
    print(io, "SquareLatticeTFIM(",
          model.Lx, "×", model.Ly,
          ", OBC, J=", model.J,
          ", h=", model.h, ")")
end
