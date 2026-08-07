# Problem Factory 用户手册：新领域的自动化科研工作流

> 目标读者：**开新窗口的你**。按本手册走完：论文搜索 → 问题提出 → 测试 → 解决。
> 代码：`tracks/agent-kb/solutions/problem-factory/`。方法论依据：
> `docs/design/problem-generation.md`（v3：分解图 + 反向筛查 + 序贯闭环）。

## 0. 能不能完成 issue #133？——能力对照

| #133 的要求 | 状态 | 在哪验证 |
|---|---|---|
| gate 必须是可运行代码，写不出就自动拒 | ✅ | 接口 A `gate.kill_if` + 反向筛查（`docs/design/problem-generation.md` §2） |
| 校准门：不看原题重新推出 #124–#128 同质量级 | ✅ | `python3 run_calibration.py` → CALIBRATED（dev 5/5，held-out #112） |
| 每次拒绝（自动或人工）都留档 | ✅ | 三态 verdict + 结构化死因 + `results/report.md` mishap review |
| 求解 gate 生成时冻结、事后不改 | ✅ | `gate.frozen: true`，进了管线不许改 |
| heuristics 库累积，增长曲线是交付物 | ✅ | `heuristics/` + `results/metrics.png` |
| 库真的改变下一轮（不只变长） | ✅ | `python3 run_learning_loop.py`：预算浪费 29% → 0%，零死亡 |
| 文献挖矿（SOTA 表 / 认证界缺口 / 争议结果） | ⚠️ 半自动 | `/arxiv-search` skill + 人定边界；`mine.py` 未实现——§2 里你就是挖矿器 |
| 新颖性检查 + 来源可追溯 | ⚠️ 半自动 | 厂内指纹去重 ✅；对外查重靠在卡上注明 provenance |
| 生成过程可复现（prompt/transcript/拒绝日志公开） | ✅ | `log.md` + `docs/discussion/` |
| Tier 1：5 题被人审接受 | 🔄 进行中 | demo 卡 5 张 + #112 全流程样板（`briefs/sawtooth-erosion-001.md`） |
| Tier 2/3（全过 gate / 过同行评审） | ⬜ 赛后 | — |

**结论**：判决层与学习闭环已完整；生成侧的文献挖矿是"agent + skill 半自动"。
新窗口里，你（agent）就是生成器，按 §2–§5 走即可。

## 1. Bootstrap（新窗口整段粘贴）

```
背景：合肥黑客松 issue #133 problem factory。先读
tracks/agent-kb/solutions/problem-factory/ 的 README.md、INTERFACE.md、
docs/user-manual.md。管线入口：run_demo.py / run_calibration.py /
run_learning_loop.py。代码风格：极简、零 try/except、schema 是约定错了就崩。
今天任务：在【填你的领域，如：阻挫磁体 / 张量网络算法】方向上，
按手册 §2–§5 完成一个新问题的 搜索→提出→测试→解决。
```

## 2. 论文搜索（挖矿，30–60 min）

目标不是"找题"，是**建分解图、定位边界**：

1. 用 `/arxiv-search` 找该方向近年综述与高引工作，提取三类锚点：
   - **SOTA 表**（被打榜的数字）→ record 型候选；
   - **认证界缺口**（上下界之间有缝）→ bound 型候选；
   - **争议结果**（两篇互相打架）→ adjudicate 型候选。
2. 每个候选必须钉死一个**文献中已发表的数字**；钉不出来 = `no_literature_anchor`，当场弃。
3. 边界探测 = 站在已知边上往外走一步：只改一个参数轴 / 一个观测量 / 一个尺寸。
   更宽的记 `too_broad`，回分解图继续拆（"基本进展单元" = 3–5 个可代码化子方案可解）。

## 3. 问题提出（结晶，写卡）

把候选写成接口 A 的卡（schema 见 `INTERFACE.md`，实例见 `cards/round2/*.yaml`）。
过堂清单——任一不过就弃，死因记档：

- [ ] **可证伪**：什么样的实验结果能判它错？
- [ ] **可量化观测**：观测量 + 成功/失败条件写成了数字吗？
- [ ] **gate 可代码化**：`kill_if` 是 runnable 的吗？写不出 = 自动拒（这是 #133 明文规则）
- [ ] **粒度**：3–5 个可代码化子方案能解吗？
- [ ] **指纹不撞**已有卡（`pf/cards.py` 的 fingerprint 规则）

写卡后先确认尺子没漂：`python3 run_calibration.py`（应仍 CALIBRATED）。

## 4. 测试（发射，分钟级）

`python3 run_demo.py` 是全管线样板（去重 → static fire → hop → 三态 verdict）。
新卡放一炉飞，看结局：

- `setup_error`（static fire 死）→ 约定/守恒律错了，回去修卡；
- `no_signal`（hop 死）→ 信号低于有限尺寸噪声层；教训入库：加大扰动或尺寸；
- `deferred` → 可见但不决定性 → **按遥测建议放大重发**（样板：`pf/round2.py` 的 relaunch-103）；
- `survivor` → 进 §5。

每个 verdict 自动沉淀 `heuristics/` 条目。跑两轮后
`python3 run_learning_loop.py` 对比预算浪费率——应该下降。

## 5. 解决（survivor 之后，照 #112 样板）

1. **TDD**：先写锚点测试（已知极限/精确解/对称性），`tests/test_*.py`，看它们先失败；
2. 求解脚本 `run_*.py` → 图 + 原始数据 json 入 `briefs/`；
3. 有第二实现就做交叉验证（样板：`scripts/xdiag_crosscheck.jl`），锚点升级为 Harness anchor；
4. 写 brief：物理图像、方法、结果、结论、**诚实的新颖性评估**；
5. **反哺 harness**：`.knowledge/` 没有对应模型卡/oracle 卡就补——"无卡先建卡"
   是根 AGENTS.md 规则，也是 agent-kb 赛道的核心交付；
6. `python3 build_run.py` + `/challenge-report` 出报告。

## 6. 死因速查

| 死因 | 检出层 | 怎么办 |
|---|---|---|
| `no_literature_anchor` | 结晶 | 回 §2 继续挖矿 |
| `not_falsifiable` / `no_quantifiable_observable` | 反向筛查 | 弃，或继续操作化 |
| `too_broad` | 结晶 | 回分解图继续拆 |
| `duplicate_fingerprint` | 去重 | 弃 |
| `setup_error` | static fire | 查约定（spin/pauli）、守恒律 |
| `no_signal` | hop | 扰动加大，或尺寸加大 |
| `deferred` | 判决 | 不是死——放大重发 |

## 7. 人的位置（gatekeeping 声明）

issue #133 要求人在生成中的角色限于**已声明的 gatekeeping**。你只做三件事：
① 给大方向；② 反向筛查争议的最终裁定；③ Tier 1 的人审。
**不要在管线运行后改 gate**——那是作弊，遥测和日志会让它无所遁形。
