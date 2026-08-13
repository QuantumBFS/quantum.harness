# Fixed-partition odd block-TN 的 stoquastic no-go

日期：2026-07-30

## 结论

复活名单 R1 已完成第一轮实质排除，结果是否定的：

> 所有固定三块 partition 的 `C3` block-TN Hermitian factory Hamiltonian 都存在同一个
> 可高效计算的 occupation-basis `+/-1` 对角符号规；变换后所有非对角矩阵元非正。

因此 R1 虽然给出 interacting、任意历史无符号的 Hamiltonian，但它属于传统
stoquastic/worldline/SSE 可处理类，不能成为目标 QNC 体系。

## Hamiltonian

对任意 TN blocks 和非负耦合，

```text
B_a = P^d_a diag(X_(a,0),X_(a,1),X_(a,2)),  d_a in {-1,0,1},
H   = -sum_a q_a [Gamma(B_a)+Gamma(B_a)^T].
```

所有 atoms 共享固定 route partition。

## 一般证明

写 `B=P D`。在按三条 route 分组的 occupation basis 中：

1. `Gamma(D)` 的矩阵元是三个 TN blocks 的 minors 乘积，所以逐元非负；
2. `Gamma(D)` 保持 route 粒子数三元组 `n=(n_0,n_1,n_2)`；
3. `Gamma(P)` 是 signed permutation，forward `C3` 的 Fock sign 只依赖 `n`：

   ```text
   epsilon(n)=(-1)^[n_0(n_1+n_2)].
   ```

4. count orbit 为 `n -> (n_1,n_2,n_0) -> (n_2,n_0,n_1)`。
   因为 `Gamma(P)^3=I`，每个 orbit 上三个 `epsilon` 的乘积为 `+1`；
5. 因此可逐 orbit 选择 `s(n)=+/-1`，满足

   ```text
   s(rotate(n)) epsilon(n) s(n)=+1.
   ```

令 `S|state>=s(n(state))|state>`。`S` 在每个 count sector 内为常数，所以不改变
`Gamma(D)` 的非负矩阵元；同时它把 `Gamma(P)` 变成非负 permutation。故对所有 atoms
和两个方向，

```text
S Gamma(B_a) S >= 0 entrywise.
```

最终 `S H S` 的所有非对角元都不大于零。这不是小尺寸猜想，而是覆盖任意 block size、
任意 atom 数和任意非负耦合的一般约化。

## 计算发现过程

- 单 atom 六模式模型：64 个 Fock states、178 条非零 off-diagonal edges，
  精确符号约束可行；
- occupation graph 有 11 个连通分量，除总粒子数外还有额外 sector；
- 固定种子 `20260730` 的 300 个双 atom TN 候选全部可规约；
- 上述共同 count gauge 随后解释了零失败，并将数值观察升级为一般证明；
- 非对易双 atom 回归确认同一 gauge 同时覆盖两个方向和所有转置 branches。

数值扫描只用于发现模式；no-go 的依据是上面的 orbit 证明。

## 保留价值与停止条件

保留：

- odd block-TN 任意深度 determinant 正性；
- 显式高体 Hermitian 模型；
- fixed partition 与 crossed-partition `-2` 反例共同形成完整边界；
- 新的共同 stoquastic gauge 作为后续候选的快速排重工具。

停止：

- 不再为 fixed-partition R1 做 extensivity、相图或文献优先权扫描；
- 不再随机增加 atoms；共同 gauge 已覆盖整个类；
- 只有打破“固定 count-preserving TN blocks”且同时绕开 `det(I+XR)=-2` 的新机制，
  才能重开。

下一项转向复活名单 R2/R3：graded-monomial route 与 fixed weighted
`l_infinity` Hamiltonian，首先执行同样的传统方法解析排重。
