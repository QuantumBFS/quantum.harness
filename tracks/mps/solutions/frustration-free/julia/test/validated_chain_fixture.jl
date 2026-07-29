isdefined(Main, :validate_chain_mapping_artifact) ||
    include(joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl"))

function validated_chain_fixture(; n_bath = 1, gamma = 0.1, bandwidth = 1.0)
    solution_dir = normpath(joinpath(@__DIR__, "..", ".."))
    return mktempdir() do directory
        bath_path = joinpath(directory, "bath.json")
        mapping_path = joinpath(directory, "chain-mapping.json")
        script = """
import sys
sys.path.insert(0, sys.argv[1])
import bath
import chain_mapping

bath_artifact = bath.write_bath_json(
    sys.argv[2],
    gamma=float(sys.argv[5]),
    bandwidth=float(sys.argv[6]),
    n_bath=int(sys.argv[4]),
    frequency_grid=[-1.0, 0.0, 1.0],
)
chain_mapping.write_chain_mapping_json(
    sys.argv[3], bath_artifact=bath_artifact
)
"""
        command = `uv run --project=$solution_dir --frozen python -c $script $solution_dir $bath_path $mapping_path $n_bath $gamma $bandwidth`
        run(command)
        bath_json = read(bath_path, String)
        mapping_json = read(mapping_path, String)
        bath_artifact = strict_json_read(bath_json, "fixture bath artifact")
        mapping_artifact =
            strict_json_read(mapping_json, "fixture chain mapping artifact")
        return validate_chain_mapping_artifact(
            mapping_artifact, mapping_json, bath_artifact
        )
    end
end
