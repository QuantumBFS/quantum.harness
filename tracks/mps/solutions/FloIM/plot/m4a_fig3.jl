# M4a 复刻对照图：我们的 j̄(ω) 连续谱 vs 作者 Zenodo CSV（图 3 六个参数组）
# 输入：tracks/mps/results/20260729-augmps-m4a/jbar_{kind}_wd{ωd}.csv（w, ours, ref）
# 输出：同目录 m4a_fig3_comparison.png
# 用法：julia --project=tracks/mps/env_floquet tracks/mps/solutions/plot/m4a_fig3.jl

using Plots
using DelimitedFiles
using LinearAlgebra
using Printf

const OUT = joinpath(@__DIR__, "..", "..", "results", "20260729-augmps-m4a")

sets = [
    ("longitudinal", 2.5), ("longitudinal", 5.0), ("longitudinal", 10.0),
    ("transversal", 1.0), ("transversal", 1.5), ("transversal", 2.0),
]

plts = []
for (kind, ωd) in sets
    d = readdlm(joinpath(OUT, @sprintf("jbar_%s_wd%s.csv", kind, ωd)), Float64)
    w, o, r = d[:, 1], d[:, 2], d[:, 3]
    mask = w .<= 12.0
    l2 = norm(o[mask] .- r[mask]) / norm(r[mask])
    p = plot(w[mask], r[mask]; line=(1.6, :solid, :black), label="authors (χ=235)",
             xlabel="ω", ylabel="j̄(ω)", title=@sprintf("%s, ω_d=%s, L2=%.1f%%", kind, ωd, 100l2),
             titlefontsize=9)
    plot!(p, w[mask], o[mask]; line=(1.2, :dash, :red), label="ours (χ_b=41)")
    push!(plts, p)
end

fig = plot(plts...; layout=(2, 3), size=(1050, 560), margin=4Plots.mm)
savefig(fig, joinpath(OUT, "m4a_fig3_comparison.png"))
println("saved: ", joinpath(OUT, "m4a_fig3_comparison.png"))
