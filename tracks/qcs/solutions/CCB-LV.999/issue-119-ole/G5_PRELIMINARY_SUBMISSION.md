# 49×1296 active OLE：BP-TN 阶段性结果

更新日期：2026-07-30

分类：**preliminary low-χ diagnostic；不是 χ 收敛后的 classical benchmark**

## 摘要

我们在 49-qubit heavy-hex、1,296-CZ 的 active operator Loschmidt echo
（OLE）实例上完成了 belief-propagation tensor network（BP-TN）的低 bond
dimension 扫描。当前成功样本数为 χ=64 的 20/20、χ=128 的 19/20 和 χ=192
的 19/20；两个缺失任务均因 walltime 在 layer 136–137/145 超时，而不是数值
失败或内存溢出。

在全部成功样本上，raw OLE 随 χ 从
`0.355781(χ=64)`、`0.500261(χ=128)` 增加到 `0.606713(χ=192)`。严格使用
18 个三点共同 seeds 后，两段 paired drift 分别为
`0.142822` 和 `0.109030`；后一段比前一段小约 24%，说明有限 χ 修正正在减小，
但 `χ=128→192` 的变化仍远大于 sampling SE。因此当前结果证明 active
问题在 χ≤192 可稳定计算，却没有证明 χ 收敛。

公开的 active raw BP-TN χ=512 中心值为 `0.88157984`，比当前 χ=192
成功样本均值高 `0.27486693`。两者方向上与“提高 χ 会保留更多相关性”一致，
但公开结果没有误差条，而且 χ、计算资源与可能的采样协议不同；当前数据不能据此
做受控 χ→512 外推，也不能给出 Agreement/Disagreement 认证。

## 1. 计算对象

| 项目 | 当前计算 |
| --- | --- |
| instance | active `49×1296` |
| graph | 49-site open heavy-hex |
| circuit | L=6，145 barriers，1,296 CZ gates |
| observable | `O=Z52 Z59 Z72` |
| target | raw `F=2⁻⁴⁹ Tr[O C† O C]` |
| perturbation | b=0.25，δ=0.15 |
| method | BP-TN Schrödinger-picture evolution |
| software | TensorNetworkQuantumSimulator.jl 0.4.4 |
| χ | 64、128、192 |
| seed namespace | `issue119-ole-v1`，seed IDs 1–20 |
| dtype / cutoff | ComplexF64 / `10⁻¹²` |
| BP | maxiter=25，tolerance=`10⁻⁸` |

active OpenQASM3 输入的 SHA-256 为
`3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0`。
它与 issue #11 的 OpenQASM2 attachment 在规范化 gate list、门序、物理 qubit
标签和角度上完全一致。

## 2. 当前成功样本

### 2.1 每个 χ 的全部成功样本

| χ | n | raw OLE mean | SE | max wall | max RSS |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 20 | 0.3557810933 | 0.0047950560 | 7.72 min | 1.865 GiB |
| 128 | 19 | 0.5002608855 | 0.0052585438 | 83.05 min | 4.420 GiB |
| 192 | 19 | 0.6067129125 | 0.0040011571 | 4.96 h | 9.702 GiB |

缺失项是：

- seed=20、χ=128：2 h walltime 时到 layer 136/145；
- seed=5、χ=192：5 h walltime 时到 layer 137/145。

58 个成功 cells 全部满足 `|F|≤1`、BP residual≤`10⁻⁸`，
`bp_nonconverged_layers=0`，且实际最大 bond 达到请求的 χ。当前没有观察到
NaN、OOM 或 BP message instability。

### 2.2 严格的 18-seed 三点共同集合

为了避免 χ 间样本组成差异影响趋势，取三个 χ 都成功的 seeds：

```text
1,2,3,4,6,7,8,9,10,11,12,13,14,15,16,17,18,19
```

| χ | n | matched mean | SE |
| ---: | ---: | ---: | ---: |
| 64 | 18 | 0.3553256604 | 0.0051216655 |
| 128 | 18 | 0.4981480740 | 0.0050908101 |
| 192 | 18 | 0.6071785691 | 0.0042012325 |

在共同 seeds 上：

```text
Δ64→128  = 0.1428224136
Δ128→192 = 0.1090304951 ± 0.0012502189 (SE)
```

最新 drift 是前一步的约 76%，说明趋势在减弱，但 `0.109` 仍约为 χ=192
sample SE 的 26 倍。**χ=192 明显不是数值平台区。**

## 3. 与已有结果比较

### 3.1 Baseline 复现提供的实现证据

相同 runner 和 seed namespace 已在较浅的 49×648 baseline 上完成 20-seed
χ=192/512 复现：

| baseline 49×648 raw | 当前值 | 公开值 | 当前−公开 |
| --- | ---: | ---: | ---: |
| BP-TN χ=192 | 0.8185618335 ± 0.0019847196 | 0.8202512915 | −0.0016894580 |
| BP-TN χ=512 | 0.8183229132 ± 0.0019858354 | 0.8216584890 | −0.0033355758 |
| Heisenberg PEPO Dop=512、χenv=64 | 0.8225508376 | 0.8216584890（BP χ=512） | +0.0008923486 |

baseline 两个 BP-TN 点都通过预先定义的复现容差。baseline 的 paired
`χ=192→512` drift 只有 `−0.0002389203`，而 active 的
`χ=128→192` drift 为 `+0.1090304951`。这表明当前 active 偏差主要来自电路
加深后迅速增加的有限 χ 误差，而不是已知的输入、observable 或基础 runner
错误。

baseline 与 active 是不同深度的电路，OLE 数值本身不能作为同一物理点直接比较；
这里比较的是方法对 bond dimension 的敏感程度。

### 3.2 Active 公开结果与当前阶段性结果

| active 49×1296 结果 | 数值 | normalization | 可比较性 |
| --- | ---: | --- | --- |
| 当前 BP-TN χ=192，19 seeds | 0.6067129125 ± 0.0040011571 | raw | 当前阶段性主结果 |
| Single-path Pauli MC | 0.619 | phase-insensitive approximation | 仅作低成本 diagnostic |
| IBM Heron R3 | 0.649–0.662 | global-rescaled | 不能与当前 raw 直接判 agreement |
| 公开 BP-TN χ=512 | 0.88157984 | raw | 同一 target，但 χ/误差预算不同 |
| 公开 BP-TN χ=512 | 0.94257142 | δ=0 rescaled | 不能与当前 raw 直接判 agreement |

当前 χ=192 raw mean 与 single-path MC 的中心值只差约 `0.0123`，但
single-path 方法忽略 Pauli path 相位干涉且没有可用误差预算，数值接近不能作为
正确性证明。

当前 χ=192 与公开 raw χ=512 相差：

```text
0.88157984 − 0.6067129125 = 0.2748669275
```

公开 raw 点延续了当前随 χ 上升的方向，但 χ=64、128、192 的曲线尚未进入平台，
因此不能用简单线性、幂律或指数模型可靠填补这段差距。公开 rescaled BP-TN 和
IBM 值改变了 normalization，只作为方法背景展示。

![Active BP-TN preliminary comparison](../../../../../results/issue119-ole-g5-active-pilot/preliminary-active-comparison.png)

图 A 的浅蓝点是每个成功 seed，深蓝点及误差棒是 mean±SE；χ=512 星号是无公开
误差条的 raw BP-TN 中心值。图 B 故意使用分类轴和不同 marker，表示这些公开值
具有不同 normalization 或近似，**不是一条共同的收敛序列**。

## 4. 阶段性结论

在不补算两个超时 seeds 的前提下，可以提交以下结论：

1. **实现有效性已有独立证据。** 49×648 baseline 已复现；active QASM2/QASM3
   gate list 已审计一致；58 个 active cells 均通过数值稳定性检查。
2. **active 低 χ 结果是稳定且可重复的。** 当前最佳成功样本统计为
   `Fraw(χ=192)=0.6067129±0.0040012 (SE,n=19)`。
3. **结果尚未 χ 收敛。** 严格共同 seeds 的最新 paired drift 为
   `0.1090305±0.0012502`，远大于 sampling error。
4. **公开 χ=512 raw 值与当前上升方向一致，但不能由当前点受控外推。**
   `0.88157984` 应作为外部高 χ 锚点，而不是当前结果的参考真值或拟合目标。
5. **量子硬件与 rescaled 结果不可和 raw 值直接排名。** 当前没有足够的
   δ=0 normalization 数据和双方法误差预算来认证 agreement/disagreement。

因此建议提交标签为：

> **Preliminary classical low-χ diagnostic for the 49×1296 active OLE
> instance, with transparent seed statistics and an unresolved finite-χ
> error.**

不建议使用“converged classical benchmark”“G5 passed”或“quantum/classical
agreement”作为结论。

## 5. 可复现文件

- 成功 cell manifests：`results/issue119-ole-g5-active-pilot/cells/`
- 阶段性机器数据：
  `results/issue119-ole-g5-active-pilot/preliminary-comparison.json`
- 阶段性表格：
  `results/issue119-ole-g5-active-pilot/preliminary-comparison.csv`
- 阶段性图：
  `results/issue119-ole-g5-active-pilot/preliminary-active-comparison.png`
  和 `.pdf`
- 完整 G5 gate：
  `results/issue119-ole-g5-active-pilot/g5-assessment.json`
- 生成命令：

```bash
python3 \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/summarize_active_preliminary.py \
  --run-dir results/issue119-ole-g5-active-pilot
```

## 6. 数值来源

- Tracker 49×648 instance：issue #10；
- Tracker 49×1296 instance：issue #11；
- 公开 baseline BP-TN χ=192/512：Tracker issues #15/#18；
- 公开 active BP-TN raw/rescaled：Tracker issues #19/#20；
- Single-path Pauli MC：Tracker issue #63；
- 当前 baseline：`OLE_G2_FINAL_REPORT.md`；
- 当前 active：`g5-assessment.json` 与本报告附带的 preliminary 数据文件。
