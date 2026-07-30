#===============================================================================
 横场 Ising 模型 SSE —— Line update（可并行的世界线线段翻转更新）
   与 TIM_lattice_QMC.jl（merge–unmerge loop update）共享:
   晶格构造 build_lattice / Sim 结构 / 对角更新 dupdate! / 测量 measure
   哈密顿量约定同上: H = J Σ_<ij> σz σz - B Σ σz - Γ Σ σx
   ★ Challenge 148 的铁磁 (J_challenge=+1, h) 等价于这里的 (J=-1, Γ=h) ★

   算法（本科毕设 sse_new 的 line update 推广到任意近邻图）:
   格点 i 的虚时世界线被 i 上的单体算符（常数 5/8, 非对角 6/7）切成线段。
   对相邻两个单体算符之间的线段整体翻转 i 的自旋:
     - 线段内每个含 i 的键算符只翻 i 那条腿, 权重比 w_new/w_b_old 进入接受率;
     - 两端单体算符在 常数(Γ) <-> 非对角(Γ) 间切换, 权重比 1;
     - heat-bath 接受 (Π ratio)/(1 + Π ratio)。
   对角更新只插删常数单体算符; 非对角算符全部由 line update 产生/消灭。

 并行化: 翻转 i 的线段只触碰 i 的单体算符与 i 的关联键算符
   => 冲突图 = 晶格图本身 => 正常点着色后同色格点可同时更新
   （蜂窝 2 色, 三角 3 色; 见 lattice_coloring.jl）
===============================================================================#
isdefined(Main, :Sim) || include(joinpath(@__DIR__, "TIM_lattice_QMC.jl"))
include(joinpath(@__DIR__, "lattice_coloring.jl"))

#------------------------- 基本操作 -------------------------#
# 键算符 p 上翻转 leg(1|2) 腿的权重比与就地翻转
# 键类型编码 tp-1 = c1 + 2 c2, c1/c2 为两腿自旋 => 翻 leg 即异或对应位
@inline function bond_flip_ratio(s::Sim, p::Int, leg::Int)
    tp = s.opl[1, p]
    @inbounds return s.weight_b[((tp - 1) ⊻ leg) + 1] / s.weight_b[tp]
end
@inline function bond_flip!(s::Sim, p::Int, leg::Int)
    @inbounds s.opl[1, p] = ((s.opl[1, p] - 1) ⊻ leg) + 1
end

#------------------------- 每格点算符位置表 -------------------------#
# lists[i]: (p, leg) 按虚时序; leg=0 单体算符, leg=1|2 键算符中 i 所在腿
function build_site_lists!(s::Sim, lists::Vector{Vector{Tuple{Int,Int}}})
    @inbounds for l in lists
        empty!(l)
    end
    @inbounds for p in 1:s.lm
        tp = s.opl[1, p]
        tp == 0 && continue
        r = s.opl[2, p]
        if tp < 5
            push!(lists[s.bond[1, r]], (p, 1))
            push!(lists[s.bond[2, r]], (p, 2))
        else
            push!(lists[r], (p, 0))
        end
    end
end

#------------------------- 单格点 line 更新 -------------------------#
# 单体算符类型编码 tp-5 = s_in + 2 s_out (in=虚时下方, out=上方)
# 线段 k: 从分隔符 a 上方到分隔符 b 下方 => 翻 a 的 out 位、b 的 in 位
# 跨 τ=0 的线段（最后一段）翻转 conf[i]
function update_site_lines!(s::Sim, i::Int, list::Vector{Tuple{Int,Int}},
                            ds::Vector{Int}, rng::AbstractRNG)
    n = length(list)
    if n == 0                       # 完全自由的世界线: 1/2 概率翻转
        rand(rng) < 0.5 && (s.conf[i] = 1 - s.conf[i])
        return 0, 0
    end
    empty!(ds)
    @inbounds for k in 1:n
        list[k][2] == 0 && push!(ds, k)
    end
    K = length(ds)
    acc = 0
    if K == 0                       # 无分隔符: 整条世界线翻转 (热浴接受率, 见下)
        R = 1.0
        @inbounds for (p, leg) in list
            R *= bond_flip_ratio(s, p, leg)
        end
        if rand(rng) < R / (1.0 + R)
            @inbounds for (p, leg) in list
                bond_flip!(s, p, leg)
            end
            s.conf[i] = 1 - s.conf[i]
            acc = 1
        end
        return acc, 1
    end
    @inbounds for k in 1:K
        a = ds[k]
        b = k == K ? ds[1] : ds[k+1]
        R = 1.0
        idx = a
        while true                  # 循环开区间 (a, b) 内全为键算符
            idx = idx == n ? 1 : idx + 1
            idx == b && break
            p, leg = list[idx]
            R *= bond_flip_ratio(s, p, leg)
        end
        # ★ 热浴 (Glauber) 接受率 R/(1+R), 而非 Metropolis min(1,R):
        #   线段不含键算符时 R=1, Metropolis 必然接受 => 每扫确定性翻转全部线段,
        #   相对构型永不改变 (非遍历, J=0 测试可复现)。热浴在 R=1 时给 1/2,
        #   恰为自由自旋区间的精确重采样, 且对任意 R 满足细致平衡。
        if rand(rng) < R / (1.0 + R)
            idx = a
            while true
                idx = idx == n ? 1 : idx + 1
                idx == b && break
                p, leg = list[idx]
                bond_flip!(s, p, leg)
            end
            pa = list[a][1]         # a==b (K==1) 时两次异或叠加为 ⊻3, 正确
            s.opl[1, pa] = ((s.opl[1, pa] - 5) ⊻ 2) + 5
            pb = list[b][1]
            s.opl[1, pb] = ((s.opl[1, pb] - 5) ⊻ 1) + 5
            k == K && (s.conf[i] = 1 - s.conf[i])
            acc += 1
        end
    end
    return acc, K
end

#------------------------- 整扫 (串行 / 按颜色并行) -------------------------#
struct LineScratch
    lists::Vector{Vector{Tuple{Int,Int}}}
    ds::Vector{Vector{Int}}              # 每线程分隔符缓冲
    rngs::Vector{MersenneTwister}        # 每线程独立 RNG
end
LineScratch(N::Int, nt::Int, seed) = LineScratch(
    [Tuple{Int,Int}[] for _ in 1:N],
    [Int[] for _ in 1:nt],
    [MersenneTwister(hash((seed, :line_thread, t))) for t in 1:nt])

function update_color_classes!(s::Sim, sc::LineScratch,
                               classes::Vector{Vector{Int}}; nt::Int = 1)
    acc = 0
    tot = 0
    if nt == 1
        ds = sc.ds[1]
        @inbounds for cls in classes, i in cls
            a, t = update_site_lines!(s, i, sc.lists[i], ds, s.rng)
            acc += a
            tot += t
        end
    else
        accs = zeros(Int, nt)
        tots = zeros(Int, nt)
        for cls in classes                       # 颜色间串行, 颜色内并行
            len = length(cls)
            chunk = cld(len, nt)
            @sync for t in 1:nt
                lo = (t - 1) * chunk + 1
                hi = min(t * chunk, len)
                lo > hi && continue
                Threads.@spawn begin
                    la = 0
                    lt = 0
                    @inbounds for k in lo:hi
                        i = cls[k]
                        a2, t2 = update_site_lines!(s, i, sc.lists[i], sc.ds[t], sc.rngs[t])
                        la += a2
                        lt += t2
                    end
                    accs[t] += la
                    tots[t] += lt
                end
            end
        end
        acc = sum(accs)
        tot = sum(tots)
    end
    return acc, tot
end

function line_sweep!(s::Sim, sc::LineScratch, classes::Vector{Vector{Int}}; nt::Int = 1)
    build_site_lists!(s, sc.lists)
    return update_color_classes!(s, sc, classes; nt = nt)
end

function set_bond_epsilon!(s::Sim, epsilon::Real)
    epsilon > 0 || throw(ArgumentError("epsilon must be positive"))
    s.Cb = abs(s.J) + 2abs(s.B) / s.z + epsilon
    @inbounds for tp in 1:4
        c1 = (tp - 1) & 1
        c2 = ((tp - 1) >> 1) & 1
        s.weight_b[tp] = -s.J * (2c1 - 1) * (2c2 - 1) +
                         (s.B / s.z) * ((2c1 - 1) + (2c2 - 1)) + s.Cb
    end
    return s
end

recommended_line_epsilon(lattice) = Symbol(lattice) == :honeycomb ? 1.0 : 0.5

#------------------------- 组态一致性检查 (调试/测试用) -------------------------#
# 沿算符列表传播 conf, 验证每个键算符类型与两腿自旋一致、
# 单体算符 in 位与下方自旋一致, 且传播一圈后回到 conf (虚时周期性)
function check_config(s::Sim)
    c = copy(s.conf)
    @inbounds for p in 1:s.lm
        tp = s.opl[1, p]
        tp == 0 && continue
        r = s.opl[2, p]
        if tp < 5
            tp == c[s.bond[1, r]] + 2 * c[s.bond[2, r]] + 1 || return false
        else
            sin_ = (tp - 5) & 1
            c[r] == sin_ || return false
            c[r] = (tp - 5) >> 1
        end
    end
    return c == s.conf
end

#------------------------- 主流程 -------------------------#
# 与 run(...) 相同的热化/测量/分 bin 结构, 更新器换成 dupdate! + line_sweep!
# 返回 (avg, err, U, Uerr, acc_rate, sweeps_per_sec)
function run_line(lattice, Lx, Ly, J, Gamma, B, beta, istp, mstp, seed;
                  nbin = 50, G0 = 0.0, nt = 1, check_every = 0, epsilon = nothing)
    s = Sim(lattice, Lx, Ly, J, B, Gamma, beta, seed)
    set_bond_epsilon!(s, isnothing(epsilon) ? recommended_line_epsilon(lattice) : epsilon)
    _, classes = color_lattice(Symbol(lattice), Lx, Ly, s.N, s.bond)
    sc = LineScratch(s.N, max(nt, 1), seed)
    G1 = Gamma
    for k in 1:istp
        G0 > 0 && (s.Gamma = G0 + (G1 - G0) * min(k / (0.8istp), 1.0))
        dupdate!(s)
        line_sweep!(s, sc, classes; nt = nt)
        lt = floor(Int, 1.25 * s.nh)
        if lt > s.lm
            s.lm = lt
            s.lm > s.ll && error("算符列表溢出, 请增大 ll")
        end
    end
    s.Gamma = G1
    acc_n = 0
    tot_n = 0
    acc = zeros(4)
    nb = max(1, mstp ÷ nbin)
    binacc = zeros(4)
    bins = Float64[]
    t0 = time()
    for i in 1:mstp
        dupdate!(s)
        a, t = line_sweep!(s, sc, classes; nt = nt)
        acc_n += a
        tot_n += t
        if check_every > 0 && i % check_every == 0
            check_config(s) || error("worldline consistency broken at sweep $i")
        end
        o = measure(s)
        acc .+= o
        binacc .+= o
        i % nb == 0 && (append!(bins, binacc ./ nb); binacc .= 0.0)
    end
    dt = time() - t0
    avg = acc ./ mstp
    nbins = length(bins) ÷ 4
    err = [std(bins[k:4:end]) / sqrt(nbins) for k in 1:4]
    m2b = bins[3:4:end]
    m4b = bins[4:4:end]
    Ub = 1.0 .- m4b ./ (3 .* m2b .^ 2)
    U = mean(Ub)
    Uerr = std(Ub) / sqrt(nbins)
    return avg, err, U, Uerr, acc_n / max(tot_n, 1), mstp / dt
end

#------------------------- 命令行入口 -------------------------#
# 用法: julia [-t T] TIM_lattice_line.jl lattice Lx Ly J Gamma B beta istp mstp seed [Gamma_start] [nt] [epsilon]
# 输出: E,E_err,mx,mx_err,m2,m2_err,m4,m4_err,U,U_err,acc_rate,sweeps_per_sec
if abspath(PROGRAM_FILE) == @__FILE__
    lat = ARGS[1]
    Lx, Ly = parse(Int, ARGS[2]), parse(Int, ARGS[3])
    J, Gamma, B, beta = parse(Float64, ARGS[4]), parse(Float64, ARGS[5]),
                        parse(Float64, ARGS[6]), parse(Float64, ARGS[7])
    istp, mstp, seed = parse(Int, ARGS[8]), parse(Int, ARGS[9]), parse(Int, ARGS[10])
    G0 = length(ARGS) >= 11 ? parse(Float64, ARGS[11]) : 0.0
    nt = length(ARGS) >= 12 ? parse(Int, ARGS[12]) : 1
    epsilon = length(ARGS) >= 13 ? parse(Float64, ARGS[13]) : recommended_line_epsilon(lat)
    nt > Threads.nthreads() &&
        error("nt=$nt 超过 Julia 线程数 $(Threads.nthreads()), 请用 julia -t $nt 启动")
    avg, err, U, Uerr, ar, sps = run_line(lat, Lx, Ly, J, Gamma, B, beta,
                                          istp, mstp, seed; G0 = G0, nt = nt,
                                          epsilon = epsilon)
    @printf("%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.4f,%.2f\n",
            avg[1], err[1], avg[2], err[2], avg[3], err[3], avg[4], err[4],
            U, Uerr, ar, sps)
end
