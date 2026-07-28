# 无符号 QMC challenge：合作者进展说明

更新时间：2026-07-28

## 一句话状态

我们已经从“理解题目”推进到“有 determinant 与 Majorana 直接 Spin-trace oracle、四轮
可复现主扫描和精确反例库”的阶段：累计检查 2,320,000 个权重，完成普通经典群、标准
Hermitian AZ 十类和共享实结构 Majorana 双锥的系统排查。目前没有发现新的恒非负类，但
已经精确排除一批自然候选；尤其已证明任意小非零夹角的完整 Majorana 双锥混用都会出现
负权，下一步缩小到物理可达受限子集、公共收缩度量和物理映射。

## 已经完成

1. 建立稳定权重 oracle：
   - 计算 `det(I + exp(A_1)...exp(A_L))`；
   - 直接计算 Majorana Fock/Spin 迹并保留 determinant 平方根的符号分支；
   - 区分正、负、零、复相位和数值不确定；
   - 对 Fock 乘积逐层正数归一化，对病态 determinant 只记录相位/对数并标记不可用检查；
   - 每个参数格保存种子、结构残差和反例。
2. 建立 25 个结构生成器：
   - 15 个经典群/李代数候选；
   - 10 个 AZ Hermitian 时间片类。
3. 完成四轮主扫描：
   - `classical-groups-v1`：900 格、900,000 个乘积；
   - `az-tenfold-hermitian-v1`：720 格、720,000 个乘积。
   - `majorana-shared-reality-cones-v2`：1,792 格、448,000 个直接 Fock 迹；
   - `majorana-small-angle-stress-v1`：840 格、252,000 个直接 Fock 迹。
4. 建立 18 组精确 SymPy 证书和 49 个自动测试。

## 当前最重要的结果

### 经典群

- 精确或数值排除：`SL(2/3,R)`、`Sp(2/4,R)`、`SU(1,1)`、`SU(2,1)`、`SU(3)`；
- `U(2)`、`U(1,1)` 的单 flavor determinant 一般为复数；
- 零负例项都能约化到已知 split-orthogonal、共轭配对或 Kramers/Majorana 机制。

### AZ 十类

统一采用 `4 x 4` Hermitian 时间片和标准 TRS/PHS/手征约束：

| 类 | 结果 |
|---|---|
| A、D、C | 从乘积深度 3 开始出现复权，并有精确三因子证书 |
| AI、AIII、CI | 从深度 3 开始出现负权，并有精确三因子证书 |
| BDI | 数值存活，但就是已知 split-orthogonal 块结构 |
| AII、DIII、CII | 数值存活，但都有 `T^2=-1` 的已知 Kramers 机制 |

因此普通 Hermitian AZ 十类没有给出新的恒非负类：六类精确失败，四类约化到已知机制。
对 D/C 等 BdG 类，这里排除的是当前 determinant 命题；完整物理权重仍可能涉及 Pfaffian 或
平方根分支，不能过度解释。

### Majorana 双锥

- 两个已知 Majorana 正锥共享同一个 `J1` 实结构，只旋转 `J2` 收缩方向；
- 448,000 个宽扫权重中有 19,128 个负权，0 复权，说明公共 `J1` 只保证实权；
- 已有深度二精确证书 `p=2-2*cosh(1)<0`，但 determinant 为 `p^2>0`；
- 小角压力测试追加 252,000 个权重，角度 `0.4` 的 4/6-Majorana 负例均由 80 位 Fock
  重放确认；
- 找到 4-Majorana、两层的解析反例族
  `p(theta,q)=-4*sin(theta)*sinh(q)^2<0`，对每个 `0<theta<pi` 成立；
- 因此不存在只由夹角控制的完整双锥恒正小角区；此前 `0.05–0.3` 随机零命中只是抽样漏掉
  秩一零权边界。

## 我们没有声称什么

- 没有声称随机扫描能证明非负；
- 没有声称已经发现新无符号 QMC 类；
- 没有把复权自动等同于所有 BdG QMC 表述都有相位问题；
- 还没有完成一个新类到具体 Hamiltonian 和 Hubbard--Stratonovich 分解的映射。

## 下一步建议

不再重复扫描整个命名群、普通 AZ 类或同分布 Majorana 双锥。优先比较两个窄方向：

1. 从明确 Hamiltonian 与 HS 分解反推可达子集，检查是否避开秩一零权边界；
2. 寻找共享更强公共收缩度量的受限锥交集，或推导角度、范数与离边界距离的联合界。

任何新候选按以下漏斗处理：

```text
定义与已知类排重
→ 小维度/深度反例搜索
→ 失败项精确化
→ 幸存项扩大扫描
→ 数学证明
→ Hamiltonian 与 HS 映射
```

只有候选格扩展到一万以上或预计达到 `10^8` 次检验后，才需要迁移到超算 CPU 任务数组。

## 查看入口

- [总入口](../START_HERE.md)
- [主办方方向完成度](ORGANIZER_DIRECTION_AUDIT.md)
- [Majorana 双锥结果](MAJORANA_CONE_RESULTS.md)
- [AZ 十类结果](AZ_TENFOLD_RESULTS.md)
- [经典群基线](BASELINE_RESULTS.md)
- [精确证书说明](EXACT_CERTIFICATES.md)
- [算力策略](COMPUTE_STRATEGY.md)

生成的完整逐格数据按 harness 约定保存在本地 `tracks/qmc/results/no-negative-vibes/`，不提交
Git；协议、汇总数字、精确证书和复现代码均保存在工作分支中。
