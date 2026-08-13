# Odd block-TN 的局域物理闭环审计

日期：2026-07-28  
状态：`natural-local-closure-falsified`

## 一句话结果

固定 block partition 下的奇数循环 block-TN 定理仍然正确；但最自然的物理推广——
让每个格点独立选择局域 `C3` 路由，再用 flavor-preserving TN hopping 连通格点——
已经有一个六模式、两层、整数矩阵的精确负权：

```text
det(I + X R) = -2.
```

因此 odd block-TN 不再作为“局域新 Hamiltonian”的近期主候选。剩余的全局同步路由
没有被此反例否定，但它对应固定宏观 block partition，局域性和自然 HS 来源仍未解决。

## 最小物理问题

取两个空间格点 `x=0,1`，每点三个 flavor `a=0,1,2`，按

```text
(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)
```

排列六个单粒子模式。

希望同时允许：

1. 每个格点上的局域三循环路由；
2. 同一 flavor 沿两个格点的局域 TN hopping。

第一项让 auxiliary route 成为真正局域场；第二项让系统不只是互不耦合的三站点玩具。

## 两个各自合法的时间片

### 局域奇循环

在 `x=0` 做一个方向的三循环，在 `x=1` 做反方向三循环：

```text
R =
[[0,1,0, 0,0,0],
 [0,0,1, 0,0,0],
 [1,0,0, 0,0,0],
 [0,0,0, 0,0,1],
 [0,0,0, 1,0,0],
 [0,0,0, 0,1,0]].
```

它满足 `R^3=I`。两个循环都为奇长度，所以 `R` 没有负实本征值并存在实矩阵对数。

### 连通 TN hopping

对三个 flavor 分别取两个空间格点上的对称正定 TN 块

```text
X_0 = [[1,1],[1,2]],
X_1 = [[2,3],[3,5]],
X_2 = [[6,2],[2,2]].
```

三个块的 determinant 分别是 `1,1,8`；每个块都逐元为正、对称正定，因此都是
某个实对称局域生成元的指数。把它们放入 flavor-preserving 的 crossed partition：

```text
X =
[[1,0,0, 1,0,0],
 [0,2,0, 0,3,0],
 [0,0,6, 0,0,2],
 [1,0,0, 2,0,0],
 [0,3,0, 0,5,0],
 [0,0,2, 0,0,2]].
```

`X` 因而是三个局域两站点 TN hopping propagator 的直和，并有实对称对数。

## 精确停止证书

直接整数行列式给出

```text
det(I+X) > 0,
det(I+R) > 0,
det(I+X R) = -2.
```

所以失败不是：

- 浮点误差；
- 深层病态乘积；
- 单时间片没有实对数；
- 使用了非局域稠密 hopping；
- 使用了偶置换。

它发生在两个各自可接受的局域实指数时间片混合后的最短深度。

## 为什么不与原 block-TN 定理矛盾

原定理固定一种 block partition：

```text
三条 route blocks
→ 一个全局 C3 同步置换
→ 每条 route 内部使用 TN block。
```

这里为了得到局域模型，使用了两种相交的 partition：

```text
R 按 site 分块，在每个 site 内轮换 flavor；
X 按 flavor 分块，在每个 flavor 内连接 sites。
```

固定分块的乘法闭包因此不再适用。负权正是说明：不能把抽象 block-TN 定理无代价地
局域化。

## 独立的群论局域性障碍

两个三循环的支撑：

| 关系 | 生成群阶数 | 是否仍为奇数阶 |
|---|---:|---|
| 相同支撑 | 3 | 是 |
| 完全不交 | 9 | 是 |
| 共享两个模式 | 12 | 否 |
| 共享一个模式 | 60 | 否 |

因此普通相互重叠的局域三体路由会迅速生成偶阶群；保持奇数阶最容易的方法是让它们
完全不交，但那又不能形成丰富的连通局域动力学。

## 当前结论边界

已经关闭：

> independent local `C3` routes + crossed flavor-preserving TN hopping。

没有被数学反例关闭：

> 固定宏观 block partition 下的全局同步 odd block-TN 半群。

但后一种构造目前只有抽象矩阵意义。若把整个同步 route 的 Fock lift 当作一个
Hamiltonian vertex，其支撑随系统大小增长；若把它拆成独立局域 route，又回到上面的
精确负权边界。因此在出现新的 constrained gauge/ancilla 机制以前，不继续把它当作
自然局域 Hamiltonian 主线。

## 可执行证据

- 构造：`oracle/monomial_candidates.py` 中
  `local_c3_crossed_tn_boundary_factors()`；
- 回归：`tests/test_monomial_candidates.py`；
- 检查内容：`R^3=I`、两个实指数重构、三个 TN/SPD 块和精确权重 `-2`。

