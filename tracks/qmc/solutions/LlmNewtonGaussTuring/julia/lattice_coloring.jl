#===============================================================================
 晶格图着色 —— 为可并行 line update 提供无冲突分组
   同色格点两两不相邻 => 同一颜色类内的格点可以同时做 line update
   （翻转格点 i 的世界线线段只读写 i 自己的单体算符与 i 关联键算符的腿）
 - 蜂窝晶格: 二部图, 2 色 (A/B 子格)
 - 三角晶格: 含奇圈, 3 色; 显式着色 c(x,y) = (x+2y) mod 3,
   周期边界自洽要求 Lx ≡ 0 且 Ly ≡ 0 (mod 3)
 - 其他情形: 贪心回退 (一般 ≤ z+1 色, 三角非 3 倍数时通常 4 色)
===============================================================================#

# 由键表构造邻接表
function build_adjacency(N::Int, bond::Matrix{Int})
    adj = [Int[] for _ in 1:N]
    for b in 1:size(bond, 2)
        i, j = bond[1, b], bond[2, b]
        i == j && error("self-bond detected (L too small for coloring/line update)")
        push!(adj[i], j)
        push!(adj[j], i)
    end
    return adj
end

# 贪心着色: 依格点序取邻居未用的最小颜色
function greedy_coloring(N::Int, bond::Matrix{Int})
    adj = build_adjacency(N, bond)
    colors = zeros(Int, N)
    for i in 1:N
        used = falses(length(adj[i]) + 1)
        for j in adj[i]
            c = colors[j]
            0 < c <= length(used) && (used[c] = true)
        end
        colors[i] = findfirst(!, used)
    end
    return colors
end

# 主入口: 返回 colors[N] 与颜色类 classes::Vector{Vector{Int}}
function color_lattice(lattice::Symbol, Lx::Int, Ly::Int, N::Int, bond::Matrix{Int})
    colors = zeros(Int, N)
    if lattice == :honeycomb
        # 站点编号: A 子格为奇, B 子格为偶 (见 build_lattice)
        for s in 1:N
            colors[s] = isodd(s) ? 1 : 2
        end
    elseif lattice == :triangular && Lx % 3 == 0 && Ly % 3 == 0
        # 显式三着色: 近邻 (1,0),(0,1),(-1,1) 分别使 c 增加 1,2,1 (mod 3)
        for y in 0:Ly-1, x in 0:Lx-1
            s = mod(x, Lx) + mod(y, Ly) * Lx + 1
            colors[s] = mod(x + 2y, 3) + 1
        end
    else
        colors = greedy_coloring(N, bond)
    end
    verify_coloring(colors, bond) ||
        error("coloring invalid for lattice=$lattice Lx=$Lx Ly=$Ly")
    nc = maximum(colors)
    classes = [Int[] for _ in 1:nc]
    for s in 1:N
        push!(classes[colors[s]], s)
    end
    return colors, classes
end

# 正确性: 每条键两端颜色不同
function verify_coloring(colors::Vector{Int}, bond::Matrix{Int})
    for b in 1:size(bond, 2)
        colors[bond[1, b]] == colors[bond[2, b]] && return false
    end
    return true
end
