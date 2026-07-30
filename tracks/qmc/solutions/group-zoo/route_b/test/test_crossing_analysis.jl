function synthetic_crossings(; hc, Rc, yt, yi)
    rows = NamedTuple[]
    for L in (8, 12, 16, 24, 32), anchor in (-0.8, 0.0, 0.8), replica in 1:8
        h = hc + anchor / L^yt
        exact = Rc + 0.31anchor - 0.04anchor^2 + 0.08L^yi
        noise = 0.002 * sin(17replica + 3L + 5anchor)
        push!(rows, (L=L, h=h, replica=replica, value=exact + noise, stderr=0.002))
    end
    return rows
end

@testset "wrapping scaling recovers a hand-derived critical point" begin
    fixture = synthetic_crossings(hc=1.0, Rc=0.42, yt=1.0, yi=-1.0)
    fit = fit_wrapping_scaling(
        fixture; Lmin=12, corrections=1, yt=1.0, yi=-1.0, hc_bounds=(0.95, 1.05),
    )
    @test fit.status == :pass
    @test abs(fit.hc - 1.0) < 3fit.stderr_hc
    @test fit.pvalue > 0.05
    @test fit.Lmin == 12
    @test fit.corrections == 1

    raised_window = fit_wrapping_scaling(
        fixture; Lmin=16, corrections=0, yt=1.0, yi=-1.0, hc_bounds=(0.95, 1.05),
    )
    @test raised_window.status == :pass
    @test abs(raised_window.hc - 1.0) < 1e-3

    ratio = bootstrap_ratio([fit, fit]; replicas=200, seed=149)
    @test ratio.n_success == 200
    @test abs(ratio.mean - 1.0) < 3ratio.stderr

    whole_replica = bootstrap_scaling(
        fixture;
        replicas=50,
        seed=150,
        Lmin=12,
        corrections=1,
        yt=1.0,
        yi=-1.0,
        hc_bounds=(0.95, 1.05),
    )
    @test whole_replica.n_success == 50
    @test whole_replica.n_failed == 0
    @test abs(whole_replica.mean_hc - 1.0) < 3whole_replica.stderr_hc
end

@testset "wrapping fits reject unusable covariance inputs" begin
    fixture = synthetic_crossings(hc=1.0, Rc=0.42, yt=1.0, yi=-1.0)
    bad = copy(fixture)
    bad[1] = merge(bad[1], (stderr=0.0,))
    @test_throws ArgumentError fit_wrapping_scaling(
        bad; Lmin=12, corrections=1, yt=1.0, yi=-1.0, hc_bounds=(0.95, 1.05),
    )
    @test_throws ArgumentError fit_wrapping_scaling(
        fixture; Lmin=64, corrections=1, yt=1.0, yi=-1.0, hc_bounds=(0.95, 1.05),
    )

    failed = fit_window_record(
        fixture; Lmin=64, corrections=1, yt=1.0, yi=-1.0, hc_bounds=(0.95, 1.05),
    )
    @test failed.status == "fail"
    @test failed.Lmin == 64
    @test failed.corrections == 1
    @test occursin("insufficient rows", failed.error)
end
