# 内部研究笔记导航

这里保存第一批非常规模型的详细推导、风险清单和数值锚点。日常请先读
[`../docs/UNCONVENTIONAL_MODEL_BATCH1_RESULTS.md`](../docs/UNCONVENTIONAL_MODEL_BATCH1_RESULTS.md)；
它负责给出统一结论。本目录的模型卡用于逐式复核，不作为成果计数入口。

| 笔记 | 内容 |
|---|---|
| [U2/U5 模型卡](U2_U5_UNCONVENTIONAL_MODEL_CARDS.md) | Wilson-string gauge；分组 grade-charge ancilla |
| [U3/U4 模型卡](U3_U4_LOCALITY_TRADEOFF_MODEL_CARDS.md) | odd block-TN 连续时间模型；pseudo-Hermitian Stark；star-to-chain |

Tensor-square 的完整最小实例单独放在
[`../docs/TENSOR_SQUARE_EFFECTIVE_MWE.md`](../docs/TENSOR_SQUARE_EFFECTIVE_MWE.md)，
通用模型工厂的代码证书位于
[`../oracle/semigroup_model_factory.py`](../oracle/semigroup_model_factory.py)。

口径始终是：

```text
构造出完整模型 != 发现新的正性定理 != 发现新的无符号物理类
```

只有经过已知类排重、给出可扩展物理解释并达到 L3 的对象，才会改变成果总账的
“新无符号物理类”计数。
