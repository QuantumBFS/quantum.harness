module QuantumMCMethods

using Carlo
using HDF5
using LinearAlgebra
using Random
using Statistics

include("models.jl")
include("exact.jl")
include("sse.jl")
include("analysis.jl")
include("diagnostics.jl")
include("carlo_adapter.jl")

export SquareLatticeTFIM,
       nsites,
       nbonds,
       site_index,
       dense_hamiltonian,
       exact_spectrum,
       exact_thermal_observables,
       exact_open_chain_observables,
       exact_infinite_chain_observables,
       exact_expansion_order_moments,
       independent_spin_observables,
       classical_enumeration,
       SSEState,
       initialize_sse,
       diagonal_update!,
       quantum_cluster_update!,
       sweep!,
       grow_cutoff!,
       validate_configuration,
       raw_measurement,
       Estimate,
       SSEResult,
       run_sse,
       SSETrace,
       AutocorrelationEstimate,
       BlockingPoint,
       sample_sse_trace,
       observable_estimate,
       observable_influence,
       autocorrelation_estimate,
       blocking_curve,
       TFIMSSECarlo

end
