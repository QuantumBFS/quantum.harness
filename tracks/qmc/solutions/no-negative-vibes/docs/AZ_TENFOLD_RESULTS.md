# AZ 十重对称类 Hermitian 时间片侦察

## 问题定义

本轮固定一个明确、可复核的约定：每个 `4 x 4` 时间片生成元 `A_i` 都是 Hermitian 矩阵，
并满足对应 Altland--Zirnbauer 类的规范时间反演 `T`、粒子-空穴 `C` 和/或手征 `S` 约束。
逐构型检验

```text
w = det(I + exp(A_1) ... exp(A_L)).
```

这是一张相同 determinant 约定下的 AZ 侦察表。它不是完整的 BdG QMC 分类：在含 PHS 的
物理表述中，实际费米子迹可能涉及 Pfaffian 或平方根分支。本轮复权足以排除上述 determinant
命题，但不能单独推出该 AZ 类的所有 QMC 表述都有相位问题。

## 协议与完整性

- 十个 AZ 类，各用一个规范 `4 x 4` 表示；
- 深度 `1,2,3,4,8,16`；
- 尺度 `0.25,0.75,1.5`；
- 四个独立种子；
- 每格 1000 个乘积；
- 共 720 格、720,000 个乘积；
- 720/720 成功，无缺失；
- 所有生成元的 Hermitian、TRS、PHS、手征结构残差为零；
- 各格累计约 170 单核秒。

深度 3 是结果驱动加入的关键横轴：一个或两个正定 Hermitian 因子的乘积仍给出正实谱结构，
本轮所有真正的负权或复权都从三个因子首次出现。

复现协议在
[protocols/az-tenfold-hermitian-v1](../protocols/az-tenfold-hermitian-v1/README.md)，生成结果在
`tracks/qmc/results/no-negative-vibes/az-tenfold-hermitian-v1/`。

## 十类结果

| AZ 类 | 72,000 样本中的结果 | 首次失败深度 | 精确闭合 | 判断 |
|---|---:|---:|---|---|
| A | 47,999 复权，1 不确定 | 3 | 与 D 共用复权证书 | determinant 命题失败 |
| AI | 5,361 负权，6 不确定 | 3 | `w=-36` | 失败 |
| BDI | 0 负权/复权，3 不确定 | 无 | 已知约化 | split-orthogonal 块结构 |
| D | 48,000 复权 | 3 | 精确复权 | determinant 命题失败 |
| DIII | 0 负权/复权/不确定 | 无 | 已知约化 | `T^2=-1` Kramers |
| AII | 0 负权/复权/不确定 | 无 | 已知约化 | `T^2=-1` Kramers |
| CII | 0 负权/复权/不确定 | 无 | 已知约化 | `T^2=-1` Kramers |
| C | 48,000 复权 | 3 | 精确复权 | determinant 命题失败 |
| CI | 6,404 负权，2 不确定 | 3 | `w=-53744/7875` | 失败 |
| AIII | 5,421 负权，9 不确定 | 3 | `w=-753344/133875` | 失败 |

“不确定”表示 `I+D` 非常接近奇异，双精度层拒绝把它强行分到正负或复相位；它不是额外的
反例。失败类都有远离零点的精确证书，因此结论不依赖这些病态样本。

[汇总图](../../../results/no-negative-vibes/az-tenfold-hermitian-v1/family-summary.png)
把负权率和复权率画在同一坐标上。

## 五组新的深度三精确证书

精确证书直接给出三个 Hermitian 正定因子 `P_i`。主对数

```text
A_i = log(P_i)
```

存在且为 Hermitian；证书再逐因子验证 TRS、PHS 或手征关系，因此 `A_i` 确实属于所声明的
AZ 时间片类。

| 证书 | 精确结果 |
|---|---:|
| AI 三个实对称正定因子 | `det(I+P_1P_2P_3) = -36` |
| AIII 三个手征正定因子 | `-753344/133875` |
| CI 三个 TRS/PHS 正定因子 | `-53744/7875` |
| A/D 三个 PHS 正定因子 | `2816/27 + (77824/729)i` |
| C 三个 PHS 正定因子 | `2816/27 - (77824/729)i` |

它们保存在 [exact_certificates.json](../fixtures/exact_certificates.json)，自动测试同时检查：

1. 每个因子 Hermitian 正定；
2. 每个 AZ 因子关系；
3. 三因子精确乘积；
4. 精确行列式和权重；
5. 生产用浮点 oracle 得到相同分类。

## 对“有没有找到新类”的回答

这一层没有找到新的恒非负类。四个数值幸存者都约化到已知机制：

- BDI 的 Hermitian 生成元是原始 split-orthogonal 的实块反对角形式；
- AII、DIII、CII 都含 `T^2=-1` 的 Kramers 配对。

这仍然推进了项目：标准 Hermitian AZ 十类已经一次性筛完，六个失败项有最短深度三精确证书，
四个幸存项完成已知机制归类。后续不应重复扫描普通 AZ 类，而应转向：

1. Majorana positivity 复数条件的简洁矩阵表述；
2. 不等于整个 AZ 类的“对称约束交半正定锥”；
3. 存活机制的非平凡半群扩展；
4. 从具体 HS 分解反向产生的受限生成元集合。
