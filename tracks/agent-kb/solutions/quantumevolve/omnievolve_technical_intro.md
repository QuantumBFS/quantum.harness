# OmniEvolve 技术介绍

> 基于源码调研（v0.2.0, 23,730 行 Python, 87 个测试文件）

---

## 1. 一句话定义

OmniEvolve 是一个**受控元进化框架**（Controlled Meta-Evolution Framework）：
用 LLM 驱动代码变异，在沙箱中评估候选，通过 MCTS 引导的进化搜索自动改进算法——
同时用分层治理约束防止进化过程本身失控。

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (typer)                              │
│   run · status · best · export · policy · audit · recover       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    EvolutionEngine                               │
│  ┌─────────────────────┐    ┌────────────────────────────────┐  │
│  │     Fast Loop        │    │         Slow Loop              │  │
│  │  (每代 11 步)        │    │  (每 N 代策略窗口评估)         │  │
│  │                     │    │                                │  │
│  │  Router → Parent    │    │  Telemetry → Health →          │  │
│  │  → Crossover →      │    │  MetaPlanner → Governance →    │  │
│  │  Director → Novelty │    │  Champion/Challenger →         │  │
│  │  → Coder → Critic → │    │  Replay → Promote/Reject       │  │
│  │  Store → Eval →     │    │                                │  │
│  │  Sandbox → Parse    │    │                                │  │
│  └─────────────────────┘    └────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼───────┐  ┌──────────▼──────────┐  ┌───────▼───────┐
│    Agents      │  │      Storage        │  │    Sandbox     │
│ Director       │  │ SQLite DB           │  │ TrustedSubproc │
│ Coder          │  │ CAS (SHA-256)       │  │ Docker         │
│ Critic         │  │ Vector Index        │  │ Hardened       │
│ Fusion         │  │ Graph Store         │  │ Monty          │
│ Meta           │  │ Repositories        │  │                │
│ Router         │  │ Artifact Store      │  │                │
│ CircuitBreaker │  │                     │  │                │
└───────────────┘  └─────────────────────┘  └───────────────┘
```

---

## 3. Fast Loop：单代进化的 11 步

每一代（每个候选）经历完整的 11 步链：

| 步骤 | 组件 | 作用 |
|------|------|------|
| 1 | `ModelRouter` | 按角色（Director/Coder/Critic）分配 LLM 模型 |
| 2 | `ParentSelector` + `ProgressiveMCGS` | MCTS 引导选择父代（Beta 后验 UCB） |
| 3 | `CrossoverOperator`（可选） | 多父代跨分支融合（2-3 个高分候选特征整合） |
| 4 | `Director` | 生成进化思想（分层改进策略 Tier 1/2/3） |
| 5 | `NoveltyGate` | 多级新颖性门（Embedding→AST→Epiplexity→行为→LLM） |
| 6 | `Coder` | 生成代码（SEARCH/REPLACE diff / 全量重写 / 融合模式） |
| 7 | `Critic` | 静态审查 + 执行反馈审查（带重试） |
| 8 | `ArtifactStore` | 保存源码 / 血统 / 向量索引任务 |
| 9 | `TaskEvaluator.build_plan` | 构建评估计划（多步沙箱执行方案） |
| 10 | `SandboxBackend.execute` | 沙箱执行候选代码 |
| 11 | `parse_result` | 更新 best / island / MCTS / memory / router / budget |

**Phase 3 异步拆分**：步骤 1-10 在 `prepare()` 中执行（无共享状态变更，可并行），
步骤 11 在 `commit_result()` 中串行执行（所有共享状态更新）。

---

## 4. Slow Loop：受控元进化

每 `health_window_gens` 代触发一次策略级自省：

```
TelemetryAggregator → HealthPolicy.assess → MetaPlanner.propose
→ Governance 风险分级 → 创建 Challenger → Replay/Canary 比较 → Promote/Reject
```

### 治理分级（Governance）

| 级别 | 权限 | 示例 |
|------|------|------|
| **L0** | 可自动允许 | 调整探索常数 C、种群微调 |
| **L1** | 必须 Replay/Canary 验证 | 修改 Prompt 模板、切换选择策略 |
| **L2** | 默认禁止 | 修改评估器语义、变更 score 定义 |

**核心不变量**：评估语义永久不可变（L2 禁止）。进化可以改搜索策略，但不能改"什么算好"。

---

## 5. 搜索算法：Progressive MCGS

不是标准 MCTS，而是**渐进式蒙特卡洛图搜索**（Monte-Carlo Graph Search）：

- **Beta 回传**（Bayesian backpropagation）：每个节点维护 Beta(α, β) 后验分布，
  而非 frequentist mean。少量访问的节点保留不确定性（宽后验），不因单次低分被剪枝。
- **UCB/PUCT 选择**：探索项 + Beta 不确定性 → 自然探索"1+1>2"组合分支
- **虚拟损失**：支持并行评估时的去重
- **分段衰减探索常数 C(t)**：前期广搜，后期收敛
- **强制反向传播**：后期加速收敛 + 维持多样性

---

## 6. 多级新颖性门（NoveltyGate）

防止进化在已知区域重复搜索：

| 级别 | 方法 | 成本 | 作用 |
|------|------|------|------|
| 1 | Embedding 相似度 | 低 | 初筛（阈值 0.92） |
| 2 | AST/结构签名 | 极低 | 检测变量重命名等表面修改 |
| 3 | Epiplexity | 极低 | 可学习新奇性（结构丰富性 × 可压缩性 × 新颖性） |
| 4 | 行为签名 | 中 | 执行小样本比较输出特征 |
| 5 | LLM 判断 | 高 | borderline 时触发（0.88-0.96 区间） |

**Epiplexity**（基于 arXiv:2607.18433 LEARNABLE_NOVELTY 论文）是独有设计。

核心思想：奖励“对有界观察者来说可学习的新结构”，同时免疫两种退化：
- “噪声电视”（纯随机代码，看起来复杂但无规律可学）
- “暗室”（纯重复代码，没有新信息）

#### 公式

```
S_φ(code) = 0.4 × richness + 0.3 × compressibility + 0.3 × novelty
```

三个分量各自在“临界复杂度”处取最大值：

| 分量 | 计算方式 | 平凡代码 | 随机代码 | 临界代码 |
|--------|---------|---------|---------|----------|
| **richness** | AST 节点类型归一化熵 × 复杂度（几何均值） | ≈ 0（只有一种节点） | 低（熵高但复杂度爆表） | 高（中等熵 × 中等复杂度） |
| **compressibility** | gzip 压缩比的倒 U 形高斯（center=0.4, σ=0.25） | 低（压缩比≈0.1，偏离中心） | 低（压缩比≈1.0，偏离中心） | 高（压缩比≈0.3-0.6） |
| **novelty** | 与最近 20 个历史签名的 Jaccard 距离 | 0（与历史完全重复） | 1（全新） | 取决于历史 |

#### 分量 1：结构丰富性 (richness)

```python
# 1. 解析 AST，收集所有节点类型
node_types = [type(node).__name__ for node in ast.walk(tree)]
# 例如: ['Module', 'FunctionDef', 'arguments', 'arg', 'Return', 'BinOp', 'Add', ...]

# 2. 计算归一化 Shannon 熵
entropy = -Σ p_i × log2(p_i)          # p_i = count(type_i) / total
normalized_entropy = entropy / log2(n_types)   # ∈ [0, 1]

# 3. 结构复杂度（节点总数对数缩放）
complexity = min(log2(n_total) / 10.0, 1.0)   # ~1000 节点 → 1.0

# 4. 临界性 = 几何均值（两者都中等时最大）
richness = √(normalized_entropy × complexity)
```

**为什么用几何均值？** 算术均值会让“极高熵 + 极低复杂度”或“极低熵 + 极高复杂度”得到中等分，
几何均值则要求两者**同时**中等才给高分——这正是“临界复杂度”的定义。

#### 分量 2：可压缩性 (compressibility)

```python
ratio = len(gzip.compress(code)) / len(code)   # 压缩比 ∈ (0, 1]

# 倒 U 形高斯：在 ratio=0.4 处取最大值 1.0
score = exp(-(ratio - 0.4)² / (2 × 0.25²))
```

直觉：
- `ratio ≈ 0.1`：极度可压缩 → 代码是 `return 42` 之类的平凡东西 → 低分
- `ratio ≈ 1.0`：不可压缩 → 代码是随机字符串 → 低分
- `ratio ≈ 0.4`：有结构但非平凡 → 有规律可学 → 高分

#### 分量 3：新颖性 (novelty)

```python
# 计算代码结构签名（AST 节点类型序列，截取前 50 个）
sig = "Module|FunctionDef|arguments|arg|Return|BinOp|Add|..."

# 与最近 20 个历史签名计算 Jaccard 距离
for hist in history[-20:]:
    similarity = |sig_tokens ∩ hist_tokens| / |sig_tokens ∪ hist_tokens|

novelty = 1.0 - min_similarity   # 与历史最相似的 → 新颖性最低
```

#### 举例：三种代码的得分对比

**① 平凡代码**（硬编码作弊）：
```python
def solve(n):
    return 92
```
- richness: AST 只有 `Module, FunctionDef, arguments, arg, Return, Constant` 共 6 种节点，
  n_total=8，complexity=log2(8)/10=0.3，normalized_entropy≈0.92 → richness=√(0.92×0.3)≈**0.53**
- compressibility: 代码极短（~30 bytes），gzip 后反而更大（header 开销），ratio≈1.5+
  → 高斯得分≈**0.0**
- novelty: 如果历史中已有类似结构 → **0.0**
- **总分 ≈ 0.4×0.53 + 0.3×0.0 + 0.3×0.0 = 0.21**

**② 随机代码**（无结构噪声）：
```python
xk9 = lambda q,z: q^z if q>z else z-q  # 无意义的随机组合
def f(a,b,c,d,e,f,g,h,i,j,k,l,m):
    return (((a^b)^c)^d)^e if a else (((f^g)^h)^i)^j
```
- richness: 节点类型多但节点总数少，complexity 低 → richness≈**0.4**
- compressibility: 随机变量名不可压缩，ratio≈0.85 → 高斯得分≈**0.13**
- novelty: 可能是新的 → **0.8**
- **总分 ≈ 0.4×0.4 + 0.3×0.13 + 0.3×0.8 = 0.44**

**③ 临界代码**（有结构但非平凡的算法改进）：
```python
def count_nqueens(n):
    """Bitmask backtracking with symmetry pruning."""
    full = (1 << n) - 1
    count = 0
    def backtrack(cols, diag_l, diag_r, depth):
        nonlocal count
        if cols == full:
            count += 1
            return
        avail = full & ~(cols | diag_l | diag_r)
        while avail:
            bit = avail & (-avail)
            avail -= bit
            backtrack(cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1, depth + 1)
    backtrack(0, 0, 0, 0)
    return count // 2  # symmetry: only count first-half placements
```
- richness: ~15 种节点类型，~60 个节点，normalized_entropy≈0.85，complexity=log2(60)/10≈0.6
  → richness=√(0.85×0.6)≈**0.71**
- compressibility: 有重复结构（`diag_l | bit`、`diag_r | bit`），ratio≈0.45
  → 高斯得分≈**0.97**
- novelty: 与历史种子差异明显（新增 symmetry pruning）→ **0.7**
- **总分 ≈ 0.4×0.71 + 0.3×0.97 + 0.3×0.7 = 0.79** ← 最高

#### 设计意图

这个得分分布恰好引导进化向“有结构的新算法”方向搜索：
- 硬编码作弊（0.21）和随机变异（0.44）都被低分拑制
- 真正的算法改进（0.79）获得最高新颖性奖励
- 全部计算在 O(n) 内完成（一次 AST parse + 一次 gzip），无需 LLM 调用

---

## 7. Agent 角色

| Agent | 职责 | 关键设计 |
|-------|------|---------|
| **Director** | 提出进化思想 | 分层策略：Tier 1（调参）→ Tier 2（换组件）→ Tier 3（换范式），由停滞级别触发 |
| **Coder** | 生成代码 | 4 种模式：TARGETED_DIFF / FULL_REWRITE / FUSION_AWARE / STEPWISE |
| **Critic** | 审查代码 | 静态审查 + 执行反馈审查 + 调试专用审查（注入历史修复案例） |
| **Fusion** | 多方案整合 | 从多个高分候选中提取互补特征 |
| **Meta** | 策略自省 | Slow Loop 中的 MetaPlanner 角色 |
| **Router** | 模型分配 | 按角色和任务复杂度路由到不同 LLM |
| **CircuitBreaker** | 容错 | API 超时/失败时的熔断保护 |

代码生成格式采用 **SEARCH/REPLACE diff**（类 AlphaEvolve）：
```
<<<<<<< SEARCH
# 要替换的原始代码
=======
# 新代码
>>>>>>> REPLACE
```

---

## 8. 分层记忆（L0-L4）

| 级别 | 范围 | 内容 |
|------|------|------|
| L0 | 当前分支 | 本次变异的 thought → outcome 映射 |
| L1 | 当前实验 | 实验级统计（成功率、最佳策略） |
| L2 | 任务族 | 跨实验的可复用模式 |
| L3 | 领域 | 领域级启发式 |
| L4 | 全局 | 全局元策略 |

检索采用**分层预算**：每级分配固定 token 预算，避免低层记忆淹没高层洞察。
存储使用 FTS5（全文）+ 向量索引（语义）混合检索。

---

## 9. 存储层

| 组件 | 技术 | 作用 |
|------|------|------|
| **Database** | SQLite | 元数据、评估记录、实验追踪 |
| **ArtifactStore** | SHA-256 CAS | 内容寻址存储，自动去重 |
| **CASCodeStore** | Manifest + CAS | 多文件快照，血统追踪 |
| **VectorIndexer** | zvec / numpy | 嵌入向量索引（新颖性门 + 记忆检索） |
| **GraphStore** | NetworkX | 进化图（血统、岛间迁移） |
| **Repositories** | CandidateRepo / ExperimentRepo / PromptRepo | 领域对象持久化 |

---

## 10. 沙箱后端

| 后端 | 隔离级别 | 适用场景 |
|------|---------|---------|
| `TrustedSubprocessBackend` | 无隔离（仅 rlimit） | 本地开发、可信代码 |
| `DockerBackend` | 容器级 | 生产环境 |
| `HardenedBackend` | 强化容器 | 安全敏感 |
| `MontyBackend` | pydantic-monty | 实验性 |

评估计划（`EvaluationPlan`）支持多步执行：
- 多个 `CandidateArtifact`（main.py + verify_*.py）
- 挂载（hidden / visible / read-only）
- 超时、内存限制、环境变量注入

---

## 11. 反作弊机制

框架级（`eval/anti_cheat.py`）：
- **Hidden mount 完整性**：SHA-256 摘要验证 + 只读强制
- **源码扫描**：AST 解析检测禁止模式（test_、hidden、evaluator、benchmark_result）

任务级（由 evaluator 的 verify_*.py 实现）：
- 递归调用链分析（AST BFS）
- 多点交叉验证
- 运行时行为检查

---

## 12. 研究基准框架

`research/` 模块支持可复现的实验矩阵：

- `ResearchMatrix`：定义实验维度（问题 × 策略 × 种子）
- `ResearchRunner`：批量执行 + 统计汇总
- 失败闭原则（fail-closed）：基准评估出错时不给分

---

## 13. CLI 命令

```bash
omnievolve run <seed.py> -e <module:Class> -c <config.toml> [--gens N] [--trusted]
omnievolve status <db_path>       # 进化进度、Champion Policy、健康状态
omnievolve best <db_path>         # 输出最优候选代码
omnievolve export <db_path>       # 导出进化图（GraphML / JSON）
omnievolve policy <db_path>       # Champion / Challenger 策略谱系
omnievolve audit <db_path>        # Artifact 哈希、评估器版本、缺失索引
omnievolve recover <db_path>      # 扫描租约过期、未完成 Outbox、孤立 Artifact
omnievolve doctor                 # 环境检测
```

---

## 14. 技术栈

| 层 | 技术 |
|----|------|
| 语言 | Python ≥ 3.12 |
| LLM 路由 | LiteLLM（支持 OpenAI / Anthropic / 阿里云 / 智谱等） |
| 数据模型 | Pydantic v2 + pydantic-settings |
| CLI | Typer + Rich |
| 数据库 | SQLite（WAL 模式） |
| 向量 | zvec（可选）/ numpy fallback / sentence-transformers（本地嵌入） |
| 图 | NetworkX |
| 沙箱 | subprocess / Docker / Monty |
| 测试 | pytest + hypothesis + pytest-benchmark |
| 代码质量 | ruff + mypy |
| 版本管理 | commitizen（conventional commits） |

---

## 15. 设计原则（从源码提炼）

1. **评估语义不可变**：进化可以改搜索策略，但不能改"什么算好"（L2 治理禁止）
2. **Beta 后验优于频率均值**：少量样本时保守，大量样本时收敛，从不过度反应单次极端结果
3. **分层升级策略**：停滞 0-1 代 → 调参；停滞 2 代 → 换组件；停滞 ≥3 代 → 换范式
4. **Epiplexity 奖励临界复杂度**：既惩罚平凡（无信息）也惩罚随机（无结构）
5. **Fail-closed 安全默认**：反作弊、基准评估、沙箱执行出错时默认不给分
6. **CAS 去重**：相同代码只存一份，血统通过 manifest 追踪
7. **prepare/commit 分离**：LLM + 沙箱可并行，状态更新必须串行

---

## 16. 代码规模

| 模块 | 文件数 | 主要职责 |
|------|--------|---------|
| `engine/` | 14 | 进化引擎核心（Fast/Slow Loop, MCTS, Novelty, Island, Memory） |
| `agents/` | 14 | LLM 角色（Director, Coder, Critic, Router, Gateway） |
| `eval/` | 13 | 评估管线（TaskEvaluator, AntiCheat, Telemetry, Health） |
| `storage/` | 16 | 持久化（DB, CAS, Vector, Graph, Repositories） |
| `meta/` | 9 | 元进化治理（Governance, PolicyGenome, PromptEvolver） |
| `sandbox/` | 6 | 执行隔离（Subprocess, Docker, Hardened, Monty） |
| `utils/` | 11 | 工具（Embedding, Hashing, TokenCounter, Plots） |
| `research/` | 3 | 研究基准框架 |
| `plugins/` | 4 | 插件系统 |
| **总计** | **~90** | **23,730 行** |

---

*基于 `challenges/omnievolve/src/omnievolve/` 源码调研，2026-07-30*
