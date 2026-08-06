# Quantum Harness 功能改动汇报

**范围。** 本汇报聚焦 Harness 功能改动，而非具体物理课题、模型、数值结果或论文复现内容。比较基准为公开仓库 [QuantumBFS/quantum.harness](https://github.com/QuantumBFS/quantum.harness) 的 `main` 分支（截至 2026-07-29）；本地工作区位于提交 `9ebcab9`，而公开仓库最新提交为 `a0562a5`。

## 一、总体定位

简单来说，我们将原本以“方法卡片 + agent skill”为核心的 Quantum Harness，扩展成一套更完整的科研执行平台。改动方向是平台化的完整实现，以及工程和工作流层面的迭代：

- 从单次指导或 prompt 交互扩展为**可执行、可验证、可恢复的工作流**；
- 从本地脚本扩展为**集群配置、预检、提交、监控和结果回收**的闭环；
- 从单一方法入口扩展为“问题定义 → 方法选择 → 工具安装 → 实验 → 验证 → 报告/挑战”的技能编排体系。

## 二、新增或显著强化的 Skills

### 1. 实验生命周期工作流

形成了一组覆盖实验全周期的 skill：

| Skill | 作用 |
|---|---|
| `/experiment` | 编排从研究问题到可复现实验的完整流程 |
| `/experiment-mvp` | 快速建立最小可运行原型 |
| `/experiment-smoke` | 以最小非平凡规模进行运行冒烟测试 |
| `/experiment-verify` | 用解析极限、基准结果和一致性检查验证脚本 |
| `/experiment-refactor` | 在保持结果不变的前提下，将单体脚本整理为模块化工程 |
| `/experiment-organize` | 检查项目结构、测试与知识记录 |
| `/experiment-scan` | 将验证过的脚本推进到生产级参数扫描 |
| `/parameter-scan` | 规划、恢复、收集、校验和绘制笛卡尔参数扫描 |
| `/scaling-fit` | 执行有限尺寸标度拟合、bootstrap 置信区间和残差诊断 |
| `/cross-method-check` | 用独立方法交叉验证单方法结果 |

这部分的核心改动是把“给出建议”变为“带有检查点、产物和验收条件的实验流程”。这也适配我们聚焦的 ED 赛道：该赛道通常涉及大量数值试验、观测量或期望值提取，以及物理结果分析。

## 三、知识库拓展设计：面向具体课题的 Project Knowledge Layer

除通用 `.knowledge/` 中的方法、模型和文献卡片外，我们新增了**面向具体研究课题的项目知识库**（project-cooked knowledge）。其目的不是重复通用物理知识，而是沉淀某一课题在实际推进过程中形成、且后续计算必须继承的上下文。

### 1. 分层知识库结构

知识库分为两个层次：

| 层次 | 位置 | 内容与作用 |
|---|---|---|
| 通用知识库 | `.knowledge/` | 面向所有课题的模型、数值方法、文献、性质检查表与 benchmark 卡片 |
| 课题知识库 | `tracks/<track>/knowledge/` | 面向某个具体课题的已验证基准、历史运行结果、参数约定和已知陷阱 |

例如，在 ED 的 Hubbard pump 课题中，知识库位于：

```text
tracks/ed/hubbard-pump/knowledge/
├── README.md       # 课题知识入口与索引
├── benchmarks.md   # 文献或解析基准
├── prior-runs.md   # 本 Harness 已验证的历史运行结果
└── notes.md        # 参数约定、数值陷阱和经验说明
```

这种结构将“通用方法知识”与“本课题已经付出的试错成本”明确区分：前者回答“通常应该如何做”，后者回答“这个项目此前做过什么、哪些值可信、哪些做法会出问题”。

### 2. `/explore-on-project-knowledge` Skill

新增 `/explore-on-project-knowledge` skill，作为访问项目知识库的统一入口。其主要流程为：

1. 根据当前上下文定位目标课题的 `tracks/<track>/knowledge/`；
2. 读取 `README.md` 作为知识入口；
3. 沿链接读取 `benchmarks.md`、`prior-runs.md` 与 `notes.md`；
4. 将内容压缩成面向计算决策的摘要，而不是把原始笔记直接堆给 agent；
5. 返回三类关键信息：已知 benchmark、Harness 历史结果和 critical notes。

输出结构被约束为紧凑表格：

| 类别 | 典型内容 | 对后续计算的作用 |
|---|---|---|
| Benchmarks | 文献值、解析极限、已知相变点或对称性结论 | 用于设定验证目标与判断数值是否合理 |
| Prior runs | 已验证运行的参数、系统尺寸、计算值、状态 | 避免重复已完成计算，并为新扫描选择可信起点 |
| Critical notes | 符号约定、有限尺寸效应、gap closing、收敛问题、危险参数区间 | 避免已知陷阱，指导诊断与资源分配 |

### 3. 与核心工作流的关联

项目知识库不是被动文档，而是接入 agent 的任务初始化过程：

```text
/solve 或 /reproduce-paper
        ↓
识别对应 track
        ↓
检查 tracks/<track>/knowledge/README.md
        ↓
调用 /explore-on-project-knowledge
        ↓
以 benchmark、历史结果和注意事项约束方案
        ↓
/experiment-mvp → /experiment-smoke → /experiment-verify
        ↓
/experiment-organize 回写新的已验证知识
```

具体来说：

- `/solve` 和 `/reproduce-paper` 在映射到某个 track 后，检查该课题是否存在 `knowledge/README.md`；存在时，先调用 `/explore-on-project-knowledge`，再提出计算方案；
- `/experiment-mvp` 在构建最小原型前读取项目知识，用已有 benchmark 和 prior runs 确定合理的初始参数、系统尺寸和预期输出；
- `/experiment-organize` 在验证完成后，将新的可信结果追加到 `prior-runs.md`；若发现新的文献基准或重要限制，则更新 `benchmarks.md` 或 `notes.md`。

因此，知识流形成闭环：

```text
已有研究记录
    → 项目知识库
    → agent 读取并约束实验设计
    → 实验、验证与诊断
    → 新的可信运行结果
    → 回写项目知识库
```

### 4. 对 ED 赛道的意义

对于 ED 课题，项目知识库尤其重要。ED 虽然适合精确计算有限系统，但实际项目通常会涉及大量相近而不完全相同的数值试验：不同尺寸、边界条件、填充数、相互作用强度、泵浦路径、观测量定义和有限尺寸标度方案。

如果没有课题知识库，agent 每次进入任务都可能重新面对以下问题：

- 哪些系统尺寸已经跑过，哪些仍值得计算；
- 哪些参数点是已验证的 benchmark；
- 观测量采用何种归一化、符号和边界条件约定；
- 哪些 gap closing、简并或数值不稳定是物理现象，哪些是实现伪影；
- 哪些参数区域需要更细扫描、额外的对称性分块或独立交叉验证。

Project Knowledge Layer 将这些信息以版本化、可读取、可回写的形式保存下来，使 agent 不再只依赖通用 prompt 或临时上下文，而能继承该课题的计算历史和经验。它将课题推进从“单次 agent 对话”转变为“可累积的研究记忆”。

### 5. 与原始 Quantum Harness 的差异

相较于以通用 `.knowledge/` 卡片为主的知识组织方式，这一改动补上了“项目级、结果级、经验级”知识层：

| 能力 | 通用 `.knowledge/` | Project Knowledge Layer |
|---|---|---|
| 适用范围 | 所有模型与方法 | 特定 track / 特定课题 |
| 知识来源 | 方法论、文献、模型定义 | 课题 benchmark、运行记录、排错经验 |
| 更新频率 | 相对稳定 | 随项目计算进展持续更新 |
| 主要用途 | 选择方法与理解背景 | 约束参数设计、复用结果、避免重复试错 |
| 与实验的关系 | 提供一般指导 | 形成“读取 → 计算 → 验证 → 回写”的闭环 |

这一设计使 Quantum Harness 的知识库从静态参考资料，扩展为可服务于长期研究项目、持续积累的 agent memory。

## 结论

这批改动的核心贡献是把 Quantum Harness 从“面向 agent 的研究知识库和提示集合”，推进为“可运行、可验证、可提交、可展示、可教学的研究工作流平台”。

其中最具工程辨识度的四项是：

1. profile 驱动的 Slurm 闭环；
2. 可恢复参数扫描；
3. 可审计有限尺寸标度分析；
4. 与 GitHub Pages/离线 Lattix 可视化联动的报告与网站体系。
