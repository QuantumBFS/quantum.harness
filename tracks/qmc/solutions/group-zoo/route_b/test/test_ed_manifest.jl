using JSON
using TOML

@testset "ED validation manifest is deterministic and non-production" begin
    config = TOML.parsefile(joinpath(@__DIR__, "..", "config", "ed_validation.toml"))
    rows = JSON.parsefile(joinpath(@__DIR__, "fixtures", "ed_reference.json"))
    first = make_ed_validation_tasks(config, rows)
    second = make_ed_validation_tasks(config, rows)

    @test length(first) == 24
    @test canonical_task_json.(first) == canonical_task_json.(second)
    @test length(unique(task_hash.(first))) == 24
    @test all(task.purpose == :ed_validation for task in first)
    @test Set((task.lattice, task.L, task.beta_over_L) for task in first) ==
          Set((Symbol(row["lattice"]), row["L"], row["c"]) for row in rows)
    @test count(task -> task.seed == UInt64(148001), first) == 1
end
