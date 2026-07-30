#===============================================================================
 通用 ED (triangular/honeycomb) 验证代码, 复用 TIM_lattice_QMC.jl 的晶格构造
 用法: julia TIM_lattice_ED.jl lattice Lx Ly J Gamma B beta1 beta2 dbeta
 输出每行: beta,E/N,mx,mz,mz2
===============================================================================#
isdefined(Main, :Sim) || include(joinpath(@__DIR__, "TIM_lattice_QMC.jl"))
using LinearAlgebra
using Printf

function build_H(lat, Lx, Ly, J, B, Gamma)
    N, Nb, z, bond, sb = build_lattice(Symbol(lat), Lx, Ly)
    dim = 1 << N
    H = zeros(Float64, dim, dim)
    for st in 0:dim-1
        dz = 0.0
        for b in 1:Nb
            s1 = 2*((st >> (bond[1,b]-1)) & 1) - 1
            s2 = 2*((st >> (bond[2,b]-1)) & 1) - 1
            dz += J*s1*s2
        end
        for i in 1:N
            dz -= B*(2*((st >> (i-1)) & 1) - 1)
        end
        H[st+1, st+1] = dz
        for i in 1:N
            H[st+1, xor(st, 1 << (i-1))+1] -= Gamma
        end
    end
    return H, N
end

function thermal_obs(λ, V, N, beta)
    w = exp.(-beta.*(λ .- λ[1]));  Z = sum(w);  w ./= Z
    E = sum(λ.*w)
    dim = 1 << N
    mzdiag = [sum(2*((st >> (i-1)) & 1) - 1 for i in 1:N)/N for st in 0:dim-1]
    mz2 = 0.0; mz = 0.0; mx = 0.0
    for n in 1:dim
        vn = @view V[:,n]
        mzn = sum(vn.^2 .* mzdiag)
        mz += w[n]*mzn
        mz2 += w[n]*sum(vn.^2 .* mzdiag.^2)
        mxn = 0.0
        for st in 0:dim-1
            acc = 0.0
            for i in 1:N
                acc += vn[xor(st, 1 << (i-1))+1]
            end
            mxn += vn[st+1]*acc
        end
        mx += w[n]*mxn/N
    end
    return E/N, mx, mz, mz2
end

if abspath(PROGRAM_FILE) == @__FILE__
    lat = ARGS[1]
    Lx, Ly = parse(Int,ARGS[2]), parse(Int,ARGS[3])
    J, Gamma, B = parse(Float64,ARGS[4]), parse(Float64,ARGS[5]), parse(Float64,ARGS[6])
    β1, β2, dβ = parse(Float64,ARGS[7]), parse(Float64,ARGS[8]), parse(Float64,ARGS[9])
    H, N = build_H(lat, Lx, Ly, J, B, Gamma)
    λ, V = eigen(Symmetric(H))
    for beta in β1:dβ:β2+1e-9
        e, mx, mz, mz2 = thermal_obs(λ, V, N, beta)
        @printf("%.6f,%.8f,%.8f,%.8f,%.8f\n", beta, e, mx, mz, mz2)
    end
end
