if !isdefined(@__MODULE__, :BPTNRunner)
    include(joinpath(@__DIR__, "..", "src", "BPTNRunner.jl"))
end

@testset "norm diagnostic is disabled when TNQS normalizes local tensors" begin
    normalized = BPTNRunner.norm_diagnostic(true)
    @test !normalized.available
    @test isnan(normalized.defect)
    @test normalized.reason == "local_tensor_normalization_drops_global_scale"

    scale_preserving = BPTNRunner.norm_diagnostic(false, 0.999)
    @test scale_preserving.available
    @test scale_preserving.defect ≈ 0.001
    @test scale_preserving.reason == "available"
end
