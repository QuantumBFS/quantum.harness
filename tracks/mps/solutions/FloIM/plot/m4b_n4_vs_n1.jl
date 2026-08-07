# M4b 对比图：N=4 链 vs N=1 单体的 j̄(ω)（ω_d=2.5, J=0.5, h_x=0.5, h_z=0.3, A=1）
# 输入：results/20260729-augmps-m4b/jbar_{N1,N4}_wd2.5.csv
# 输出：同目录 m4b_n4_vs_n1.png
# 用法：julia --project=tracks/mps/env_floquet tracks/mps/solutions/plot/m4b_n4_vs_n1.jl

using Plots
using DelimitedFiles

const OUT = joinpath(@__DIR__, "..", "..", "results", "20260729-augmps-m4b")

d1 = readdlm(joinpath(OUT, "jbar_N1_wd2.5.csv"), Float64)
d4 = readdlm(joinpath(OUT, "jbar_N4_wd2.5.csv"), Float64)
w = d1[:, 1]

p1 = plot(w[w.<=12], d1[w.<=12, 2]; line=(1.6, :solid, :black), label="N=1 (single spin)",
          xlabel="ω", ylabel="j̄(ω)", title="N=1: Ī=0.029, c_1=0.028", titlefontsize=10, ylim=(0, 0.14))
plot!(p1, w[w.<=12], d4[w.<=12, 2]; line=(1.4, :dash, :red), label="N=4 chain (J=0.5)")

p2 = plot(w[w.<=12], d4[w.<=12, 2]; line=(1.6, :solid, :red), label="N=4 chain (J=0.5)",
          xlabel="ω", ylabel="j̄(ω)", title="N=4: Ī=0.066, c_1=0.0024", titlefontsize=10, ylim=(0, 0.14))
plot!(p2, w[w.<=12], d1[w.<=12, 2]; line=(1.4, :dash, :black), label="N=1 (single spin)")

fig = plot(p1, p2; layout=(1, 2), size=(900, 360), margin=5Plots.mm)
savefig(fig, joinpath(OUT, "m4b_n4_vs_n1.png"))
println("saved: ", joinpath(OUT, "m4b_n4_vs_n1.png"))
