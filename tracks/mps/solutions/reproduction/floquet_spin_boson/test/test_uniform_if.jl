using Test
using UniformTEMPO
using JLD2

const CACHE_TEST_METADATA = uniform_if_metadata(SpinBosonModel(), 0.1, 1.0e-7;
                                                temperature=0.0)

function fixture_adapter(; metadata=CACHE_TEST_METADATA, value=0.0,
                         convergence_metadata=Dict("iterations" => 3, "residual" => 1.0e-8))
    q = fill(ComplexF64(value), 2, 4, 2, 4)
    return UniformIFAdapter(q, ComplexF64[1, 0], ComplexF64[1, 0], metadata;
                            convergence_metadata=convergence_metadata)
end

@testset "Uniform IF adapter validates UniformPTMPO fields and shapes" begin
    pt = UniformPTMPO(2, 0.1)
    adapter = adapt_uniform_pt(pt; metadata=CACHE_TEST_METADATA)
    @test size(adapter.q) == (1, 4, 1, 4)
    @test adapter.v_left == ComplexF64[1]
    @test adapter.v_right == ComplexF64[1]

    @test_throws ArgumentError UniformIFAdapter(zeros(ComplexF64, 2, 4, 3, 4),
                                                ComplexF64[1, 0], ComplexF64[1, 0],
                                                CACHE_TEST_METADATA)
    @test_throws ArgumentError UniformIFAdapter(zeros(ComplexF64, 2, 4, 2, 3),
                                                ComplexF64[1, 0], ComplexF64[1, 0],
                                                CACHE_TEST_METADATA)
    @test_throws ArgumentError UniformIFAdapter(zeros(ComplexF64, 1, 9, 1, 9),
                                                ComplexF64[1], ComplexF64[1],
                                                CACHE_TEST_METADATA)
end

@testset "Uniform IF key preserves the exact dt bit pattern" begin
    dt = 0.1
    near_dt = nextfloat(dt)
    key = uniform_if_key(CACHE_TEST_METADATA)
    near_key = uniform_if_key(merge(CACHE_TEST_METADATA,
                                    Dict("exact_dt_bits" => bitstring(near_dt))))
    @test key != near_key
    @test key == uniform_if_key(copy(CACHE_TEST_METADATA))
end

@testset "Uniform IF provenance records fixed bath and runtime versions" begin
    metadata = uniform_if_metadata(SpinBosonModel(), 0.1, 1.0e-7)
    @test metadata["exact_dt_bits"] == bitstring(0.1)
    @test metadata["bath"]["alpha_bits"] == bitstring(0.05)
    @test metadata["coupling_operator"] == "sigma_z"
    @test metadata["adapter_schema"] == "uniform-if-adapter-v2"
end

@testset "Uniform IF cache rejects incompatible provenance" begin
    mktempdir() do cache_dir
        expected = copy(CACHE_TEST_METADATA)
        incompatible = merge(expected, Dict("uniformtempo_revision" => "other-revision"))
        path = uniform_if_cache_path(cache_dir, expected)
        atomic_save(path, fixture_adapter(metadata=incompatible))
        @test_throws ArgumentError load_or_build_uniform_if(cache_dir, expected,
            () -> error("a provenance mismatch must not rebuild the cache"))
    end
end

@testset "Uniform IF cache reuses completed data and preserves it on interrupted replacement" begin
    mktempdir() do cache_dir
        builds = Ref(0)
        builder = function ()
            builds[] += 1
            return fixture_adapter()
        end

        first = load_or_build_uniform_if(cache_dir, CACHE_TEST_METADATA, builder)
        payload = JLD2.load(uniform_if_cache_path(cache_dir, CACHE_TEST_METADATA))
        @test payload["achieved_chi"] == 2
        @test payload["convergence_metadata"] == first.convergence_metadata
        reused = load_or_build_uniform_if(cache_dir, CACHE_TEST_METADATA, builder)
        @test builds[] == 1
        @test reused.q == first.q

        path = uniform_if_cache_path(cache_dir, CACHE_TEST_METADATA)
        @test_throws ErrorException atomic_save(path, fixture_adapter(value=7.0);
                                                before_rename=() -> error("interrupted"))
        recovered = load_or_build_uniform_if(cache_dir, CACHE_TEST_METADATA, builder)
        @test builds[] == 1
        @test recovered.q == first.q

        rebuilt = load_or_build_uniform_if(cache_dir, CACHE_TEST_METADATA, builder; rebuild=true)
        @test builds[] == 2
        @test rebuilt.q == first.q
    end
end

@testset "Uniform IF adapter authenticates process-tensor provenance" begin
    model = SpinBosonModel()
    metadata = uniform_if_metadata(model, 0.1, 1.0e-7)
    @test_throws ArgumentError adapt_uniform_pt(UniformPTMPO(2, nextfloat(0.1)); metadata=metadata)
    @test_throws ArgumentError adapt_uniform_pt(UniformPTMPO(3, 0.1); metadata=metadata)
    @test_throws ArgumentError adapt_uniform_pt(UniformPTMPO(2, 0.1);
                                                metadata=merge(metadata,
                                                    Dict("uniformtempo_revision" => "not-installed")))
end

@testset "Uniform IF metadata keys every construction control" begin
    model = SpinBosonModel()
    metadata = uniform_if_metadata(model, 0.1, 1.0e-7)
    @test metadata["temperature_bits"] == bitstring(0.0)
    for field in ("auto_nc", "n_c", "truncation", "cap_rank", "max_rank",
                  "low_rank_svd", "svd_filtering_tolerance_bits")
        @test haskey(metadata["build"], field)
    end
    base_key = uniform_if_key(metadata)
    @test base_key != uniform_if_key(uniform_if_metadata(model, 0.1, 1.0e-7; temperature=0.25))
    for build in (
        UniformIFBuildSettings(auto_nc=false),
        UniformIFBuildSettings(n_c=17),
        UniformIFBuildSettings(truncation=:abs),
        UniformIFBuildSettings(cap_rank=23),
        UniformIFBuildSettings(max_rank=29),
        UniformIFBuildSettings(low_rank_svd=true),
        UniformIFBuildSettings(svd_filtering_tolerance=1.0e-9),
    )
        @test base_key != uniform_if_key(uniform_if_metadata(model, 0.1, 1.0e-7; build=build))
    end
end
