# 二维神经网络 VMCRG 基础挑战

## 代码与结果声明

- 本项目是依据论文和补充材料编写的独立复现，不是作者公开的原始代码。
- 原论文使用有限算符展开；这里的神经网络部分是研究扩展，不属于论文原结果。
- 当前实现是 `13 项线性偏置 + D4/Z2 局域神经残差`，不是纯神经网络替代。
- 当前 `PASS` 只表示下述二维基础挑战全部通过，不表示 Table I 或三维自旋玻璃已经完成。
- 所有验收量均由冻结参数后的独立样本计算，训练轨迹不参与最终验收。

## 完整代码在哪里

代码没有藏在输出文件中，也没有压缩成单个超长脚本。完整实现按职责分成四层，每个算法只有一份：

1. `reproduce.py`：唯一用户入口，检查参数并先运行测试；
2. `scripts/neural_challenge.py`：按顺序完成训练、验证、投影、消融、自相关和报告；
3. `src/vmcrg_ref/hybrid_neural.py`：实现混合 Metropolis、局部能量差、多 walker 和 Adam 更新；
4. `src/vmcrg_ref/neural_energy.py`：实现对称神经能量、解析梯度和精确局部缓存。

实际调用顺序为：

```text
python reproduce.py neural-easy
  -> _neural_easy()
  -> neural_challenge.run()
  -> train()
  -> validate()
  -> project()
  -> ablate()
  -> compare_autocorrelation()
  -> report()
```

训练阶段内部调用：

```text
HybridNeuralVMCRGOptimizer.run()
  -> 16 个 LinearNeuralBiasedMetropolis.run_sweeps()
  -> 计算 biased/target 神经梯度
  -> Adam.update()
  -> 刷新神经局部查找表
```

因此 `scripts/neural_challenge.py` 是完整实验代码，两个 `src` 文件是它调用的核心算法库。把三者机械复制到一个文件只会产生重复实现，不会让算法更完整。

## 范围

目标是在 `45×45` 二维 Ising 模型上，用神经网络增强重整化哈密顿量，并同时满足：

1. `3×3` majority-rule 粗粒化；
2. 块自旋分布接近均匀目标；
3. 完整 13 维固定点不漂移；
4. 神经残差在独立样本上确实降低变分目标；
5. 临界自相关时间明显下降。

这部分是对 PRL 119, 220602 的研究扩展，不是论文原结果。

## 均匀参考分布不是物理温度

优化器默认使用 `UniformIsingReference2D`：每个块自旋独立等概率取
`-1/+1`。它的作用是把带偏粗粒化分布压平，从最优偏置恢复有效哈密顿量，
不是把微观 Ising 模型的温度设置成无穷高。物理温度始终由微观无量纲耦合
`K=J/(k_B T)` 决定。

参考分布接口同时要求 `sample` 和 `log_probability`。若未来使用非均匀参考
`p_ref`，必须按

\[
H'(\mu)=-V_{\min}(\mu)-\log p_{ref}(\mu)+\mathrm{const}
\]

恢复重整化哈密顿量。只有样本生成器而没有 `log p_ref` 的外部数据源会破坏
这一关系，因此当前正式二维挑战固定使用均匀参考。

当前实现严格限定为二维：平方晶格、D4 对称和二维 `3x3` 多数块。它不能
直接用于三维模型。

## 唯一实现

重整化偏置写成

\[
V(\mu)=J\cdot S_{13}(\mu)+V_\theta(\mu).
\]

- `J·S13`：保留距离 2、3 的两体/四体长程结构；
- `V_theta`：平移、D4、Z2 对称的 `3×3` patch MLP 残差；
- 每次单自旋翻转只更新受影响的算符和局域查找表；
- 均匀目标项 `<dV/dtheta>_target` 显式采样；
- 后半段参数做预声明轨迹平均。

核心代码只有：

- `src/vmcrg_ref/neural_energy.py`：对称神经能量和局部缓存；
- `src/vmcrg_ref/hybrid_neural.py`：混合 Metropolis 与变分优化；
- `scripts/neural_challenge.py`：训练、冻结验证、投影、消融、自相关、报告；
- `scripts/neural_confirmation.py`：锁定的五训练种子确认、分层 bootstrap 和最终硬门槛；
- `reproduce.py neural-easy`：用户入口。
- `reproduce.py neural-confirm`：正式多随机种子确认入口。

## 运行

快速连接测试：

```powershell
python reproduce.py neural-easy --preset smoke --output tmp/neural_smoke
```

正式计算必须使用新目录：

```powershell
python reproduce.py neural-easy --preset formal `
  --output output/neural_hybrid_easy_formal_v2
```

正式参数为 16 walkers、3000 steps、每步 20 sweeps，共 960000 walker-sweeps。

## 历史单训练种子结果

目录：`output/neural_hybrid_easy_formal_v2/`

| 验收项 | 结果 | 门槛 |
|---|---:|---:|
| 13 项最大等价上界 | 0.001899 | ≤ 0.02 |
| held-out 3×3 excess-TV 上界 | 0.001546 | ≤ 0.02 |
| 固定点 L∞ 残差 | 0.000520 | ≤ 0.001 |
| 固定点相对 L2 残差 | 0.002209 | ≤ 0.005 |
| 神经残差 ΔΩ 的 mean+2SE | -2.83e-7 | < 0 |
| 有偏平均 τint | 4.909 | — |
| 无偏平均 τint | 188.170 | — |
| 配对 τ 比值上界 | 0.04994 | ≤ 0.5 |

`log(mean(exp(-V)))` 使用链内 jackknife 修正有限样本偏差。综合结果见
`challenge_report.json`。

上述 `formal_v2` 是单训练种子结果。当前代码重新执行的 `formal_v3` 在冻结分布和
13 维固定点投影上通过，但神经残差消融的 `mean+2SE=1.258e-6>0`，因此单训练
种子 PASS 不再作为最终挑战结论。

## 锁定的第一阶段确认协议

协议文件为 `config/neural_confirmation_v1.json`，在正式计算前固定：

- 5 个训练种子；
- 每个模型 3000 steps、16 walkers、每步 20 sweeps；
- 每个模型 32 条独立消融链；
- 训练、冻结验证、投影、消融、自相关和 bootstrap 使用互不重复的随机流；
- 至少 4/5 个模型的消融点估计为负；
- 两层 bootstrap 的 `mean+2SE<0`；
- 所有模型都必须通过冻结分布与固定点投影；
- 聚合消融通过后才运行自相关；
- 所有模型的自相关门与聚合自相关门都必须通过。

连接测试：

```powershell
python reproduce.py neural-confirm --preset smoke `
  --output-root tmp/neural_confirmation_smoke
```

正式确认必须写入全新目录：

```powershell
python reproduce.py neural-confirm --preset formal `
  --output-root output/neural_confirmation_formal_v1
```

运行开始前会保存协议、固定点输入、Python/NumPy 版本和关键代码 SHA-256。
正式聚合消融失败时程序会停止，不会用自相关结果事后补救。

## 边界

当前完成了二维混合神经挑战的单种子可行性实验；最终多种子确认尚未运行。尚未完成：

- 完全去掉 13 项跳连的纯神经表示；
- 把 `H'=-J·S13-V_theta` 原样作为下一轮微观哈密顿量的连续多轮 RG；
- 三维 `45³` 自旋玻璃转变点。
