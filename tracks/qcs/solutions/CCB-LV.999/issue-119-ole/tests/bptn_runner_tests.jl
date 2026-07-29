include(joinpath(@__DIR__, "..", "src", "BPTNRunner.jl"))
using .BPTNRunner

const IDENTITY_QASM = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
rx(pi/3) q[0];
rz(-0.2) q[1];
barrier q[0],q[1];
cz q[0],q[1];
barrier q[0],q[1];
cz q[0],q[1];
barrier q[0],q[1];
rz(0.2) q[1];
rx(-pi/3) q[0];
barrier q[0],q[1];
"""

@testset "real TNQS runner preserves an exact inverse circuit" begin
    protocol = OLEProtocol.parse_qasm(IDENTITY_QASM)
    checkpointed_layers = Int[]
    result = run_seed(
        protocol;
        seed_namespace = "issue119-ole-test",
        seed_id = 1,
        observable_labels = [0, 1],
        maxdim = 4,
        cutoff = 1.0e-12,
        dtype = ComplexF64,
        bp_maxiter = 5,
        bp_tolerance = 1.0e-12,
        progress = false,
        layer_callback = record -> push!(checkpointed_layers, record.layer),
    )

    @test result.seed_id == 1
    @test result.sample_value ≈ 1.0 atol = 1.0e-11
    @test result.raw_expectation ≈ result.initial_parity atol = 1.0e-11
    @test result.max_truncation_error ≤ 1.0e-12
    @test length(result.layers) == 4
    @test all(record -> record.bp_residual ≤ 1.0e-12, result.layers)
    @test all(record -> record.bp_converged, result.layers)
    @test checkpointed_layers == [1, 2, 3, 4]
    @test result.wall_seconds ≥ 0
end
