# PEPO/OLE 当前结果与代码有效性说明

更新日期：2026-07-28

> 后续更新：49Q 远端 pilot 与自适应扫描已经完成到
> `Dop=32,χenv=64`。本文件以下内容保留的是提交 49Q 计算前的阶段性判断；
> 最新数值、资源和结论见 `PEPO_49Q_VALIDATION.md`。最终结论仍是代码/执行链路
> 有效，但 PEPO 数值在批准的 `Dop≤32` 范围内未收敛。

## 结论

当前七量子比特测试为 PEPO/Heisenberg-picture 实现提供了**很强的代码级有效性证据**：独立 dense oracle 与未截断 PEPO 在 δ=0 和 δ=0.15 两个参数点的最大差异为 `6.883×10⁻¹⁵`，远小于预先规定的纯绝对容差 `10⁻¹⁰`，重复运行的 PEPO 标量差为 0。

这足以支持下一步进行受控的 49Q pilot，但不能单独证明：

- 49Q 结果已经准确或收敛；
- 小 `Dop`、小 `χenv` 在 49Q 上足够；
- PEPO 已经复现 BP-TN baseline；
- PEPO 满足最终内部误差预算 `εPEPO≤10⁻³`。

因此，当前判断是：

> **小系统代码验证通过；full-system 数值验证尚未完成；baseline benchmark 尚未成立。**

## 已锁定的问题定义

小系统验证使用：

- 物理站点：`{33,39,49,50,51,52,53}`；
- 相互作用边：`(33,39)`、`(39,53)`、`(53,52)`、`(52,51)`、`(51,50)`、`(50,49)`；
- 观测量：`O=Z52`；
- 参数：δ=0 和 δ=0.15；
- 目标量：`F=2⁻⁷ Tr[O C† O C]`；
- dense Hilbert 空间维数：`D=2⁷=128`；
- 接受条件：`|FPEPO−Fdense|≤10⁻¹⁰`。

完整问题保持为 49 个 active sites、73 层、648 个 CZ、`O=Z52 Z59 Z72` 和
`F=2⁻⁴⁹ Tr[O C† O C]`。当前没有执行或认证 49Q 数值结果。

## 当前数值结果

| 参数 | Dense oracle | 未截断 PEPO | 纯绝对差 |
| --- | ---: | ---: | ---: |
| δ=0 | 0.9999999999999785 | 0.9999999999999853 | 6.883×10⁻¹⁵ |
| δ=0.15 | 0.9650960939174911 | 0.9650960939174973 | 6.217×10⁻¹⁵ |

主运行资源：

- wall time：24.380 s；
- peak RSS：296,882,176 bytes，约 0.276 GiB；
- 当前 numerical-core digest：
  `cb55b3bd68415d10cbfd4d23f980fdd3fe99dea07e7387f4ce59070c10e4715f`；
- quimb commit：
  `3c89529fe0a3487133a3928201691161e110abdf`；
- QASM SHA-256：
  `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455`。

重复运行再次得到 success，两个 PEPO 标量与主运行逐位相同。

## 截断结果给出的重要警告

δ=0.15 时，固定小 `Dop` 的结果为：

| Dop | PEPO 值 | 相对 dense 的纯绝对差 |
| ---: | ---: | ---: |
| 1 | 0.000003050414984 | 0.9651 |
| 2 | 0.001519203623422 | 0.9636 |
| 4 | 0.068810381415524 | 0.8963 |

这组数据并不否定代码有效性。它说明未截断算法能复现 exact，但强截断会产生很大偏差。其直接后果是：

- 49Q 的 `Dop={2,4}` pilot 只能视为可运行性和误差趋势测试；
- 不能把 pilot 最大角点直接当作物理解；
- 很可能需要把 `Dop` 自适应扩展到明显高于 4；
- `χenv` 的 full-system 收缩误差仍需独立扫描。

## 为什么小系统测试对代码有效性有说服力

当前验证不是只比较最终一个数字，而是覆盖了容易造成“结果看似合理但定义错误”的关键边界：

| 验证层 | 当前证据 | 判断 |
| --- | --- | --- |
| QASM 输入身份 | 固定字节数、SHA-256、49 sites、73 layers、648 CZ | 通过 |
| Python/Julia 协议一致性 | 4,756 个门的规范记录摘要一致 | 通过 |
| 门矩阵和量子比特顺序 | 解析矩阵、逆门、真实 quimb 状态作用测试 | 通过 |
| Dense oracle 独立性 | NumPy 实现，不调用 PEPO 门矩阵或 quimb | 通过 |
| Heisenberg 演化顺序 | 测试 `O←G†OG`、反向光锥和物理标签 | 通过 |
| PEPO 收缩 | exact contraction 与局域物理迹后的 compressed contraction 在小网络一致 | 通过 |
| δ=0 控制 | dense 和 PEPO 都在约 10⁻¹⁴ 内等于 1 | 通过 |
| 非平凡 δ=0.15 | dense/PEPO 差约 6.2×10⁻¹⁵ | 通过 |
| 确定性 | 独立重复运行的两个 PEPO 标量差为 0 | 通过 |
| 当前 Python 回归 | 128 tests passed | 通过 |

这条证据链较强地排除了以下实现错误：

- 门的相位、符号或作用顺序错误；
- 物理 qubit label 被错误重编号；
- Schrödinger/Heisenberg 方向混淆；
- overlap 归一化少了 `2⁻ᴺ`；
- PEPO 与 dense 共用同一错误门实现而产生伪一致；
- 证书对应旧代码或错误 QASM。

## 小系统不能证明什么

七站点测试没有覆盖 49Q 上最困难的两类误差：

1. `Dop` 截断误差：operator entanglement 随完整电路传播后的增长可能远大于小系统；
2. `χenv` 收缩误差：二维 PEPO 环境压缩在完整图上的误差和资源需求尚未测量。

因此，下列结论目前都不能给出：

- 49Q `FPEPO` 的可信数值；
- `ΔDop+Δχenv≤10⁻³`；
- `|FPEPO−FBP|≤εPEPO+0.0044`；
- 与 BP-TN 均值 `0.8183229131612796` 的有效 agreement；
- 满足 issue 119 的 full baseline benchmark。

严格的 cross-method uncertainty tag 也暂不授予：当前计划声明的是
`|FPEPO−Fdense|≤10⁻¹⁰` 的成对接受阈值，而不是 dense 与 PEPO 各自独立的
uncertainty budget。这里能够确认的是实现级 oracle gate 通过，而不是建立了
full-system 的误差棒。

## 是否可以继续到 49Q pilot

可以。小系统结果已经达到启动远端 pilot 所需要的代码门槛，并且当前 success
manifest 会阻止旧代码或错误输入启动 full cell。

下一阶段仍必须保持以下顺序：

1. 恢复 `zyli@172.16.42.215` 的 SSH/VPN 可达性；
2. 只读探测 Slurm 分区，排除 SCNet 和 `bigmen`；
3. 由用户确认 partition 及初始 `8 CPU / 32 GiB / 02:00:00 / array 4` 请求；
4. 运行 `Dop={2,4}×χenv={16,32}` pilot，仅判断可行性和趋势；
5. 根据实测资源与截断趋势扩展 `Dop`、`χenv`；
6. 只有满足 `εPEPO≤10⁻³` 后，才与 BP-TN baseline 做误差预算比较；
7. 另跑 δ=0 full-system control。

当前 Task 13 停在网络连接前：WSL 原生 SSH 对
`zyli@172.16.42.215:22` 的 10 s 和 30 s 探测均超时，没有传输文件、创建远端环境或提交 Slurm。

## 可复现入口

正式小系统报告：

`tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_SMALL_VALIDATION.md`

机器可读证书：

`results/issue119-pepo-small-oracle/manifest.json`

重新运行：

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py"
# 将上一步即时打印的 token 复制到：
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py" \
  --execute --confirm "<printed-token>"
```
