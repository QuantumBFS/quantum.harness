@testset "blocking and initial-positive autocorrelation" begin
    x = vcat(fill(0.0, 100), fill(1.0, 100))
    stats = binned_stats(x; binsize=20)
    @test stats.nbins == 10
    @test stats.mean == 0.5
    @test stats.stderr > 0
    @test stats.tau_int >= 0.5
    @test stats.ess <= stats.nbins
    @test stats.binsize == 20

    constant = binned_stats(fill(2.0, 40); binsize=4)
    @test constant.mean == 2.0
    @test constant.stderr == 0.0
    @test constant.tau_int == 0.5
    @test constant.ess == constant.nbins
end

@testset "statistics reject unusable series" begin
    @test_throws ArgumentError binned_stats(Float64[]; binsize=4)
    @test_throws ArgumentError binned_stats([1.0, NaN, 2.0]; binsize=1)
    @test_throws ArgumentError binned_stats(collect(1.0:5.0); binsize=2)
    @test_throws ArgumentError binned_stats([1.0, 2.0]; binsize=0)
end
