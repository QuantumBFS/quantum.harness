# 第四阶段：纯神经 VMCRG 可行性试验结果 v1

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: run + validate
- Origin Date: 2026-07-20
- Verification Status: VERIFIED
- Version Label: neural_replacement_pilot_result_v1

## 结论

L=45 的纯神经偏置试验得到 `GO_FORMAL_PROTOCOL_DESIGN`。这只说明五个预注册方向均优于零偏置或无偏基线，允许设计正式多种子协议；不代表纯神经挑战已经通过，也不代表论文 Table I 已复现。

## GO/NO-GO 门槛

| 指标（越小越好） | 纯神经 | 对照/阈值 | 结果 |
|---|---:|---:|---|
| 13项算符最大 `abs(mean)+2SE` | 0.506684 | 零偏置 0.644400 | PASS |
| patch-TV 上界 | 0.544105 | 零偏置 0.650699 | PASS |
| 固定点投影 L∞ 残差 | 0.354700 | 零偏置 0.369539 | PASS |
| 留出集 `ΔΩ` 上界/块格点 | -0.031101 | 0 | PASS |
| 自相关时间配对比值上界 | 0.437865 | 1 | PASS |

纯神经采样接受率为 0.250318，零偏置为 0.224135；该指标没有参与 GO/NO-GO 判定。

## 尚未达到的绝对目标

- 算符分布要求不超过 0.02，当前为 0.506684；
- patch-TV 要求不超过 0.02，当前为 0.544105；
- 固定点投影要求 L∞ 不超过 0.001 且相对 L2 不超过 0.005，当前分别为 0.354700 和 0.958928；
- 当前仅有一个训练种子、100 个变分步，不能估计训练种子间不确定性。

因此本试验只证明学习方向正确，尚未证明网络独立表示了重整化哈密顿量。

## 独立复算

- 使用保存的8条零偏置链重新计算均值、标准误和上界，全部与报告精确一致；
- 使用原始4对自相关时间重新计算配对比值上界，结果为 0.4378645332042215，与报告精确一致；
- 使用13项目标耦合与神经投影重新计算 L∞ 残差，结果为 0.3546997488533366，与报告精确一致；
- 第一版与补存链级证据后的第二版全部判定标量精确一致；
- 所有保存数值均为有限值。

正式证据位于 `output/neural_replacement_pilot_v1/pilot_assessment_v2.json`。第一版 `pilot_assessment.json` 保留且未覆盖。

## Statistical Interpretation

总体置信度为 `CAUTION`。五项门槛均通过，但这是短程单训练种子 pilot；方向性改善不能外推为正式挑战成功。正式阶段必须预先锁定训练长度、种子、样本量、停止规则和失败规则。

## Fallacy Scan

- Coverage: 11/11 checked；未发现 RED_FLAG；
- Look-elsewhere：五项门槛全部报告且要求同时通过，没有只挑有利指标；
- Garden of forking paths：GO/NO-GO 门槛在读取结果前已写入协议，本阶段未事后改变；
- Survivorship bias：8条验证链和4对自相关链全部纳入；
- Simpson、ecological、Berkson、collider、base-rate、regression-to-mean、correlation/causation、reverse-causality：本算法模拟比较不涉及相应总体或因果外推。

## 下一步边界

下一阶段只能设计并冻结正式多种子协议。不能直接把 pilot 参数复制为成功配置，也不能根据正式中途结果调参。
