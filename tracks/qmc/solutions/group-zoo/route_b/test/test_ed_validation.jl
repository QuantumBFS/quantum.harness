using JSON

const ED_FIXTURE = JSON.parsefile(joinpath(@__DIR__, "fixtures", "ed_reference.json"))

@testset "ED comparison rejects empty and incomplete results" begin
    empty_report = compare_ed(Dict{String,Any}(), ED_FIXTURE[1])
    @test empty_report.status == :insufficient_samples
    @test !empty_report.production_eligible

    incomplete = Dict("energy" => ED_FIXTURE[1]["energy"])
    @test compare_ed(incomplete, ED_FIXTURE[1]).status == :insufficient_samples
end

@testset "ED comparison accepts a synthetic within-tolerance result" begin
    reference = ED_FIXTURE[1]
    passing = Dict{String,Any}(
        "energy" => reference["energy"], "energy_stderr" => 1e-4,
        "energy_ess" => 64,
        "mx" => reference["mx"], "mx_stderr" => 1e-4,
        "mx_ess" => 64,
        "bond" => reference["bond"], "bond_stderr" => 1e-4,
        "bond_ess" => 64,
        "worm_return" => reference["worm_return"], "worm_return_stderr" => 1e-4,
        "worm_return_ess" => 64,
    )
    report = compare_ed(passing, reference)
    @test report.status == :pass
    @test report.production_eligible
    @test isempty(report.failures)

    failing = copy(passing)
    failing["mx"] = reference["mx"] + 0.1
    @test compare_ed(failing, reference).status == :fail

    low_ess = copy(passing)
    low_ess["worm_return_ess"] = 19
    low_ess_report = compare_ed(low_ess, reference)
    @test low_ess_report.status == :insufficient_samples
    @test low_ess_report.failures == ["worm_return_ess"]
end
