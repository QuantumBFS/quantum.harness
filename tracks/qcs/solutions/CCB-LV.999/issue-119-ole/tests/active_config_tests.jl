using TOML

@testset "active configuration changes only the audited L=6 instance fields" begin
    config_dir = joinpath(@__DIR__, "..", "configs")
    baseline_path = joinpath(config_dir, "baseline-49x648.toml")
    active_path = joinpath(config_dir, "active-49x1296.toml")

    @test isfile(active_path)
    if isfile(active_path)
        baseline = TOML.parsefile(baseline_path)
        active = TOML.parsefile(active_path)

        @test active["simulation"] == baseline["simulation"]
        @test active["software"] == baseline["software"]
        @test active["problem"]["active_qubits"] == baseline["problem"]["active_qubits"]
        @test active["problem"]["observable_qubits"] ==
              baseline["problem"]["observable_qubits"]
        @test active["problem"]["qasm_register_size"] ==
              baseline["problem"]["qasm_register_size"]
        @test active["problem"]["b"] == baseline["problem"]["b"]
        @test active["problem"]["delta"] == baseline["problem"]["delta"]
        @test active["problem"]["perturbation"] == baseline["problem"]["perturbation"]

        @test active["problem"]["name"] ==
              "operator_loschmidt_echo_49x1296"
        @test active["problem"]["run_directory"] == "active-49x1296"
        @test active["problem"]["L"] == 6
        @test active["problem"]["layers"] == 145
        @test active["problem"]["barriers"] == 145
        @test active["problem"]["cz_gates"] == 1296
        @test active["problem"]["qasm_sha256"] ==
              "3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0"
        @test active["problem"]["qasm_bytes"] == 321769
        @test active["problem"]["qasm_git_blob"] ==
              "829be362d1526ea9afe8e13fe1594e2e00eaa2e2"
        @test active["problem"]["issue_attachment_qasm"]["format"] == "OpenQASM 2.0"
        @test active["problem"]["issue_attachment_qasm"]["sha256"] ==
              "d237a273c7cc233e9d64039ad06613af17eb472b19bda12f4ce458b9c4541645"
        @test active["problem"]["issue_attachment_qasm"]["bytes"] == 297926
        @test active["problem"]["issue_attachment_qasm"]["canonical_tnqs_equal"] == true
    end
end
