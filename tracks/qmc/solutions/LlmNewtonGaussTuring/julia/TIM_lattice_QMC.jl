#===============================================================================
 横场 Ising 模型 (TFIM) 的 SSE 量子蒙特卡洛 —— 三角晶格 / 蜂窝晶格通用版
 采用文献 arXiv:2409.17835 的 merge–unmerge loop 更新算法
   H = J Σ_<ij> σz_i σz_j  -  B Σ_i σz_i  -  Γ Σ_i σx_i
 用途: Challenge 148 —— 三角/蜂窝晶格 TFIM 临界点比值 (√5 猜想) 的检验
 观测量: E, m_x, m_z, <m^2>, <m^4>, Binder 累积量 U = 1 - <m^4>/(3<m^2>^2)
===============================================================================#
using Random
using Printf
using Statistics

mutable struct Sim
    rng::MersenneTwister
    Lx::Int; Ly::Int; N::Int; Nb::Int; z::Int
    bond::Matrix{Int}        # bond[2, Nb]
    site_bonds::Matrix{Int}  # site_bonds[z, N]
    J::Float64; B::Float64; Gamma::Float64; beta::Float64; Cb::Float64
    weight_b::Vector{Float64}
    ll::Int; lm::Int; nh::Int
    opl::Matrix{Int}
    conf::Vector{Int}
    opl3::Matrix{Int}
    link::Vector{Int}
    opcfg::Vector{Int}
    ft::Vector{Int}; lt::Vector{Int}
    pos_nm::Vector{Int}
    nlf::Int
end

#------------------------- 晶格构造 -------------------------#
# triangular: N=Lx*Ly, Nb=3N, z=6; 方向 (1,0),(0,1),(-1,1)
# honeycomb : N=2*Lx*Ly (A/B 双子格), Nb=3LxLy=3N/2, z=3
function build_lattice(lattice::Symbol, Lx, Ly)
    if lattice == :triangular
        N = Lx*Ly; Nb = 3N; z = 6
        bond = zeros(Int, 2, Nb); site_bonds = zeros(Int, 6, N)
        dirs = ((1,0),(0,1),(-1,1))
        sid(x,y) = mod(x,Lx) + mod(y,Ly)*Lx + 1
        for y in 0:Ly-1, x in 0:Lx-1
            s = sid(x,y)
            for d in 1:3
                b = (s-1)*3 + d
                bond[1,b] = s
                bond[2,b] = sid(x+dirs[d][1], y+dirs[d][2])
            end
            for d in 1:3
                site_bonds[d, s]   = (s-1)*3 + d
                sb = sid(x-dirs[d][1], y-dirs[d][2])
                site_bonds[d+3, s] = (sb-1)*3 + d
            end
        end
    elseif lattice == :honeycomb
        N = 2Lx*Ly; Nb = 3Lx*Ly; z = 3
        bond = zeros(Int, 2, Nb); site_bonds = zeros(Int, 3, N)
        aid(x,y) = 2*(mod(x,Lx) + mod(y,Ly)*Lx) + 1   # A 子格
        bid(x,y) = aid(x,y) + 1                        # B 子格
        # 三类键: d1: A(x,y)-B(x,y); d2: A(x,y)-B(x-1,y); d3: A(x,y)-B(x,y-1)
        for y in 0:Ly-1, x in 0:Lx-1
            cell = x + y*Lx + 1; a = aid(x,y)
            for d in 1:3
                b = (cell-1)*3 + d
                bond[1,b] = a
                bond[2,b] = d==1 ? bid(x,y) : d==2 ? bid(x-1,y) : bid(x,y-1)
            end
            site_bonds[:, a] .= (cell-1)*3 .+ (1:3)   # A 点的 3 条键
        end
        for y in 0:Ly-1, x in 0:Lx-1                  # B 点的 3 条键
            s = bid(x,y)
            site_bonds[1, s] = (x + y*Lx)*3 + 1                 # d1 of cell(x,y)
            site_bonds[2, s] = (mod(x+1,Lx) + y*Lx)*3 + 2       # d2 of cell(x+1,y)
            site_bonds[3, s] = (x + mod(y+1,Ly)*Lx)*3 + 3       # d3 of cell(x,y+1)
        end
    else
        error("unknown lattice: $lattice")
    end
    return N, Nb, z, bond, site_bonds
end

function Sim(lattice, Lx, Ly, J, B, Gamma, beta, seed)
    N, Nb, z, bond, site_bonds = build_lattice(Symbol(lattice), Lx, Ly)
    Cb = abs(J) + 2abs(B)/z + 0.5
    weight_b = zeros(4)
    for tp in 1:4
        c1 = (tp-1) & 1; c2 = ((tp-1)>>1) & 1
        weight_b[tp] = -J*(2c1-1)*(2c2-1) + (B/z)*((2c1-1)+(2c2-1)) + Cb
    end
    rng = MersenneTwister(seed)
    conf = [rand(rng,0:1) for _ in 1:N]
    ll = max(1000, ceil(Int, 6*beta*(Nb+N)))
    lm = 10
    opl = zeros(Int, 2, ll); opl3 = zeros(Int, 2, ll)
    link = zeros(Int, 4ll); opcfg = zeros(Int, 4ll)
    return Sim(rng, Lx, Ly, N, Nb, z, bond, site_bonds,
               Float64(J), Float64(B), Float64(Gamma), Float64(beta), Cb,
               weight_b, ll, lm, 0, opl, conf,
               opl3, link, opcfg, fill(-1,N), fill(-1,N), zeros(Int, ll), 1)
end

#------------------------- 对角更新 -------------------------#
function dupdate!(s::Sim)
    opn = s.Nb + s.N
    for i in 1:s.lm
        vtp = s.opl[1,i]
        if vtp == 0
            r = rand(s.rng, 1:opn)
            if r <= s.Nb
                tp = s.conf[s.bond[1,r]] + 2*s.conf[s.bond[2,r]] + 1
                if s.weight_b[tp]*s.beta*opn/(s.lm-s.nh) > rand(s.rng)
                    s.opl[1,i] = tp; s.opl[2,i] = r; s.nh += 1
                end
            else
                r -= s.Nb
                if s.Gamma*s.beta*opn/(s.lm-s.nh) > rand(s.rng)
                    s.opl[1,i] = s.conf[r]*3 + 5; s.opl[2,i] = r; s.nh += 1
                end
            end
        elseif vtp != 6 && vtp != 7
            ap = vtp < 5 ? (s.lm-s.nh+1)/(s.weight_b[vtp]*s.beta*opn) :
                           (s.lm-s.nh+1)/(s.Gamma*s.beta*opn)
            if ap > rand(s.rng)
                s.opl[1,i] = 0; s.opl[2,i] = 0; s.nh -= 1
            end
        else
            r = s.opl[2,i]; s.conf[r] = 1 - s.conf[r]
        end
    end
end

#------------------------- loop 更新 (merge–unmerge) -------------------------#
const PASS_LEG = (3,4,1,2)
const PASS_OFF = ((2,3,4),(1,3,4),(1,2,4),(1,2,3))
const EXIT_P = 0.5

function lupdate!(s::Sim)
    rng = s.rng; z = s.z
    fill!(s.ft, -1); fill!(s.lt, -1)
    #====== merge + 链接表 ======#
    is = 0; ln = 0; nm = 0
    for i in 1:s.lm
        tp = s.opl[1,i]
        tp == 0 && continue
        r = s.opl[2,i]
        if tp < 5
            is += 1
            s.opl3[1,is] = tp; s.opl3[2,is] = r
            s.opcfg[ln+1] = s.conf[s.bond[1,r]]; s.opcfg[ln+2] = s.conf[s.bond[2,r]]
            s.opcfg[ln+3] = s.opcfg[ln+1];      s.opcfg[ln+4] = s.opcfg[ln+2]
        else
            s0 = r
            b  = s.site_bonds[rand(rng,1:z), s0]      # z 条相邻键均匀选 1
            is += 1
            s.opcfg[ln+1] = s.conf[s.bond[1,b]]; s.opcfg[ln+2] = s.conf[s.bond[2,b]]
            if tp == 6 || tp == 7
                s.opl3[1,is] = -1
                s.conf[s0] = 1 - s.conf[s0]
            else
                s.opl3[1,is] = 0
            end
            s.opcfg[ln+3] = s.conf[s.bond[1,b]]; s.opcfg[ln+4] = s.conf[s.bond[2,b]]
            s.opl3[2,is] = b
            nm += 1; s.pos_nm[nm] = is
            r = b
        end
        for leg in 1:2
            bl = s.bond[leg, r]
            if s.ft[bl] == -1; s.ft[bl] = ln+leg; end
            if s.lt[bl] == -1
                s.lt[bl] = ln+2+leg
            else
                s.link[s.lt[bl]] = ln+leg
                s.link[ln+leg]   = s.lt[bl]
                s.lt[bl] = ln+2+leg
            end
        end
        ln += 4
    end
    for i in 1:s.N
        if s.ft[i] != -1
            s.link[s.ft[i]] = s.lt[i]; s.link[s.lt[i]] = s.ft[i]
        end
    end
    #====== loop (start–run–stop) ======#
    for _ in 1:(s.nlf*nm)
        st = s.pos_nm[rand(rng,1:nm)]
        vtx0 = s.opl3[1,st]
        base = (st-1)*4
        if vtx0 == 0
            outleg = rand(rng,1:4)
        elseif s.opcfg[base+1] != s.opcfg[base+3]
            outleg = rand(rng,1:2)*2 - 1
        else
            outleg = rand(rng,1:2)*2
        end
        s.opl3[1,st] = -1 - vtx0
        j2 = base + outleg
        s.opcfg[j2] = 1 - s.opcfg[j2]
        fflag = true
        while fflag
            j1 = s.link[j2]
            inleg = mod(j1-1,4) + 1
            st = (j1-1)÷4 + 1
            vtx0 = s.opl3[1,st]
            base = (st-1)*4
            if vtx0 > 0
                if isodd(inleg)
                    vtx2 = (1-s.opcfg[base+1]) + 2*s.opcfg[base+2] + 1
                else
                    vtx2 = s.opcfg[base+1] + 2*(1-s.opcfg[base+2]) + 1
                end
                if rand(rng) < s.weight_b[vtx2]/s.weight_b[vtx0]
                    s.opcfg[j1] = 1 - s.opcfg[j1]
                    outleg = PASS_LEG[inleg]
                    j2 = j1 - inleg + outleg
                    s.opcfg[j2] = 1 - s.opcfg[j2]
                    s.opl3[1,st] = vtx2
                else
                    j2 = j1
                end
            elseif vtx0 == 0
                s.opcfg[j1] = 1 - s.opcfg[j1]
                if rand(rng) <= 0.5*EXIT_P
                    s.opl3[1,st] = -1
                    fflag = false
                else
                    outleg = PASS_LEG[inleg]
                    j2 = j1 - inleg + outleg
                    s.opcfg[j2] = 1 - s.opcfg[j2]
                end
            else
                left_active = s.opcfg[base+1] != s.opcfg[base+3]  # ★ 翻转前判断活跃端
                s.opcfg[j1] = 1 - s.opcfg[j1]
                can_stop = left_active ? isodd(inleg) : iseven(inleg)
                if can_stop && rand(rng) <= EXIT_P
                    s.opl3[1,st] = 0
                    fflag = false
                else
                    outleg = PASS_OFF[inleg][rand(rng,1:3)]
                    j2 = j1 - inleg + outleg
                    s.opcfg[j2] = 1 - s.opcfg[j2]
                end
            end
        end
    end
    #====== 恢复组态 + unmerge ======#
    for i in 1:s.N
        if s.ft[i] != -1; s.conf[i] = s.opcfg[s.ft[i]]; end
    end
    is = 0
    for i in 1:s.lm
        vtp = s.opl[1,i]
        if vtp != 0
            if vtp < 5
                is += 1
                s.opl[1,i] = s.opl3[1,is]
            else
                is += 1
                r = s.opl3[2,is]; vtx0 = s.opl3[1,is]; base = (is-1)*4
                if vtx0 == 0
                    if rand(rng) < 0.5
                        s.opl[1,i] = s.opcfg[base+1]*3 + 5; s.opl[2,i] = s.bond[1,r]
                    else
                        s.opl[1,i] = s.opcfg[base+2]*3 + 5; s.opl[2,i] = s.bond[2,r]
                    end
                elseif s.opcfg[base+1] != s.opcfg[base+3]
                    s.opl[1,i] = 7 - s.opcfg[base+1]; s.opl[2,i] = s.bond[1,r]
                else
                    s.opl[1,i] = 7 - s.opcfg[base+2]; s.opl[2,i] = s.bond[2,r]
                end
            end
            is == s.nh && break
        end
    end
end

#------------------------- 测量 (增量式) -------------------------#
# E = -<n>/β + Nb*Cb + ΓN ;  m_x = <n_site>/(βΓN) - 1
# m2 = <(Σσz/N)^2>, m4 = <(Σσz/N)^4>  (虚时平均, 增量跟踪 S=Σσz)
function measure(s::Sim)
    n_site = 0
    c = copy(s.conf)
    S = sum(2 .* c .- 1)
    m2_acc = 0.0; m4_acc = 0.0
    invN = 1.0/s.N
    for i in 1:s.lm
        tp = s.opl[1,i]
        if tp == 6 || tp == 7
            si = s.opl[2,i]
            c[si] = 1 - c[si]
            S += 2*(2*c[si]-1)
            n_site += 1
        elseif tp == 5 || tp == 8
            n_site += 1
        end
        m = S*invN
        m2 = m*m
        m2_acc += m2; m4_acc += m2*m2
    end
    E   = -s.nh/s.beta + s.Nb*s.Cb + s.Gamma*s.N
    mx  = n_site/(s.beta*s.Gamma*s.N) - 1.0
    return E/s.N, mx, m2_acc/s.lm, m4_acc/s.lm
end

#------------------------- 主流程 -------------------------#
# 返回 (E, mx, m2, m4) 的均值与 binning 误差, 以及逐 bin 的 Binder U
function run(lattice, Lx, Ly, J, Gamma, B, beta, istp, mstp, seed; nbin=50, G0=0.0)
    s = Sim(lattice, Lx, Ly, J, B, Gamma, beta, seed)
    G1 = Gamma
    for k in 1:istp
        G0 > 0 && (s.Gamma = G0 + (G1-G0)*min(k/(0.8istp),1.0))
        dupdate!(s); lupdate!(s)
        lt = floor(Int, 1.25*s.nh)
        if lt > s.lm
            s.lm = lt
            s.lm > s.ll && error("算符列表溢出, 请增大 ll")
        end
    end
    s.Gamma = G1
    acc = zeros(4); nb = max(1, mstp÷nbin); binacc = zeros(4); bins = Float64[]
    for i in 1:mstp
        dupdate!(s); lupdate!(s)
        o = measure(s)
        acc .+= o; binacc .+= o
        i % nb == 0 && (append!(bins, binacc./nb); binacc .= 0.0)
    end
    avg = acc./mstp
    nbins = length(bins)÷4
    err = [std(bins[k:4:end])/sqrt(nbins) for k in 1:4]
    # 逐 bin 的 Binder 累积量
    m2b = bins[3:4:end]; m4b = bins[4:4:end]
    Ub = 1.0 .- m4b./(3 .* m2b.^2)
    U  = mean(Ub); Uerr = std(Ub)/sqrt(nbins)
    return avg, err, U, Uerr
end

#------------------------- 命令行入口 -------------------------#
# 用法: julia TIM_lattice_QMC.jl triangular|honeycomb Lx Ly J Gamma B beta istp mstp seed [Gamma_start]
# 输出: E,E_err,mx,mx_err,m2,m2_err,m4,m4_err,U,U_err
if abspath(PROGRAM_FILE) == @__FILE__
    lat = ARGS[1]
    Lx, Ly = parse(Int,ARGS[2]), parse(Int,ARGS[3])
    J, Gamma, B, beta = parse(Float64,ARGS[4]), parse(Float64,ARGS[5]),
                        parse(Float64,ARGS[6]), parse(Float64,ARGS[7])
    istp, mstp, seed = parse(Int,ARGS[8]), parse(Int,ARGS[9]), parse(Int,ARGS[10])
    G0 = length(ARGS) >= 11 ? parse(Float64,ARGS[11]) : 0.0
    avg, err, U, Uerr = run(lat, Lx, Ly, J, Gamma, B, beta, istp, mstp, seed; G0=G0)
    @printf("%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
            avg[1], err[1], avg[2], err[2], avg[3], err[3], avg[4], err[4], U, Uerr)
end
