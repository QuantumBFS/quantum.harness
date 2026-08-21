module LegacySSEModel

using Main.Challenge148: LatticeGeometry, lattice_geometry
import StochasticSeriesExpansion as SSE

export TFIMModel, tfim_bond_hamiltonian

struct TFIMModel <: SSE.AbstractModel
    geometry::LatticeGeometry
    lattice::SSE.Lattice{2}
    J::Float64
    h_input::Float64
    h_simulated::Float64
    opstring_estimators::Vector{DataType}
end

function TFIMModel(params::AbstractDict{Symbol,<:Any})
    lattice_name = params[:lattice]
    L = Int(params[:L])
    geometry = lattice_geometry(lattice_name, L)
    unitcell = if lattice_name === :triangle
        SSE.UnitCells.triangle
    elseif lattice_name === :honeycomb
        SSE.UnitCells.honeycomb
    else
        throw(ArgumentError("unsupported lattice: $lattice_name"))
    end
    lattice = SSE.Lattice(unitcell, (L, L))
    package_bonds = [(bond.i, bond.j) for bond in lattice.bonds]
    package_bonds == geometry.bonds ||
        error("SSE lattice bonds differ from the shared ED/QMC bond list")

    measure = get(params, :measure, [:magnetization])
    measure == [:magnetization] ||
        throw(ArgumentError("the c=1 pilot currently supports only :magnetization"))
    estimator = SSE.MagnetizationEstimator{
        (false, false),
        false,
        TFIMModel,
        Symbol(),
        nothing,
    }

    h_input = Float64(params[:h])
    return TFIMModel(
        geometry,
        lattice,
        Float64(get(params, :J, 1.0)),
        h_input,
        abs(h_input),
        DataType[estimator],
    )
end

SSE.leg_count(::Type{<:TFIMModel}) = 4
SSE.normalization_site_count(model::TFIMModel) = model.geometry.nsites
SSE.get_opstring_estimators(model::TFIMModel) = model.opstring_estimators

SSE.magnetization_state(
    ::TFIMModel,
    ::Val,
    ::Integer,
    state_idx::Integer,
) = state_idx == 1 ? 1.0 : -1.0

function SSE.generate_sse_data(model::TFIMModel)
    coordinations = unique(model.geometry.coordination)
    length(coordinations) == 1 || error("TFIM SSE requires a regular lattice")
    coordination = only(coordinations)
    Hbond = tfim_bond_hamiltonian(model.J, model.h_simulated, coordination)
    vertex_data = [SSE.VertexData((2, 2), Hbond)]
    bonds = [SSE.SSEBond(1, bond) for bond in model.geometry.bonds]
    return SSE.SSEData(vertex_data, bonds)
end

function tfim_bond_hamiltonian(J::Real, h::Real, coordination::Integer)
    coordination > 0 || throw(ArgumentError("coordination must be positive"))
    g = float(h) / coordination
    return [
        -float(J) -g -g 0.0
        -g float(J) 0.0 -g
        -g 0.0 float(J) -g
        0.0 -g -g -float(J)
    ]
end

end
