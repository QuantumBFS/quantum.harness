@testset "Huang continuous-time log weight" begin
    @test log_weight(1.0, 2.0, 3, 4, 5.0) == 10.0
    @test log_weight(2.0, 0.0, 2, 1, 0.0) == 3log(2.0)
    @test log_ratio(
        1.0;
        delta_kinks=0,
        h=2.0,
        delta_spin_time=-0.25,
    ) == -0.5
    @test log_ratio(
        2.0;
        delta_kinks=-2,
        h=-0.5,
        delta_spin_time=3.0,
    ) == -2log(2.0) - 1.5
end

@testset "log-domain Metropolis probability is stable" begin
    @test metropolis_from_logratio(1000.0) == 1.0
    @test metropolis_from_logratio(0.0) == 1.0
    @test metropolis_from_logratio(-1000.0) == 0.0
    @test metropolis_from_logratio(log(0.25)) == 0.25
    @test_throws ArgumentError metropolis_from_logratio(NaN)
    @test_throws ArgumentError metropolis_from_logratio(Inf)
    @test_throws ArgumentError metropolis_from_logratio(-Inf)
end

@testset "invalid physical weight inputs are rejected" begin
    @test_throws ArgumentError log_weight(0.0, 1.0, 0, 0, 1.0)
    @test_throws ArgumentError log_weight(-1.0, 1.0, 0, 0, 1.0)
    @test_throws ArgumentError log_weight(1.0, 1.0, -1, 0, 1.0)
    @test_throws ArgumentError log_weight(1.0, 1.0, 0, -1, 1.0)
    @test_throws ArgumentError log_weight(1.0, Inf, 0, 0, 1.0)
    @test_throws ArgumentError log_weight(1.0, 1.0, 0, 0, NaN)
    @test_throws ArgumentError log_ratio(
        0.0;
        delta_kinks=0,
        h=1.0,
        delta_spin_time=1.0,
    )
end
