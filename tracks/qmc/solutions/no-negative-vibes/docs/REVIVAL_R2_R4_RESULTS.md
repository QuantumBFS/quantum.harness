# 复活名单 R2–R4：首轮 Hamiltonian 排重结果

日期：2026-07-30

## 结论

三个剩余自有候选已经实际进入 Hamiltonian/adjoint 审计：

| 候选 | 结果 | 判定 |
|---|---|---|
| R2 odd positive-monomial | 任意奇数阶 permutation group 的 Fock signs 有共同 `+/-1` gauge | 整类 stoquastic，关闭为 QNC |
| R3 fixed weighted `l_infinity` | 两个合法 contraction atoms 加入 Hermitian adjoint 后深度 2 负权 | 原正半群不能 Hermitian 化 |
| R4 reciprocal-parabolic | upper reciprocal shears 加入 adjoint 后精确权 `4-s^2` | `s>2` 即负，不能 Hermitian 化 |

这三项都保留数学正性或单向 transfer 价值，但不能直接产生目标 Hermitian QNC。

## R2：odd monomial 的共同 Fock gauge

设 `G` 是奇数阶 permutation group，atoms 为

```text
B_(g,a)=P_g D_a,   D_a>0 diagonal,
H=-sum_(g,a) q_(g,a) [Gamma(B_(g,a))+h.c.].
```

`Gamma(D_a)` 是正对角矩阵。`Gamma(P_g)` 是 signed permutation。固定一个 occupation
state，其 stabilizer 在 Fock line 上给出 sign character

```text
chi: Stab(state) -> {+1,-1}.
```

stabilizer 是奇数阶群的子群，不能有非平凡映射到二阶群，所以 `chi=+1`。因此每个
occupation orbit 上都可任选代表态相位，再沿 group action 传播，得到共同 gauge `S`：

```text
S Gamma(P_g) S >= 0
```

对所有 `g` 同时成立。因为 `Gamma(D_a)` 为正对角，同一个 `S` 也使所有
`Gamma(P_g D_a)` 非负，故 `S H S` stoquastic。

这覆盖 `C3`、`C5` 和任意奇数阶非阿贝尔 permutation group。偶数阶边界不成立：
regular `V4` 在某些 occupation state 上有负 stabilizer self-loop，与既有 `-9/4`
determinant 反例一致。

graded transposition + ancilla 路线不因此复活：既有审计已证明 ancilla number
严格守恒，完整模型是静态 bit sectors 的直和；其物理 hopping 另有普通 site-sign
stoquastic gauge。

## R3：固定加权 `l_infinity` 不对 adjoint 闭合

取公共 metric `h=(8,1)` 和两个生成元

```text
A_+ = [[-3/8, +3], [0,0]],
A_- = [[-3/8, -3], [0,0]].
```

两者都严格满足

```text
a_ii + sum_(j!=i) |a_ij| h_j/h_i <= 0
```

（第一行恰好饱和，第二行为零），所以 `B_+=exp(A_+)`、`B_-=exp(A_-)` 都在同一个
固定加权 `l_infinity` contraction semigroup。令

```text
a=exp(-3/8),  b=8(1-a),
B_+=[[a,b],[0,1]],  B_-=[[a,-b],[0,1]].
```

Hermitian factory 必须同时允许 `B_-^T`，但最短 mixed word 已给出

```text
det(I + B_+ B_-^T)
 = 2 + 2a^2 - b^2
 = -3.3136985846984692...
```

且 `sigma_min(I+B_+B_-^T)>0.45`，不是近零翻号。原 R3 的正性只覆盖单向 contraction
semigroup；它不满足 Hermitian factory 的 transpose-closure 前提。

若强行缩到同时在 weighted `l_infinity` 及其 dual 中收缩的子类，机制将退化为公共
双侧/Euclidean contraction；这是一个较小 repair 候选，不能沿用原 R3 的广泛声明。

## R4：reciprocal-parabolic 同样不对 adjoint 闭合

在最小 `2x2` 情形取

```text
A_+=[[0,+s],[0,0]],  A_-=[[0,-s],[0,0]].
```

它们都属于 `[[H,Q],[0,-H^T]]`，且

```text
B_+=exp(A_+)=[[1,s],[0,1]],
B_-=exp(A_-)=[[1,-s],[0,1]].
```

单向 upper-parabolic words 的正性仍由三角因子化保证；但 Hermitian adjoint 引入
lower-parabolic branch。深度 2：

```text
det(I+B_+B_-^T)=4-s^2.
```

`s=3` 时精确为 `-5`。这就是此前 reciprocal-bicoupled 失败的解析最小核：
`Q` 不是“物理 trace 中无害的 decoration”，而是 adjoint 一加入便破坏正性。

## 本轮停止与剩余窗口

已关闭：

- R1 fixed-partition odd block-TN：共同 count gauge，stoquastic；
- R2 odd monomial/graded route：共同 orbit gauge或静态 ancilla sectors；
- R3 原 fixed weighted `l_infinity`：缺少 transpose closure；
- R4 reciprocal-parabolic：缺少 transpose closure，精确 `-5`。

仍可独立研究但必须作为新候选重新登记：

1. **bi-contractive repair**：同时控制 norm 与 dual norm，再检查是否只有已知 Euclidean
   contraction，及其 Hamiltonian 是否非-stoquastic；
2. **动态 graded ancilla**：加入不守恒 ancilla dynamics，同时保持逐历史正权；
3. **Majorana protected parity**：已有数值线索，但与协作者 PR #3 的 Majorana/oddcycle
   范围有交叉，未同步 ownership 前不执行。

本结果没有触碰 tensor-square 相图、oddcycle seeds/joint-pair 或 exterior exact-card
搜索。
