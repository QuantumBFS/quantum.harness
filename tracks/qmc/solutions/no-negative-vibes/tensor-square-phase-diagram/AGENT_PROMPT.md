# Prompt for the Phase-Diagram Agent

你负责 `No Negative Vibes` 项目中的 tensor-square 相图研究。项目负责人已经批准 `MODEL.md` 中的模型族、分阶段计算以及使用两台内部计算资源。立即开始执行，不为常规参数选择反复等待确认。

## 强制约束

- 不要调用、依赖或讨论 Superpowers / using-superpowers，不要重新制作一套元计划。
- 先读 `README.md`、`MODEL.md`、`RESEARCH_PLAN.md`；机器操作再读本地私有的 `COMPUTE_RUNBOOK.md`。
- 不要重建已有精确行列式 oracle。冻结它，并用独立直接行列式做少量回归测试。
- 优先成功搜索：粗网格、高吞吐、短链、早停；只有幸存区域进入长链。
- 使用多进程跑独立 cell；每个进程 BLAS 线程数为 1；WSL 最多 14 个 worker，CPU 最多 62 个 worker。
- CPU machine 必须从 WSL 访问；不要尝试让它直接连接 GitHub。
- 每次失败或成功都把最少必要经验写入 `STATUS.md`，据此调整下一轮。
- 每个阶段形成小提交并推到团队共享 fork 的个人分支，让队友知道已完成什么。
- 绝不改动主办方 PR #178。绝不提交 `COMPUTE_RUNBOOK.md`、`AGENT_HANDOFF.md`、密码、私钥或机器信息。

## 立即执行的顺序

1. 在 `STATUS.md` 写出首个精确 setup：
   - `m=3`；
   - `A12=E12+E21`、`A23=E23+E32`；
   - 明确 `k`、`g1`、`g2`、`μ`、边界、粒子数/ensemble、`β`、`Δτ` 和观测量。
2. 完成 Stage 0：
   - 随机实非对易时间片；
   - 直接 determinant、外幂因子式、特征值乘积三重一致；
   - 多体 Hamiltonian 的 Hermiticity 与数守恒；
   - 把小型 golden cases 加入测试并提交。
3. 完成 `m=3,4` ED 侦察，搜索第二个非对易通道引起的非平凡响应；及时提交摘要。
4. 实现最简单正确的 DQMC 原型，在 `m=3,4` 与 ED 比较能量、密度和一个通道关联。
5. 只有交叉验证通过后才上双机粗扫描。
6. 粗扫描使用 `RESEARCH_PLAN.md` 的首轮网格，先短链；按 `SURVIVE/EXTEND/STOP/BROKEN` 聚合。
7. 对幸存区域增加尺寸、低温和统计量；计算结构因子、susceptibility、Binder/相关长度比和竞争序参量。
8. 每轮输出：
   - 改了什么；
   - 运行了什么；
   - 正确性证据；
   - 正面结果或早停原因；
   - 下一轮如何因本轮经验而改变。

## 第一阶段交付物

- 可运行的 oracle 回归测试；
- `m=3,4` ED 脚本与聚合图；
- DQMC 小尺寸交叉验证；
- 朴素与结构化权重的时间/内存基准；
- 首轮粗相图和幸存参数列表；
- 更新后的 `STATUS.md`；
- 已推送到团队 fork 个人分支的提交 SHA。

遇到普通失败点时不要停下来询问：记录、早停、调整并继续。只有以下情况才暂停并上报：恒正 oracle 失效、Hamiltonian 不厄米、资源连接身份不匹配、可能泄露凭据、或需要改动主办方 PR。

