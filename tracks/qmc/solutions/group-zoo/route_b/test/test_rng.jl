@testset "counter RNG is reproducible and has a frozen stream" begin
    rng = CounterRNG(0)
    @test [rand_u64!(rng) for _ in 1:3] == UInt64[
        0xe220a8397b1dcdaf,
        0x6e789e6aa1b965f4,
        0x06c45d188009454f,
    ]

    left = CounterRNG(0x148)
    right = CounterRNG(0x148)
    @test [rand_float!(left) for _ in 1:20] ==
          [rand_float!(right) for _ in 1:20]
    @test all(0.0 <= rand_float!(left) < 1.0 for _ in 1:100)
    @test all(1 <= rand_int!(right, 7) <= 7 for _ in 1:100)
    @test_throws ArgumentError rand_int!(right, 0)
end

@testset "counter RNG resumes from one UInt64" begin
    rng = CounterRNG(99)
    rand_u64!(rng)
    saved = rng.state
    suffix = [rand_u64!(rng) for _ in 1:10]
    resumed = CounterRNG(saved)
    @test [rand_u64!(resumed) for _ in 1:10] == suffix
end
