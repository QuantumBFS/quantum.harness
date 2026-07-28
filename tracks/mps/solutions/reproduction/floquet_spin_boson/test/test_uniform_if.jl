using Test
using UniformTEMPO

const CACHE_TEST_METADATA = Dict(
    "adapter_schema" => "uniform-if-adapter-v1",
    "uniformtempo_revision" => "test-revision",
    "julia_version" => "test-julia",
    "exact_dt_bits" => bitstring(0.1),
    "compression_tolerance" => 1.0e-7,
    "bath" => Dict("alpha" => 0.05, "omega_c" => 2.5),
    "coupling_operator" => "sigma_z",
)

function fixture_adapter(; metadata=CACHE_TEST_METADATA, value=0.0)
    q = fill(ComplexF64(value), 2, 4, 2, 4)
    return UniformIFAdapter(q, ComplexF64[1, 0], ComplexF64[1, 0], metadata)
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
    metadata = uniform_if_metadata(SpinBosonModel(), 0.1, 1.0e-7;
                                   uniformtempo_revision="test-revision")
    @test metadata["exact_dt_bits"] == bitstring(0.1)
    @test metadata["bath"]["alpha_bits"] == bitstring(0.05)
    @test metadata["coupling_operator"] == "sigma_z"
    @test metadata["adapter_schema"] == "uniform-if-adapter-v1"
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
