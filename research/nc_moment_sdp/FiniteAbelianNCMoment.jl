module FiniteAbelianNCMoment

using JuMP
using LinearAlgebra
using MosekTools
const MOI = JuMP.MOI

include("algebra.jl")
include("problem.jl")
include("compile.jl")
include("solver.jl")
include("benchmarks.jl")

export GeneratorSystem, NCWord, NCPolynomial, ReducedMonomial,
       StarAlgebraBackend, LegacyInvolutionBackend, PauliBackend,
       NCProblem, AffineForm, CompiledDenseIR, SDPResult,
       generators, reduce_word, star_word, star, polynomial, coefficient,
       normalize_word, enumerate_words, moment_key, word_character,
       compile_dense, solve_moment_sdp, evaluate_moment,
       chsh_z2, pauli_z2xz2, complex_pauli_benchmark,
       equality_localizer_benchmark

end
