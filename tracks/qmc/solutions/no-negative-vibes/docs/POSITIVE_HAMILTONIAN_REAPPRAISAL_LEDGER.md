# 旧正性成果的 Hamiltonian 再评价总账

日期：2026-07-30
状态：`active`

## 判定字段

每项依次记录 `H/S/Q/E/P/L`：

- `H`：显式 Hermitian Hamiltonian；
- `S`：可控缩放/热力学极限；
- `Q`：逐配置非负且可运行的 QMC；
- `E`：传统方法排除；
- `P`：非平凡物理问题；
- `L`：模型级文献空白。

取值为 `pass`、`partial`、`fail`、`open` 或 `owned-elsewhere`。`open` 不是正面证据。

## 主总账

| ID | 旧成果 | 当前判定 | H/S/Q/E/P/L | 本轮动作 | 下一条可证伪问题 |
|---|---|---|---|---|---|
| R1 | fixed-partition `C3` odd block-TN | `sign-free-but-conventional` | pass/open/pass/fail/fail/open | **已完成首轮排重并停止** | 共同 count-sector `+/-1` gauge 把整个类化为 stoquastic |
| R2 | odd positive-monomial / graded route | `math-known-model-open` | partial/open/pass/open/open/open | Hamiltonian 化后查静态 sector、JW 和 stoquastic | route Hamiltonian 是否只是可积置换/静态 grade 的直和？ |
| R3 | fixed weighted `l_infinity` contraction | `sign-free-mechanism-known` | partial/open/pass/open/open/open | 构造有限密度模型 | 公共收缩是否强制低密度或可简单 uniformization？ |
| R4 | reciprocal-parabolic `[[H,Q],[0,-H^T]]` | `math-only-pending-embedding` | fail/open/pass/open/open/open | 先 Hermitian embedding/no-go | `Q` 是否会从物理 trace/可观测量中完全消失？ |
| R5 | Majorana protected parity | `parked-ownership-risk` | partial/open/partial/open/open/open | 只保留既有证据，先不扩展 | 与 PR #3 的 Majorana/oddcycle 工作边界未同步前不运行 |
| C1 | tensor-square `m>=3` multi-channel | `collaborator-owned` | pass/partial/pass/partial/pass/open | **只读** | ZiboJin phase-diagram 分支负责 ED/DQMC/低温相图 |
| C2 | symmetric oddcycle / seeds `117,132,147` | `collaborator-owned` | partial/open/partial/open/open/open | **只读** | PR #3 负责 metric、transfer、joint pair 与 Hamiltonian portfolio |
| C3 | typed exterior/Pfaffian cones | `collaborator-overlap/reference` | partial/open/partial/open/open/open | 不重搜 exact cards | PR #3 与 PR #8 已覆盖 exterior 搜索和 typed pilot |

## 已关闭或仅作校准

| ID | 路线 | 保留证书 | 关闭原因 |
|---|---|---|---|
| X1 | TN path / 1D bond-HS | 已有任意深度 TN 证明 | JW/1D/worldline 风险直接，作为对照 |
| X2 | independent local `C3` + crossed TN | `det(I+XR)=-2` | 最短两层精确负权 |
| X3 | even monomial `V4` | `-9/4` 精确反例 | 偶循环直接翻号 |
| X4 | moving weighted norm | 80 位稳定负权 | 每片各自收缩不产生公共保护 |
| X5 | reciprocal bicoupled | 80 位稳定负权 | lower-block feedback 破坏 reciprocal pairing |
| X6 | near-commuting frames | 80 位稳定负权 | “近似可积”不闭合 |
| X7 | Wilson gauge cocycle | code-space isometry | 精确变成局域 stoquastic link-spin 模型 |
| X8 | grade-charge ancilla | sector decomposition | ancilla 数守恒，只是静态扇区直和 |
| X9 | adjoint lift / `D4` split | fixed metric certificate | 落入已知 `O(p,q)`/split-orthogonal 类 |
| X10 | commuting dense | exact exponential collapse | 可积校准 |
| X11 | Stark similarity / star-to-chain | exact similarity/Lanczos | 已知表示变换，不形成新物理类 |

## R1 已知事实与重新打开的理由

已知：

```text
B = P_C3 diag(X_0,X_1,X_2),
H = -sum_a q_a [Gamma(B_a)+Gamma(B_a)^dagger].
```

固定 partition 的 odd block-TN 半群对乘法和转置封闭，并有
`det(I+D)>=0`，所以连续时间每个 vertex word 都非负。六模式锚点已经出现非零六体
density coefficient，因此不是普通二次自由模型。

此前降级的理由是“最自然的独立局域 route”被 `-2` 反例关闭。新标准下，这只关闭
crossed-partition 局域化，不关闭固定全局 route 本身。它仍可能对应：

- cavity/global drive 下同步切换的三腿 synthetic dimension；
- 可用单粒子 determinant 多项式代价采样的全局 many-body vertex；
- 不能由局域 worldline/SSE、简单 JW 或固定符号规处理的 interacting ensemble。

R1 的实际复活审计现已完成，并得到一般 no-go：
`Gamma(P)` 的 fermionic sign 只依赖三条 route 的粒子数；`Gamma(P)^3=I` 允许逐
count orbit 构造共同 `+/-1` gauge，而 block-diagonal TN lift 保持这些 count sectors
且逐元非负。因此所有 atoms、两个 `C3` 方向及其转置共享同一个 gauge，完整 `H`
被化为 stoquastic。详见
[fixed-partition odd block-TN stoquastic no-go](ODD_BLOCK_TN_STOQUASTIC_NO_GO.md)。

## R1 立即执行的排除矩阵

| 常规路线 | 当前证据 | 缺少的证书 |
|---|---|---|
| 自由/matchgate | 六模式存在非零六体 coefficient | 一般 `L` 的不可二次化证明 |
| 局域 stoquastic gauge | 尚无 | 小尺寸精确相位规不可行 + frustrated sign cycle |
| JW/worldline/SSE | 全局 route vertex 非局域 | 具体世界线权翻号或无局域分解证明 |
| 静态 sector | 尚无 | 计算一体/局域 commutant |
| even-flavor square | `C3` 为奇 route，不是显式双副本 | 排除隐藏 determinant/Pfaffian 平方 |
| fixed basis/TN | `P_C3` 有负二阶 minor，不能相似到 ordinary TN 的简单谱障碍 | 对整个 Fock Hamiltonian 的变换审计 |

## 升级纪律

总账中的 `pass` 必须链接到证明、回归或机器可读证书。任何候选若直接落入已知求解器，
立即降级但不删除；任何 `open` 都不能写成“无法模拟”。首个真正积极结果必须是六项
全部 `pass` 的 `QNC-primary`。
