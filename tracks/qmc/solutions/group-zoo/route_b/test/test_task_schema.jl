function tiny_task(; seed=148, bins=8)
    TaskSpec(
        lattice=:chain,
        L=3,
        J=1.0,
        h=0.3,
        beta_over_L=1.0,
        seed=seed,
        kernel=:huang,
        tau_multipliers=(1.0, 1.0, 1.0),
        warmup_bins=1,
        retained_bins=bins,
        visits_per_bin=20,
        checkpoint_every=2,
        purpose=:validation,
    )
end

@testset "task canonicalization and hashes" begin
    task = tiny_task()
    @test task.beta == 3.0
    encoded = canonical_task_json(task)
    @test task_hash(task) == task_hash(parse_task(encoded))
    @test length(task_hash(task)) == 64
    @test task_hash(task) != task_hash(tiny_task(seed=149))
    @test_throws ArgumentError tiny_task(bins=0)
end

@testset "strict task fields reject production ambiguity" begin
    @test_throws ArgumentError TaskSpec(
        lattice=:chain, L=3, J=1.0, h=0.3, beta_over_L=1.0, seed=1,
        kernel=:cluster, tau_multipliers=(1.0, 1.0, 1.0), warmup_bins=1,
        retained_bins=2, visits_per_bin=20, checkpoint_every=2,
        purpose=:validation,
    )
    @test_throws ArgumentError TaskSpec(
        lattice=:chain, L=3, J=1.0, h=0.3, beta_over_L=1.0, seed=1,
        kernel=:huang, tau_multipliers=(1.0, 1.0, 1.0), warmup_bins=1,
        retained_bins=2, visits_per_bin=20, checkpoint_every=2,
        purpose=:production,
    )
end
