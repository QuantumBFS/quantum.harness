isdefined(@__MODULE__, :validate_chain_mapping_artifact) ||
    include(joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl"))

const VALIDATED_CHAIN_FIXTURE_BATH_SHA256 = (
    "7d894928d95481cff0c5a8f47592681db1e9bae8731f1a16bb1b83fc310a8b4f",
    "acada4ceb615f6f9ab020376e0ce1e2c529011c0606b6e5178251ce9e6753395",
    "01f498d95a6e22db27ff8992001edd896d48f3bbc4563a1477fa5371e2c46931",
    "fd790a29ad2c3fe5e840c7ee260dbcf96b50ec434b9ef01065f1bfa1ba231cdf",
    "818dc73dffeb851961e8cb6944df92a45423d9ee8893bd8b9b3d08e4135323ba",
    "57f6b6295f9cb0cba9fc5463a004cf1ed37a846d7229bd21343fff74292cbea4",
)
const VALIDATED_CHAIN_FIXTURE_MAPPING_SHA256 = (
    "cb9fc9fbb83e7d6538e4f08f2dee0d218787946006f1aa4437bad23d55e8ba4a",
    "30ba94076c1a5828da8749bc79dc495b59db2ae1e49d99f2db928e8fd2a22c09",
    "8041184dd33c467d361218a157fafdb027290adf941312262d550f44a23318fb",
    "79139728b461f34bce98d6d3fb664cbebabd2f22090e06ad7ab8f3f38cc3f81c",
    "5e21d93e712fa611fe7bda482f19b6ddce0aea295770804ed27e3cfcaf74eb18",
    "9c27f3b20aa5891b3aa393e45ac012ca39eebba974f3e417268d7ef0c48a6ed3",
)

function validated_chain_fixture_artifacts(n_bath::Int)
    n_bath in 1:6 ||
        throw(ArgumentError("canonical chain fixture n_bath must be in 1:6"))
    root = joinpath(@__DIR__, "fixtures", "qn_chain")
    bath_json = read(joinpath(root, "bath-n$n_bath.json"), String)
    mapping_json = read(joinpath(root, "mapping-n$n_bath.json"), String)
    bath_artifact = strict_json_read(bath_json, "fixture bath artifact")
    mapping_artifact =
        strict_json_read(mapping_json, "fixture chain mapping artifact")
    bath_artifact["sha256"] ==
        VALIDATED_CHAIN_FIXTURE_BATH_SHA256[n_bath] ||
        error("checked-in bath fixture digest pin mismatch")
    mapping_artifact["sha256"] ==
        VALIDATED_CHAIN_FIXTURE_MAPPING_SHA256[n_bath] ||
        error("checked-in mapping fixture digest pin mismatch")
    validate_bath_artifact(
        bath_artifact, bath_json, authoritative_model_definition()
    )
    return (; bath_artifact, bath_json, mapping_artifact, mapping_json)
end

function validated_chain_fixture(; n_bath = 1)
    n_bath isa Integer && !(n_bath isa Bool) ||
        throw(ArgumentError("n_bath must be an integer"))
    artifacts = validated_chain_fixture_artifacts(Int(n_bath))
    return validate_chain_mapping_artifact(
        artifacts.mapping_artifact,
        artifacts.mapping_json,
        artifacts.bath_artifact,
    )
end
