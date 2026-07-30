using Printf, Statistics, LinearAlgebra, DelimitedFiles, Random

const EIG_DIR = "/mnt/c/Users/Public/self_dual_results_ly20/self_dual_results"
const SVD_DIR = dirname(abspath(@__FILE__)) * "/results"

# Read Ly=20 eigenvalue data (columns: sample,f_amp,f_eig,f_sv,f_det,gamma0_eig,gamma0_sv,gamma0_det,n_sp,d1,d2,d3)
function read_eig_csv(filepath)
    data = readdlm(filepath, ',', skipstart=1)
    g0sv = Float64.(data[:, 7])   # gamma0_sv = log(sv_max)/Ly
    g0eig = Float64.(data[:, 6])  # gamma0_eig = log(lambda_max)/Ly
    d1 = Float64.(data[:, 10])
    d2 = Float64.(data[:, 11])
    d3 = Float64.(data[:, 12])
    return g0sv, g0eig, d1, d2, d3
end

# Read Ly=10 SVD data (columns: sample,gamma0,...,gamma7,Phi_L,d1,...,d7)
function read_svd_csv(filepath)
    data = readdlm(filepath, ',', skipstart=1)
    g0 = Float64.(data[:, 2])     # gamma0 = log(sv_max)/Ly
    d1 = Float64.(data[:, 11])
    d2 = Float64.(data[:, 12])
    d3 = Float64.(data[:, 13])
    d4 = Float64.(data[:, 14])
    return g0, d1, d2, d3, d4
end

function mean_err(v)
    m = mean(v)
    return m, std(v)/sqrt(length(v))
end

function fit_w(A, y, w)
    W = Diagonal(w)
    sol = (A' * W * A) \ (A' * W * y)
    chi2 = sum(w .* (A * sol - y) .^ 2)
    return sol, chi2
end

pair_c(L1, L2, f1, f2) = 6 / pi * L1^2 * L2^2 * (f2 - f1) / (L2^2 - L1^2)

sep = "=" ^ 70
println(sep)
println("Self-Dual Point Final Analysis (theta=pi/4)")
println("Convention: Phi = -gamma0 (amplitude/single-layer, gives c=1/2 for Ising)")
println(sep)

# ====================================================================
# Collect data
# ====================================================================
Ls_all = [4, 6, 8, 10, 12]

# Ly=20 eigenvalue data
println("\n=== Ly=20*L Eigenvalue Data ===")
eig_data = Dict{Int, NamedTuple}()
for L in Ls_all
    fp = joinpath(EIG_DIR, "self_dual_eig_L$(L).csv")
    if !isfile(fp)
        println("  L=$L: NOT FOUND")
        continue
    end
    g0sv, g0eig, d1, d2, d3 = read_eig_csv(fp)
    n = length(g0sv)
    phi_sv_m, phi_sv_e = mean_err(-g0sv)
    phi_eig_m, phi_eig_e = mean_err(-g0eig)
    eig_data[L] = (n=n, g0sv=-g0sv, g0eig=-g0eig, phi_sv=phi_sv_m, phi_sv_e=phi_sv_e,
                   phi_eig=phi_eig_m, phi_eig_e=phi_eig_e,
                   d1=d1, d2=d2, d3=d3, d1_m=mean(d1), d2_m=mean(d2), d3_m=mean(d3))
    @printf("  L=%-3d n=%-4d  Phi_sv=%.6f+/-%.6f  Phi_eig=%.6f+/-%.6f  d1=%.4f d2=%.4f d3=%.4f\n",
            L, n, phi_sv_m, phi_sv_e, phi_eig_m, phi_eig_e, mean(d1), mean(d2), mean(d3))
end

# Ly=10 SVD data
println("\n=== Ly=10*L SVD Data ===")
svd_data = Dict{Int, NamedTuple}()
for L in Ls_all
    fp = joinpath(SVD_DIR, "self_dual_opt_L$(L).csv")
    if !isfile(fp)
        println("  L=$L: NOT FOUND")
        continue
    end
    g0, d1, d2, d3, d4 = read_svd_csv(fp)
    n = length(g0)
    phi_m, phi_e = mean_err(-g0)
    svd_data[L] = (n=n, g0=-g0, phi=phi_m, phi_e=phi_e,
                   d1=d1, d2=d2, d3=d3, d4=d4,
                   d1_m=mean(d1), d2_m=mean(d2), d3_m=mean(d3), d4_m=mean(d4))
    @printf("  L=%-3d n=%-4d  Phi=%.6f+/-%.6f  f=%.6f  d1=%.4f d2=%.4f\n",
            L, n, phi_m, phi_e, phi_m/L, mean(d1), mean(d2))
end

# ====================================================================
# c_eff from Ly=20 SVD data (Phi = -gamma0_sv)
# ====================================================================
println("\n" * sep)
println("c_eff from Ly=20 SVD (Phi = -gamma0_sv)")
println(sep)

Ls_eig = sort(collect(keys(eig_data)))
nL_e = length(Ls_eig)
phi_e = [eig_data[L].phi_sv for L in Ls_eig]
phi_e_err = [eig_data[L].phi_sv_e for L in Ls_eig]
ns_e = [eig_data[L].n for L in Ls_eig]
all_g0_e = [eig_data[L].g0sv for L in Ls_eig]

w_e = 1.0 ./ phi_e_err .^ 2

# 3-param fit
A1 = zeros(nL_e, 3)
for i in 1:nL_e
    A1[i,1] = Ls_eig[i]; A1[i,2] = 1.0; A1[i,3] = -pi/(6*Ls_eig[i])
end
sol1, chi21 = fit_w(A1, phi_e, w_e)
@printf("  3-param: c_eff = %.4f (chi2/dof=%.2f/%d)\n", sol1[3], chi21, nL_e-3)

# Pair estimates
println("  Pair estimates:")
for i in 1:nL_e, j in (i+1):nL_e
    cv = pair_c(Ls_eig[i], Ls_eig[j], phi_e[i]/Ls_eig[i], phi_e[j]/Ls_eig[j])
    @printf("    c(%d,%d) = %.4f\n", Ls_eig[i], Ls_eig[j], cv)
end

# Bootstrap
Random.seed!(42)
nboot = 2000
cboot_e = Float64[]
for _ in 1:nboot
    phi_b = [mean(all_g0_e[i][rand(1:ns_e[i], ns_e[i])]) for i in 1:nL_e]
    Ab = zeros(nL_e, 3)
    for i in 1:nL_e
        Ab[i,1] = Ls_eig[i]; Ab[i,2] = 1.0; Ab[i,3] = -pi/(6*Ls_eig[i])
    end
    push!(cboot_e, ((Ab' * Ab) \ (Ab' * phi_b))[3])
end
@printf("  Bootstrap: c_eff = %.4f +/- %.4f\n", mean(cboot_e), std(cboot_e))

# Exclude L=12 (convergence issue)
Ls_no12 = filter(L -> L <= 10, Ls_eig)
nL_n = length(Ls_no12)
phi_n = [eig_data[L].phi_sv for L in Ls_no12]
phi_n_err = [eig_data[L].phi_sv_e for L in Ls_no12]
w_n = 1.0 ./ phi_n_err .^ 2
A1n = zeros(nL_n, 3)
for i in 1:nL_n
    A1n[i,1] = Ls_no12[i]; A1n[i,2] = 1.0; A1n[i,3] = -pi/(6*Ls_no12[i])
end
sol1n, chi21n = fit_w(A1n, phi_n, w_n)
@printf("  3-param (L<=10): c_eff = %.4f (chi2/dof=%.2f/%d)\n", sol1n[3], chi21n, nL_n-3)
println("  Pair estimates (L<=10):")
for i in 1:nL_n, j in (i+1):nL_n
    cv = pair_c(Ls_no12[i], Ls_no12[j], phi_n[i]/Ls_no12[i], phi_n[j]/Ls_no12[j])
    @printf("    c(%d,%d) = %.4f\n", Ls_no12[i], Ls_no12[j], cv)
end

# ====================================================================
# c_eff from Ly=10 SVD data (Phi = -gamma0)
# ====================================================================
println("\n" * sep)
println("c_eff from Ly=10 SVD (Phi = -gamma0)")
println(sep)

Ls_svd = sort(collect(keys(svd_data)))
nL_s = length(Ls_svd)
phi_s = [svd_data[L].phi for L in Ls_svd]
phi_s_err = [svd_data[L].phi_e for L in Ls_svd]
ns_s = [svd_data[L].n for L in Ls_svd]
all_g0_s = [svd_data[L].g0 for L in Ls_svd]

w_s = 1.0 ./ phi_s_err .^ 2

A1s = zeros(nL_s, 3)
for i in 1:nL_s
    A1s[i,1] = Ls_svd[i]; A1s[i,2] = 1.0; A1s[i,3] = -pi/(6*Ls_svd[i])
end
sol1s, chi21s = fit_w(A1s, phi_s, w_s)
@printf("  3-param: c_eff = %.4f (chi2/dof=%.2f/%d)\n", sol1s[3], chi21s, nL_s-3)

println("  Pair estimates:")
for i in 1:nL_s, j in (i+1):nL_s
    cv = pair_c(Ls_svd[i], Ls_svd[j], phi_s[i]/Ls_svd[i], phi_s[j]/Ls_svd[j])
    @printf("    c(%d,%d) = %.4f\n", Ls_svd[i], Ls_svd[j], cv)
end

# Bootstrap
cboot_s = Float64[]
for _ in 1:nboot
    phi_b = [mean(all_g0_s[i][rand(1:ns_s[i], ns_s[i])]) for i in 1:nL_s]
    Ab = zeros(nL_s, 3)
    for i in 1:nL_s
        Ab[i,1] = Ls_svd[i]; Ab[i,2] = 1.0; Ab[i,3] = -pi/(6*Ls_svd[i])
    end
    push!(cboot_s, ((Ab' * Ab) \ (Ab' * phi_b))[3])
end
@printf("  Bootstrap: c_eff = %.4f +/- %.4f\n", mean(cboot_s), std(cboot_s))

# ====================================================================
# Scaling dimensions (Ly=20 data, L=4-10 only, L=12 excluded)
# ====================================================================
println("\n" * sep)
println("Scaling Dimensions (Ly=20 data, L<=10)")
println(sep)

Ls_dim = filter(L -> L <= 10, Ls_eig)
nL_d = length(Ls_dim)

for (dm_arr, de_arr, label) in [
    ([eig_data[L].d1_m for L in Ls_dim], [std(eig_data[L].d1)/sqrt(eig_data[L].n) for L in Ls_dim], "Delta_1"),
    ([eig_data[L].d2_m for L in Ls_dim], [std(eig_data[L].d2)/sqrt(eig_data[L].n) for L in Ls_dim], "Delta_2"),
    ([eig_data[L].d3_m for L in Ls_dim], [std(eig_data[L].d3)/sqrt(eig_data[L].n) for L in Ls_dim], "Delta_3"),
]
    vals_str = join([@sprintf("%.4f", v) for v in dm_arr], ", ")
    # 1/L^2 extrapolation
    wd = 1.0 ./ de_arr .^ 2
    Ad = zeros(nL_d, 2)
    for i in 1:nL_d
        Ad[i,1] = 1.0; Ad[i,2] = 1.0/Ls_dim[i]^2
    end
    sold, chi2d = fit_w(Ad, dm_arr, wd)
    @printf("  %s: Delta_inf = %.5f (chi2/dof=%.2f/%d)  vals=[%s]\n",
            label, sold[1], chi2d, nL_d-2, vals_str)
end

# Also show L=12 values (noted as unreliable)
if 12 in Ls_eig
    println("\n  L=12 values (NOT extrapolated, convergence issue):")
    @printf("    d1=%.4f  d2=%.4f  d3=%.4f\n", eig_data[12].d1_m, eig_data[12].d2_m, eig_data[12].d3_m)
end

# ====================================================================
# Scaling dimensions from Ly=10 data (for comparison, noting poor convergence)
# ====================================================================
println("\n  Ly=10 data (subleading exponents not converged, for reference):")
for L in Ls_svd
    @printf("    L=%d: d1=%.4f d2=%.4f d3=%.4f\n", L, svd_data[L].d1_m, svd_data[L].d2_m, svd_data[L].d3_m)
end

# ====================================================================
# Summary
# ====================================================================
println("\n" * sep)
println("FINAL SUMMARY: Self-Dual Point (theta=pi/4)")
println(sep)

println("\n  Literature: c_eff = 0.447 (arXiv:2502.14034)")

println("\n  c_eff estimates:")
@printf("    Ly=20 SVD, 3-param (L=4-12):   %.4f\n", sol1[3])
@printf("    Ly=20 SVD, 3-param (L=4-10):   %.4f\n", sol1n[3])
@printf("    Ly=20 SVD, bootstrap (L=4-12): %.4f +/- %.4f\n", mean(cboot_e), std(cboot_e))
@printf("    Ly=20 pair c(4,6):             %.4f\n", pair_c(4, 6, eig_data[4].phi_sv/4, eig_data[6].phi_sv/6))
if 10 in keys(eig_data)
    @printf("    Ly=20 pair c(4,10):            %.4f\n", pair_c(4, 10, eig_data[4].phi_sv/4, eig_data[10].phi_sv/10))
end
@printf("    Ly=10 SVD, 3-param (L=4-12):   %.4f\n", sol1s[3])
@printf("    Ly=10 pair c(4,6):             %.4f\n", pair_c(4, 6, svd_data[4].phi/4, svd_data[6].phi/6))
if 10 in keys(svd_data)
    @printf("    Ly=10 pair c(4,10):            %.4f\n", pair_c(4, 10, svd_data[4].phi/4, svd_data[10].phi/10))
end

println("\n  Scaling dimensions (Ly=20, L=4-10):")
# Recompute final values
for (dm_arr, de_arr, label) in [
    ([eig_data[L].d1_m for L in Ls_dim], [std(eig_data[L].d1)/sqrt(eig_data[L].n) for L in Ls_dim], "Delta_1"),
    ([eig_data[L].d2_m for L in Ls_dim], [std(eig_data[L].d2)/sqrt(eig_data[L].n) for L in Ls_dim], "Delta_2"),
    ([eig_data[L].d3_m for L in Ls_dim], [std(eig_data[L].d3)/sqrt(eig_data[L].n) for L in Ls_dim], "Delta_3"),
]
    wd = 1.0 ./ de_arr .^ 2
    Ad = zeros(nL_d, 2)
    for i in 1:nL_d
        Ad[i,1] = 1.0; Ad[i,2] = 1.0/Ls_dim[i]^2
    end
    sold, _ = fit_w(Ad, dm_arr, wd)
    @printf("    %s = %.5f\n", label, sold[1])
end

println("\n  Data tables:")
println("    Ly=20 SVD (Phi = -gamma0_sv):")
for L in Ls_eig
    @printf("      L=%-3d n=%-4d Phi=%.6f+-%.6f f=%.6f\n",
            L, eig_data[L].n, eig_data[L].phi_sv, eig_data[L].phi_sv_e, eig_data[L].phi_sv/L)
end
println("    Ly=10 SVD (Phi = -gamma0):")
for L in Ls_svd
    @printf("      L=%-3d n=%-4d Phi=%.6f+-%.6f f=%.6f\n",
            L, svd_data[L].n, svd_data[L].phi, svd_data[L].phi_e, svd_data[L].phi/L)
end

println(sep)
