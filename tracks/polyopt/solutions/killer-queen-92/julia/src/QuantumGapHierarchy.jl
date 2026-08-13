module QuantumGapHierarchy

using LinearAlgebra
using SparseArrays
using JuMP
using Clarabel
import Pardiso
using MathOptInterface
using JSON3
using Arblib

include("Algebra.jl")
include("Types.jl")
include("StatePolynomials.jl")
include("Hierarchy.jl")
include("Solver.jl")
include("Certificates.jl")
include("Serialization.jl")

export Q23, SQRT2, SQRT3, LocalAtom, OperatorWord, PureStateMonomial, StateMonomial,
       LevelSpec, ModelParams, RootedGraph, HierarchyTemplate, SolveRecord, GapBracket,
       CertificateReport, PRIMARY_SYMMETRY, UNRESTRICTED_SYMMETRY,
       LocalBasisData, local_basis, local_basis_data, ladder_matrices, ladder_degrees,
       multiply_words, rebase_word, charge, support, degree,
       operator_basis, state_basis, graph_window, neighbors, hamiltonian_degree,
       build_level, level_fingerprint, term_sparsity_cliques,
       solve_feasibility, solve_observable, bisect_gap, verify_certificate,
       read_graph_json, write_record_json, write_template_summary

end
