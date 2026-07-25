## 赛道核心信息确认

### 1. 论文复现目标

- **复现对象**：*[TensorCircuit-NG: A Universal, Composable, and Scalable Platform for Quantum Computing and Quantum Simulation](https://arxiv.org/abs/2602.14167)*
- **核心任务**：参考该论文的图 2，在无分布式（单机）环境下，复现并 profiling 一维横场伊辛模型（1D TFIM）VQE 单步（期望值前向计算 + 梯度反向传播）的时间（编译时间和运行时间）与空间消耗。
- **算力分级指标**：
  - **（有 GPU）**：32-qubit, 16-layer VQE 线路。
  - **纯 CPU 基准**：24-qubit, 12-layer VQE 线路。

### 2. 知识库起步语料

为赛道提供以下文献，兼顾张量网络理论与计算框架的工程实现：

- **第一代软件白皮书**：[TensorCircuit: a Quantum Software Framework for the NISQ Era](https://arxiv.org/abs/2205.10091)
- **第二代软件白皮书**：[TensorCircuit-NG: A Universal, Composable, and Scalable Platform for Quantum Computing and Quantum Simulation](https://arxiv.org/abs/2602.14167)
- **Cotengra 核心文献**：[Hyper-optimized tensor network contraction](https://arxiv.org/abs/2002.01935)
- TensorCircuit-NG 开源框架（自带基础 Harness）：https://github.com/tensorcircuit/tensorcircuit-ng

### 3. 在线讨论时间

请从以下两个时段中选：

- **5/26（周二）11AM**
- **5/27（周三）11AM**

## 挑战问题：极限效能的 VQE 数值模拟方案

**核心目标**

构建一个可持续迭代、可自动化评估的 Harness 框架，利用半自动化的算法与工程联合创新，实现一个在**空间效率**和**时间效率**（包含首次 JIT 编译效率与后续运行时执行效率）上超越当前 `tensorcircuit-ng` 官方基线的 VQE 计算方案。更进阶的，这套 Harness 框架可以自动化地可靠地帮助用户优化基于TensorCircuit-NG的代码脚本性能。

**创新切入点 (Gadgets) 参考池**

参赛团队可考虑在此 Harness 中集成并组合以下维度的优化策略：

算法层面：张量网络缩并路径搜索，切片搜索

工程层面：scan 控制流、aot 编译利用，算子融合与定制、自动微分检查点、内存 offloading、混合精度等。