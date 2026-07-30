using JSON
using SHA
using TOML

@testset "ED fixture provenance and normalization are frozen" begin
    fixture_path = joinpath(@__DIR__, "fixtures", "ed_reference.json")
    config_path = joinpath(@__DIR__, "..", "config", "ed_validation.toml")
    config = TOML.parsefile(config_path)
    rows = JSON.parsefile(fixture_path)

    @test bytes2hex(SHA.sha256(read(fixture_path))) == config["reference_sha256"]
    @test config["source"] == "docs/challenge-148-route-b-ed-baseline.md"
    @test config["hamiltonian"] ==
          "H=-J sum_<ij> sigma_z(i)sigma_z(j)-h sum_i sigma_x(i)"
    @test config["omega_g"] == "beta*N"
    @test [(row["lattice"], row["L"]) for row in rows] ==
          [("honeycomb", 2), ("honeycomb", 2), ("honeycomb", 2),
           ("triangle", 3), ("triangle", 3), ("triangle", 3)]
    @test all(row["worm_return"] > 0 for row in rows)
end
