function window(hc, stderr; status="pass")
    return (status=status, hc=hc, stderr_hc=stderr)
end

@testset "universal regression gates keep statistical and window errors separate" begin
    chain = evaluate_regression_gate(
        [window(1.00010, 3e-5), window(1.00014, 4e-5), window(1.00006, 5e-5)];
        reference=1.0,
        absolute_tolerance=2e-4,
        sigma_multiplier=0.0,
        declared_systematic=4e-5,
    )
    @test chain.status == "pass"
    @test chain.reference_difference ≈ 1e-4
    @test chain.statistical_stderr == 3e-5
    @test chain.observed_window_shift ≈ 4e-5
    @test chain.combined_stderr ≈ 5e-5

    square = evaluate_regression_gate(
        [window(3.04442, 4e-5), window(3.04440, 4e-5)];
        reference=3.044330,
        absolute_tolerance=5e-5,
        sigma_multiplier=3.0,
        declared_systematic=3e-5,
    )
    @test square.status == "pass"
    @test square.acceptance_threshold ≈ 1.5e-4
end

@testset "failed or unstable fit windows fail closed" begin
    unstable = evaluate_regression_gate(
        [window(1.0, 2e-5), window(1.0002, 2e-5)];
        reference=1.0,
        absolute_tolerance=2e-4,
        sigma_multiplier=0.0,
        declared_systematic=5e-5,
    )
    @test unstable.status == "fail"
    @test !unstable.window_stable

    failed = evaluate_regression_gate(
        [window(1.0, 2e-5), window(nothing, nothing; status="fail")];
        reference=1.0,
        absolute_tolerance=2e-4,
        sigma_multiplier=0.0,
        declared_systematic=5e-5,
    )
    @test failed.status == "fail"
    @test failed.failed_windows == 1
end
