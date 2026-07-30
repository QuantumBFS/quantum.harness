include(joinpath(@__DIR__, "..", "src", "OLEProtocol.jl"))
using .OLEProtocol

const TINY_QASM = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[8];
rx(pi/2) q[2];
s q[5];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7];
cz q[2],q[5];
sdg q[2];
sx q[5];
sxdg q[2];
rz(-3*pi/8) q[5];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7];
"""

const TINY_TRACKER_QASM3 = """
OPENQASM 3.0;
include "stdgates.inc";
gate sxdg _gate_q_0 {
  s _gate_q_0;
  h _gate_q_0;
  s _gate_q_0;
}
qubit[8] q;
rx(pi/2) q[2];
s q[5];
barrier q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7];
cz q[2], q[5];
sdg q[2];
sx q[5];
sxdg q[2];
rz(-3*pi/8) q[5];
barrier q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7];
"""

@testset "strict OpenQASM subset and physical-label mapping" begin
    protocol = parse_qasm(TINY_QASM)

    @test protocol.register_size == 8
    @test protocol.physical_labels == [2, 5]
    @test protocol.physical_to_internal == Dict(2 => 1, 5 => 2)
    @test length(protocol.layers) == 2
    @test length(protocol.layers[1]) == 2
    @test length(protocol.layers[2]) == 5
    @test protocol.barrier_count == 2
    @test gate_counts(protocol) == Dict(
        "cz" => 1,
        "rx" => 1,
        "rz" => 1,
        "s" => 1,
        "sdg" => 1,
        "sx" => 1,
        "sxdg" => 1,
    )

    tnqs = reduce(vcat, tnqs_layers(protocol))
    @test first(tnqs) == ("Rx", [2], π / 2)
    @test tnqs[2] == ("Rz", [5], π / 2)
    @test tnqs[3] == ("CZ", [2, 5])
    @test tnqs[4] == ("Rz", [2], -π / 2)
    @test tnqs[5] == ("Rx", [5], π / 2)
    @test tnqs[6] == ("Rx", [2], -π / 2)
    @test tnqs[7] == ("Rz", [5], -3π / 8)
end

@testset "Tracker OpenQASM 3 export preserves the canonical TNQS circuit" begin
    qasm3_protocol = try
        parse_qasm(TINY_TRACKER_QASM3)
    catch
        nothing
    end
    @test !isnothing(qasm3_protocol)
    if !isnothing(qasm3_protocol)
        qasm2_protocol = parse_qasm(TINY_QASM)
        @test qasm3_protocol.register_size == qasm2_protocol.register_size
        @test qasm3_protocol.barrier_count == qasm2_protocol.barrier_count
        @test qasm3_protocol.physical_labels == qasm2_protocol.physical_labels
        @test tnqs_layers(qasm3_protocol) == tnqs_layers(qasm2_protocol)
    end
end

@testset "parser rejects silent protocol changes" begin
    @test_throws ArgumentError parse_qasm(replace(TINY_QASM, "sx q[5];" => "h q[5];"))
    @test_throws ArgumentError parse_qasm(replace(TINY_QASM, "pi/2" => "sin(pi/2)"))
    @test_throws ArgumentError parse_qasm(replace(TINY_QASM, "q[8]" => "q[3]"))
end

@testset "stable seed bank does not depend on Julia RNG internals" begin
    labels = [2, 5, 52, 59, 72]
    @test basis_bits("issue119-ole-v1", 1, labels) == [0, 1, 0, 1, 1]
    @test basis_bits("issue119-ole-v1", 2, labels) == [0, 1, 0, 1, 0]
    @test basis_bits("issue119-ole-v1", 1, reverse(labels)) ==
          reverse(basis_bits("issue119-ole-v1", 1, labels))
    @test observable_parity(Dict(zip(labels, [0, 1, 0, 1, 1])), [52, 59, 72]) == 1
    @test observable_parity(Dict(zip(labels, [0, 1, 0, 1, 0])), [52, 59, 72]) == -1
end

@testset "input identity is content-addressed" begin
    @test qasm_sha256(TINY_QASM) ==
          "75c6fb8bff95e19402763d32504fcca332b0daf527e604edcc4b28101bdf188d"
    @test validate_qasm_identity(
        TINY_QASM;
        expected_sha256 = qasm_sha256(TINY_QASM),
        expected_bytes = ncodeunits(TINY_QASM),
    ) === nothing
    @test_throws ArgumentError validate_qasm_identity(
        TINY_QASM;
        expected_sha256 = repeat("0", 64),
        expected_bytes = ncodeunits(TINY_QASM),
    )
end

@testset "delta-zero control changes only the audited perturbation angles" begin
    perturbed = parse_qasm(replace(TINY_QASM, "rz(-3*pi/8)" => "rz(0.3)"))
    zeroed = with_zeroed_perturbation(
        perturbed;
        perturbation_angle = 0.3,
        expected_count = 1,
    )
    original_gates = reduce(vcat, perturbed.layers)
    zeroed_gates = reduce(vcat, zeroed.layers)

    changed = findall(i -> original_gates[i].angle != zeroed_gates[i].angle, eachindex(original_gates))
    @test changed == [7]
    @test zeroed_gates[7].name == "rz"
    @test zeroed_gates[7].angle == 0.0
    @test_throws ArgumentError with_zeroed_perturbation(
        perturbed;
        perturbation_angle = 0.3,
        expected_count = 2,
    )
end
