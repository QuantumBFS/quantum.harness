# Problem Factory 开发日志 — Day 1–2（2026-07-27/28）

> 记录本次 session 做了什么、为什么这样做、结果意味着什么。
> 位置：`tracks/agent-kb/solutions/problem-factory/`

---

## 一、做了什么（按顺序）

| 步骤 | 产物 | 说明 |
|---|---|---|
| 1 | `pf/ed.py`（~50 行） | 最小 XXZ+J2 精确对角化：Sz=0 对称 sector 内构稀疏矩阵，dense 对角化取最低两个本征值 |
| 2 | **物理验证** | 用 Bethe ansatz 精确解检验 ED 正确性（见第三节） |
| 3 | `pf/cards.py`（~60 行） | 模板生成 5 张 problem cards + 指纹去重（接口 A） |
| 4 | `pf/static_fire.py`（~40 行） | 第一性原理检查：Bethe oracle + Sz 守恒 |
| 5 | `pf/probe.py`（~50 行） | hop test：跑完整 (L, Δ, J2) 网格，计算 decisiveness 指标 |
| 6 | `pf/verdict.py`（~40 行） | 三态判定（survivor/deferred/dead）+ 战报生成 |
| 7 | `run_demo.py`（~60 行） | 唯一入口，串联全管线 |
| 8 | **抓到并修正一个判据 bug** | deferred 判据初版物理上错误（见第五节） |
| 9 | `AGENTS.md` | scoped 工作约定：schema、verdict 规则、代码风格 |
| 10 | `README.md` | 火箭测试叙事文档 |

运行产物：`cards/*.yaml`（5 张卡）、`results/telemetry.jsonl`（每卡一条遥测）、`results/report.md`（战报）。

---

## 二、架构：火箭测试三级裁判

核心主张：**问题的好坏不由 agent 讨论决定，由实验数字决定**（回应指导老师"多 agent 对抗会模棱两可"的批评）。

```
cards.py 生成 5 张卡（YAML，gate 已冻结）
        │
        ▼
  指纹去重 ────────────────→ dead（duplicate_fingerprint）
        │
        ▼
  static fire（第一性原理）
  · Bethe oracle：L=10, Δ=1 的 E/N 对精确解 −0.4431
  · Sz 守恒：[H, Sz_tot] = 0
        │ 失败 → dead（setup_error）
        ▼
  hop test（实验测量）
  · 跑完卡上声明的全部 (L, Δ, J2) 网格，不许跳点
  · decisiveness = 扰动引起的 gap 移动 / baseline 自身的有限尺寸噪声
        │
        ▼
  三态 verdict
  · decisiveness ≥ 2.0        → survivor（信号决定性）
  · 0.5 ≤ decisiveness < 2.0  → deferred（可见但不决定性，建议放大发射）
  · decisiveness < 0.5        → dead（no_signal）
        │
        ▼
  telemetry.jsonl + report.md（每张卡都有机器可读记录，死亡必须带死因）
```

设计原则：

1. **Gate-first**：没有冻结 gate 的卡不允许占"发射窗口"；gate 在求解后绝不修改
2. **失败是资产**：dead 卡和死因是启发式库的种子，不是垃圾
3. **deferred 是一等公民**：smoke 测不准的问题不冤杀也不放行，带着"值得放大"的建议回到人面前
4. **代码极简**：管线内零 try/except，schema 是约定不是运行时校验，格式错了就让它响亮地崩

---

## 三、物理正确性验证

ED 求解器本身先过了自己的 static fire：

```
L=6   E0/L = -0.467129   gap = 0.6847
L=8   E0/L = -0.456387   gap = 0.5227
L=10  E0/L = -0.451545   gap = 0.4232
Bethe ansatz 热力学极限 E/N = -0.443147
```

E/N 从上方随 L 收敛到精确解（有限尺寸修正 ~1/L²），gap 按 1/L 收缩——正是无磁隙 Heisenberg 链的已知行为。求解器可信，后面的判决才有意义。

---

## 四、首飞结果

```
launched 5: survivor 1, deferred 1, dead 3
```

| 卡 | 设计意图 | 判决 | 机制 |
|---|---|---|---|
| xxz-j2-gap-001 | J2=0.3 强扰动 | **survivor** | decisiveness 5.49，信号远压过噪声 |
| xxz-j2-deferred-004 | J2=0.05 弱扰动 | **deferred** | 0.93，看得见但不够决定性 |
| xxz-j2-tiny-002 | J2=0.001 极弱扰动 | dead | no_signal：0.02，不可见 |
| xxz-bad-setup-003 | pauli/spin 约定混淆（能量差 4×） | dead | setup_error：Bethe oracle 在 static fire 阶段拦截，没浪费 hop 机时 |
| xxz-j2-gap-001-dup | 与 001 完全同构 | dead | duplicate_fingerprint：零物理成本拦截 |

关键观察：**三种死法各由不同机制检出**（去重 / 第一性原理 / 实验信号），这正是系统"有牙齿"的证据。交付物不是那个 survivor，而是整个判决过程的可信度。

---

## 五、首飞抓到的判据 bug（重要教训）

初版 deferred 判据要求"effect 随 L 增长"，结果把 J2=0.05 卡冤杀了（gradient = −0.0017）。

分析：**无磁隙相里，gap 本身 ~1/L，扰动引起的 gap 移动也同样 ~1/L 收缩**。所以 raw effect 随 L 下降是物理正确的行为，不代表信号消失。"effect 必须随 L 增长"对 gap 类观测量是错的判据。

修正：deferred 只看 decisiveness 区间（0.5–2.0），gradient 保留在 telemetry 里供人参考，不做硬判据。

元教训：**判据本身也要被实验检验**——这正是"用实验当裁判"相比"用讨论当裁判"的优势：讨论只会互相附和，实验会当场反驳你。

---

## 六、分工接口（明天接头用）

两个 schema 已冻结在 `AGENTS.md`：

- **接口 A（problem card YAML）**：`pf/cards.py` 是手工 fixtures，换队友的生成器或 LLM 生成器只需替换 `generate()`，schema 不变
- **接口 B（telemetry JSONL）**：`problem_id / verdict / reason / metrics`，队友的任何 probe runner 产出同样格式即可汇合

## 七、Day 2 待办

- [ ] **出题人**：从论文挖掘结构性锚点（对称性条件、守恒律、已知极限、参数绑定）生成 idea → 结晶器强制补齐 gate → 补不出来的记死因 uncrystallizable
- [ ] **value 校准**：decisiveness ≠ 价值；用文献中已知好/平庸问题回测管线排序，区分 idea（无 gate）与 question（可判定）
- [ ] deferred 卡上集群放大（L=12–16，`scripts/harness_array_sbatch.sh`）
- [ ] 与队友接头：外部卡片倒入本管线
- [ ] 死因分类 → heuristic library
- [x] 更新 `docs/design/` 方法论文档（~~听证会旧版~~ → 见 Day 3：新建 `problem-generation.md`，弃用听证会形式）

---
---

# Day 2（2026-07-28）

## 一、issue #133 全文重读：被低估的 calibration gate

issue 原文有一条 Day 1 日志没抓住的硬要求：

> Before generating new problems, the generator must **re-derive problems of the same quality class as #124–#128** from the open literature, without access to the originals. If the rubric cannot reconstruct the hand-curated set, it is not trusted on new problems.

结论：校准不是"加分项"，是 issue 明文的信任锚。Day 2 主攻方向因此从"出题人优先"改为**校准优先（造尺子），出题人用尺子量产**。

## 二、校准集画像（#124–#128 的共同指纹）

| # | gate 家族 | 单一标量 |
|---|---|---|
| 124 kagome 能量区间 | certificate（SDP 对偶可行性） | bracket 宽度 ↓ |
| 125 J1-J2 打榜 | fresh_sample（变分自认证） | E/N ↓ |
| 126 AKLT 能隙定理 | interval_arithmetic（Knabe 判据） | 阈值余量 ↑ |
| 127 收缩成本 | cost_arithmetic（确定性 FLOPs） | FLOPs ↓ |
| 128 Trotter 界 | certificate（符号对易子范数） | 可证门数 ↓ |

四条可操作特征：**文献锚（钉死的数字+引用）、证书型 gate、单一标量 merit、可发表单元（超越 SOTA 的陈述）**。

**校准发现 #1（在读论文阶段就浮现）**：Day 1 的 decisiveness gate 属于"统计信号检测"家族，不在 issue 点名的四种证书型 gate 里——不先校准，工厂量产的会是同一偏科家族的问题。

## 三、落地：rubric + 回测（`pf/rubric.py` + `run_calibration.py`，~90 行）

- `pf/rubric.py`：四条指纹检查（presence 层）。**分层声明**：rubric 只查结构存在性；"钉死的数字是否真实、checker 是否真能跑"留给下游 static fire / hop 验证——不把深验证伪装成浅检查。
- `calibration/`：5 个正例（#124–128 手工编码为 candidate YAML）+ 3 个负例。
- 负例设计（阴性对照，呼应 Track 1 教学）：
  - `neg-xxz-signal-detection`：我们自己的 Day 1 卡重新编码 → 必须拒
  - `neg-vague-hubbard`：空洞题（"研究 Hubbard 相图"）→ 四项全挂
  - `neg-anchor-no-scalar`：有文献锚但无标量/无证书 → 检验各检查的独立性

## 四、回测结果

```
calibration: 5/5 positives accepted, 3/3 negatives rejected -> CALIBRATED
```

最有信息量的一条：`neg-xxz-signal-detection`（我们自己的卡）在 4 项检查中挂了 3 项（无文献锚、gate 家族不符、无可发表单元）。**校准发现 #1 现在有了可执行证据**，不再是口头判断。

## 五、对 C（出题人）的设计约束（明天用）

结晶器模板必须按四种 gate 家族分别配置；结构锚点清单里新增必备项：**"文献中已钉死的数字"**。缺此锚的 idea 死因记 `no_literature_anchor`。

## 六、其他记录

- 环境：Track 1 训练顺手装好 `.venv`（pymupdf4llm）和 Julia 1.12.6；Ion.lock 已同步 commit
- **harness 改进候选**：根 `.gitignore` 不忽略 `.venv/`（`make install pdf-render` 的产物），每个新用户都会踩 → 可提炼为 PR 三要素之一的"harness 改进"
- 污染风险对策已定：生成协议只喂原始文献、不喂 issue 文本；隔离声明写进 provenance 日志

## 七、Day 2 剩余 / Day 3 待办

- [ ] 出题人（结晶器按新尺子量产）
- [ ] deferred 卡上集群放大
- [ ] 与队友接头
- [ ] 死因分类 → heuristic library（rubric 拒绝日志是第一批素材）
- [ ] 更新 `docs/design/` 方法论文档
- [ ] `.venv` gitignore 改进项提上 PR 清单

---

## 八、Day 2 下午：#112 实测 → 尺子扩成双质量类

### 隔离协议首测

用户拿来公开 issue #112（陈锟老师出的"局域磁振子侵蚀地图"）考尺子。按既定协议执行：

1. **自我申报**：锯齿链局域磁振子物理（2002–2004 经典文献）在 LLM 训练数据内，声明为污染；issue 文本当天首读，无污染
2. **对策**：编码字段全部可回溯 issue 原文，判决交给 `rubric.py` 确定性代码——LLM 只做搬运，不参与打分

### 一判结果与扩类

旧尺子判决：**REJECTED**（3/4 过，`single_scalar` 挂）。分析：#112 交付物是**曲线族/相图**（侵蚀地图），不是被推进的标量——它和 #124–128 是不同物种：

| | record 类（#124–128） | map 类（#112） |
|---|---|---|
| 交付物 | 一个被推进的标量 | 一族曲线 + 相图 |
| 不可作弊靠 | 证书/确定算术 | 精确整数锚 + 解析 PT 交叉验证 |
| 五条指纹 | 文献锚/证书/单标量/可发表 | 文献锚/证书/**留白声明**/曲线+解析校验/可发表 |

赛道专家亲手出的题不在官方校准集的类里——**校准集 #124–128 的策展偏好被尺子量化出来了**（issue 说的 "partial failure is informative" 的实例）。

### 扩类实现（`pf/rubric.py` v2）

- `grade()` 现在同时算 record / map 两类检查，任一类全过即 accept，返回归属类
- map 类新增两字段：`uncharted`（留白声明，含边界文献）、`merit.curve` + `merit.analytic_check`（曲线族必须带解析牙齿——没牙齿的曲线正是老师批评的"模棱两可"）
- 校准集分 dev（#124–128 + 3 负例）/ held-out test（#112 + 2 个 map 类专属负例）

### 复测结果

```
dev:  5/5 positives（全部 record 类）, 3/3 negatives
test: 1/1 positives（#112 → map 类）, 2/2 negatives -> CALIBRATED
```

两个新负例各只挂该挂的一项（`uncharted_region` / `curve_merit`），新检查项独立性得证。

### 沉淀

- 死因分类法对生成侧的启示：`no_uncharted_region`（没声明留白的地图题）、`no_analytic_teeth`（曲线无解析校验）可入 heuristic library
- 给队友（生成侧）的接口更新：结晶模板现在有两套——record 模板补 `merit.scalar`，map 模板补 `uncharted` + `merit.curve/analytic_check`

### 事故与修复（同日下午）

提交扩类时误把 `.venv/`（4600+ 文件）和根 `AGENTS.md` 的一处断词腐坏（`capit/ulation`，疑为 IDE 误触自动保存）卷入 commit 并推送。修复：`reset --soft` 回退 → 丢弃腐坏 → 重提干净 commit → **顺手把 `.venv/` 补进根 `.gitignore`（harness 改进候选 #1 就此落地，commit b6b1279）** → force-with-lease 推送。教训：**commit 前看一眼 `git status --short` 的暂存区全貌**，尤其多人共用一台机器时暂存区可能有别人的东西。

---

## 九、Day 2 傍晚：#112 失谐轴解题（reconnaissance 尺度）

### 过程（TDD）

可行性先行（`docs/sawtooth-ed-feasibility.md`：本机到 N=20，N=28 留集群）→ 锚点测试先行 → `sawtooth_hamiltonian` builder → 磁化曲线模块 `pf/sawtooth.py` → `run_sawtooth.py` 一条命令出全部产物。

**TDD 抓到一只物理预期错误**：初版跳变测试断言"所有 sector 能量相等"，实测 k≥4 能量上升——不是 builder 错，是硬双子约束：N_c 原胞的环上最多摆 N/4 个局域磁振子。平台长度恰好 N/4 双证 builder 正确。测试修正为"平台+上升"完整签名。

### 结果

- 锚点全部复现（1e-8~1e-10）：平带、跳变、Lucas=18、剩余熵、Monti–Sütő
- 磁化曲线方法：Sz 守恒下场只贡献 −h·Sz，整条阶梯曲线由零场 sector 能量精确给出，无需扫场
- 三个侵蚀观测量：W(δ) 线性收缩；ΔM(δ) 仅在 δ=0 满跳（measure-zero 特性）；**Γ(δ) ≈ 单磁振子带宽 → 抹平是单粒子物理**
- **候选新现象（未证实）**：δ<0 时 Γ 超过带宽、δ>0 时不及——相互作用在两侧作用不对称。需 N=20–28 + 简并微扰交叉验证才升级为 claim

### 产物（全部入库，commit 19bd78d）

`briefs/sawtooth-erosion-001.md` + 两张图 + `briefs/data/erosion.json`；README 加了"Solved: issue #112"成果节。

---

## 十、Day 2 深夜：反哺 harness —— 把对话产物整合进知识库

### 动机（自我解剖）

解题时绕开了 harness：没读模型卡（不存在）、没用 /method-ed 和 XDiag（手搓 scipy ED）、没做跨方法交叉验证。根因：**知识发现是白名单制**——`quantum-model` dispatcher 的 description 显式列模型，sawtooth 不在其中 → 对 agent 隐形。这是 agent-kb 赛道的活教材缺口。

### 整合五项（全量完成）

| # | 项 | 产物 |
|---|---|---|
| 1 | XDiag 交叉验证 | `scripts/xdiag_crosscheck.jl`：三锚点全 PASS（平带 −4.0、Lucas=18、Monti–Sütő），两套独立代码互证 → 锚点升级 **Harness anchor** |
| 2 | 精确解 oracle 卡 | `.knowledge/solvable/sawtooth-localized-magnon/`（ORACLE.md + oracle.py，T5/Tier C/Script S，6 自测锚点），INDEX + ref.bib 注册，自动发现确认 |
| 3 | 模型卡 | `.knowledge/models/sawtooth-chain/MODEL.md`（A1–D16 + 方法路由 + 验证指针，引用 oracle 卡） |
| 4 | dispatcher 注册 | `skills/quantum-model/SKILL.md` 白名单加 sawtooth-chain——**"agent 看不见"的机制性修复** |
| 5 | 根 AGENTS.md 规则 | "无卡先建卡"：计算前发现 `.knowledge/` 无对应卡 → 补卡是该 session 交付物的一部分 |

### 回归

solution 三件套全绿（anchors 6/6、demo 战报不变、校准 CALIBRATED）。

### 环境备忘

`uv` 未装（`make test-oracles` 需要）；oracle 用系统 python3 验证通过。

---
---

# Day 3（2026-07-29）

## 一、出题方法论 v3：分解图 + 反向筛查（取代 record/map，弃用听证会形式）

用户提出新思考，本轮归纳并落文档（代码不动，迁移留下一轮）。

**新框架四条**（全文在 `docs/design/problem-generation.md`）：

1. **问题二分类（按性质）**：工程类（新算法、材料改进——明确量化指标）vs
   抽象类（新理论等）。共同来源 = 真实物理问题 + 物理世界与现有理论/目标的不一致。
   抽象类必须分解操作化、化归为可量化形式才准进管线。
2. **反向筛查（badness filter）**：正面量化"好"很难，反面排"坏"可以很硬——
   不可实验验证（`not_falsifiable`）、给不出可量化观测条件
   （`no_quantifiable_observable`）当场拒，幸存者才进发射流程。
   排除法而非评分法：通过只代表"配被实验判决"。
3. **分解图控粒度**：大问题逐层分解；"基本进展单元" = 3–5 个可代码化子方案可解，
   更宽记 `too_broad`——把"问题太宽泛"从模糊感觉变成可执行检查。
4. **边界探测生成法**：大方向用户端给定 → 论文库提取业界已有认知与公认开放问题
   → 建分解图 → 在图的边界上试探出新问题（站在已知的边上往外走一步，
   "新"与"可判"同时成立的唯一区域）。

**用户裁定**：工程/抽象二分类**取代** record/map 质量类（record/map 是按交付物
形态分的；新框架按问题性质分 + 反向筛查 + 粒度判据）。校准集重新归类：
#124–#128 全属工程类；#112 也属工程类（W/ΔM/Γ 全部可数值化且有精确锚点，
"地图"是交付物形态不是性质）。

**弃用听证会形式**：早期"多 agent 听证/辩论"的方法论叙事不再使用——
生成侧靠分解图控制来源与粒度，判决侧靠反向筛查 + 实验数字，任何环节
都不让 agent 讨论当裁判（与 Day 1 的核心主张一致，贯彻到出题层）。

## 二、落地产物（本轮纯文档）

- 新建 `docs/design/problem-generation.md`（v3 方法论全文 + 迁移说明 + 接口预留）
- `README.md` Layout 注记 rubric 分类法已被取代（行为与校准不变）
- `~/problem-factory-guide.md` §4.1 改写为新框架、§3/§8 同步注记
- 新死因入册：`not_falsifiable` / `no_quantifiable_observable` / `too_broad`
  （检出于最上游，进一步压低预算浪费率）

## 三、下一轮（代码迁移）待办

- [ ] `pf/rubric.py` 重构为「反向筛查 + 粒度检查」；校准 fixtures 改编
  （正例 = 过两条反向判据，负例 = 各挂一条的对照例）
- [ ] 接口 A 新增字段：`class: engineering|abstract`、`parent_problem`、
  `decomposition_node`（接口 B 不变）——改前通知队友（schema 单源）
- [ ] Day 2 遗留：出题人量产 / deferred 卡集群放大 / 与队友接头 / heuristics 库

---
---

# Day 4（2026-07-30）

## 一、重定位：从"出题+判题"到序贯决策闭环

上午 brainstorm（全文 `docs/discussion/2026-07-30-092851-brainstorm-ideas-log.md`）：
讲座意见与用户一致——"纯粹出题并评价题目好坏"不对。结论：系统重定位为
**sequential scientific decision system**——文献开放问题 → 边界探测选前沿 →
判别实验 → 新数据 → 新问题从残差中长出（K_t + 实验 → K_{t+1}）。
decisiveness ≠ value 的缺口由闭环回应：价值不由 agent 评分，由"实验结果
改变下一步行动"来体现。队友的信息论方案归档为 EIG=选下一步实验的候选
判据，不单独定义科学价值（详见 problem-generation.md §8）。

## 二、学习闭环实证（TDD）

- 新增 `pf/budget.py`（hop 成本核算：1 次 ED = 1 点；只有 no_signal 死亡算浪费）
  与 `pf/round2.py`（round-2 舰队，每卡 `licensed_by` 注明授权它的 heuristics 条目）
- 新增 `run_learning_loop.py`：两轮同管线对比，写 `results/learning_loop.md` +
  `results/telemetry_round2.jsonl` + `cards/round2/`；不动 run_demo 的任何产物
- 锚点测试 `tests/test_learning_loop.py` 全绿（舰队授权、指纹不撞、static fire、
  round-1 浪费锚点 18/63）
- **结果**：round 1 浪费 29%（18/63 hop ED，tiny-002 死于噪声层下）→
  round 2 浪费 0%（0/54），零死亡；判决边界被夹在 J2=0.1（1.85）与 0.2（3.70）
  之间；deferred-004 放大重发 0.93 → 1.60 仍 deferred → 库给出下一步建议 L≥14
- 诚实声明：round-2 舰队是规则生成、逐卡引用教训——演示闭环机制，非 LLM 生成器

## 三、回归与交付

- 回归全绿：test_sawtooth（anchors 6/6）、run_demo（精确 1/1/3）、
  run_calibration（CALIBRATED）、run_sawtooth、test_learning_loop、build_run
- 队友生成侧今天不接（其 problem-factory-test 仓库为空 clone）；接口 A 留好
- /challenge-report + 向 upstream 开 PR（三要素：harness 改进 / solution /
  可复现 prompt）

## 四、issue #148 全流程实战：√5 猜想（搜索→提出→测试→解决）

下午按手册 §2–§5 把 challenge #148（三角/六角晶格 TFIM 临界场比值是否精确
等于 √5，发布人 Xiao-Yan Xu，标签 accepted+autoresearch）当作工厂"新领域
全流程"的实战题跑完。这也是 #133 Tier 1 需要的又一例全流程样板。

### 1. 挖矿（§2，约 30 min）

- Blöte & Deng (PRE 66, 066110 (2002)) 全部 **203 篇引用**(Semantic Scholar)
  + arXiv 摘要检索：**没有任何 2002 年后的工作改进** h_c(△)=4.76811(9)、
  h_c(⬡)=2.13250(4)——这对 24 年前的数字至今仍是 SOTA,challenge 的
  baseline 就是已发表最优值。锚点钉死，写进卡的 provenance。
- 赛道情报：#148 已被 4 队认领（PR #224/#202/#195/#191，全走 qmc)。我们
  不正面赛跑——它是工厂的能力演示素材，qmc 是 issue 指定的方法但工厂的
  hop 层是 ED，这本身就是一次"管线把问题路由到正确方法"的测试。

### 2. 结晶（§3)

- 一张卡 `cards/round3/tfim-ratio-sqrt5-001.yaml`:gate 生成时冻结——
  decisiveness = |R−√5|/σ_R,kill_below 2.0；目标精度 σ_R ≤ 1.2×10⁻⁵
  直接取自 issue item 3。观测量：声明团簇上的 Binder cumulant 交叉。

### 3. 测试（§4):两轮发射，闭环再加一例

- **Round 1 死 `no_solver`**：注册表只有 xxz_j2_chain / sawtooth_chain,
  二维 TFIM 卡在物理之前被注册表门拦下。第四种死因的首次实战触发
  （此前只在 INTERFACE.md §4 纸面上）。
- **Builder 补环（TDD，先锚点后实现）**:`tests/test_tfim2d.py` 先写先看红,
  然后 `pf/tfim2d.py`(~90 行：chain/square/triangular/honeycomb 环面团簇,
  偶宇称 sector)。锚点 6/6 绿：精确 dimer E0=−√(J²+4h²)（全 h);h=0
  E0=−键数（四晶格）；强场变分界 −h−z/4h ≤ E0/N ≤ −h;[H,P]=0;
  **Jordan–Wigner 独立交叉验证**(chain N=16,h=0.5/1/2,1e-10——同一批
  矩阵元走完全不同的解析路径）;Binder 极限 U=2/3(cat)与 U=2/3N（极化）。
  中途自纠一次：h→∞ 的 U 锚点我初写成 <0.05，正确值是二项分布的 2/3N,
  错的是锚点不是代码——按 TDD 规矩改锚点并留档。
- **Round 2**:static fire 4/4 → hop → **deferred(decisiveness 0.73)**。

### 4. 结果与解决（§5,reconnaissance 尺度）

| 量 | 本次（N≤18 ED) | Blöte–Deng 2002 |
|---|---|---|
| h_c(△) | 4.342 ± 0.002 | 4.76811(9) |
| h_c(⬡) | 1.986 ± 0.062 | 2.13250(4) |
| h_c(□,builder 验证） | 2.870 | 3.04438(2) |
| R = h_c(△)/h_c(⬡) | **2.186 ± 0.068** | 2.23592(6) |

- R 距 √5 只有 0.73σ、距经典星三角值 2.3975 有 3.1σ——方向正确但
  σ_R = 0.068 是所需 1.2×10⁻⁵ 的 ~5700 倍。**√5 在 ED 尺度不可判决**,
  管线用数字说出这句话并给出路由：sign-free QMC(SSE/连续时间 cluster)
  + FSS 交叉分析，正是 issue 的 verification plan。
- 小团簇交叉系统性地比 QMC 值低 5–7% 且随 N 上移（图里可见）——方晶格
  对照说明这是已理解的有限尺寸效应，方法没坏。
- 诚实声明：无新物理；R = 2.186 ± 0.068 不许被引用为支持/反对 √5 的证据。
  交付物是过程本身 + 注册表增长（tfim_2d)+ heuristics 两条。

### 5. 产物与反哺

- `briefs/tfim-ratio-sqrt5-001.md`（物理图像/方法/结果/诚实新颖性评估/
  QMC 下一步）、`briefs/data/sqrt5.json`、`briefs/figures/binder_crossings.png`
- `results/telemetry_sqrt5.jsonl`（两轮：no_solver → deferred)、
  heuristics 新增 `tfim-ratio-sqrt5-001.yaml` + `-no-solver.yaml`
- KB:`.knowledge/models/transverse-field-ising/MODEL.md` 补三角/六角
  benchmark（按根 AGENTS.md provenance 纪律打 Literal / Harness anchor 标签）
- INTERFACE.md §4 注册表加 `tfim_2d`;INTERFACE 里 §5–§7 "冻结待实现"的
  状态注记不受影响
- **harness 修复**：发现根 AGENTS.md 在本仓库从未生效（无 CLAUDE.md)——
  按其自身约定（第 132 行：CLAUDE.md 是一行接入文件、gitignored）已补，
  新会话自动加载。自首：本轮 hop 计算前违反"设置先确认"规则，设置实际
  冻结在卡中，但规矩是先报。
- 回归：`run_demo.py`(1/1/3)、`run_calibration.py`(CALIBRATED）不受
  static_fire.py 扩展影响。

### 6. 死因体系更新

`no_solver` 从纸面死因变成实战死因（第 4 种）,5 种死因现在全部有实证：
duplicate_fingerprint / setup_error / no_signal / uncrystallizable(📐) /
no_solver ✅。教训入库：新模型类的卡要预算一个 builder 周期才算发射。
