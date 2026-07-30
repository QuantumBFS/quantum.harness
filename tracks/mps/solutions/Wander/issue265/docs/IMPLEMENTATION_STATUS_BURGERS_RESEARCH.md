# Burgers 普适性研究：实施状态与下一门槛

更新日期：2026-07-30。

## 当前结论

本地可完成的研究设计、推导、数值分析和判决基础设施已经完成。当前机器
状态为

```text
overall: simulation_unresolved
next_gate: complete_convergence_datasets
pre_unblinding: true
```

`simulation_unresolved` 只表示确认性张量网络数据尚未完成，不能解释成
“Burgers 已被证伪”。12 个正式收敛任务已于 2026-07-29 提交到 SCNet
xh5 并全部开始运行。现有公开单轨迹的独立 Phase 0 结论仍是：

```text
universal_scalar: unresolved
finite_window_surrogate: supported
microscopic_moment_law: not_rejected
two_mode: not_tested
overall: insufficient_observables
```

## 十项计划的实施审计

| 任务 | 本地状态 | 主要产物/门槛 |
|---:|---|---|
| 1. 冻结假设、矩阵和阈值 | 完成 | `configs/` 与预注册协议 |
| 2. 矩量桥 | 完成 | \(W^{3/2}\)、隐式宽度律、2000 次时间块 bootstrap |
| 3. 数据格式和任务清单 | 完成 | 74 项清单；31 个阶段 B 保持盲态 |
| 4. 数值收敛门 | 后端与审计完成、12 个正式任务运行中 | 高温 purification TEBD、common-grid/crop、剖面/宽度/守恒/边界审计；\(J_2\) 分组后端本地门已通过、集群门待复核 |
| 5. 跨初态标量检验 | 代码完成、数据待算 | shared、condition-specific、\(2\sigma g\mu\)、LOCO、对称性、bootstrap |
| 6. 微观推导账本 | 完成 | exact/asymptotic/closure/empirical 分级和 Mori–Zwanzig 目标 |
| 7. 两模 NLFH | 分层判别器完成、量子对照待算 | 四级嵌套模型、复 FCS、脉冲响应、共同随机数、分块损失、成对误差 CI |
| 8. 冻结判决引擎 | 完成 | 缺数据只返回 unresolved，不作物理选择 |
| 9. 当前数据 pilot | 完成 | \(A_W=0.741842\)、\(A_B/A_W=0.999154\) |
| 10. 生产与开盲 | 12 个收敛任务运行中、production A 待门控 | Slurm 作业 23009466–23009477；一次性开盲脚本；当前无开盲记录 |

## 已通过的验证

- TeNPy 小链双向畴壁 smoke 数据已实际生成；
- 磁化、局域磁流、连通 \(C^{zz}\) 的 spin-flip 缺陷低于
  \(2\times10^{-15}\)，总磁化漂移约 \(10^{-14}\)；
- 格点连续性方程相对残差 \(4.17\times10^{-4}\)；
- 真正两次测量 transfer-FCS 的 Hermiticity、spin-flip、零计数场和
  一阶累积量—电荷转移一致性全部通过；
- \(L=6\) 完整密度矩阵精确演化交叉验证通过，四类观测量最大误差为
  \(10^{-9}\) 或更低；
- HDF5 checkpoint/resume 经实际中断验证，恢复结果与不中断运行逐位一致；
- \(J_1\)-\(J_2\) 分组 purification-TEBD 后端已经实现：每个 MPS 格点承载
  两个相邻物理自旋，完整物理割线电流同时计入最近邻项和所有跨割线
  次近邻项；
- \(J_2=0.1\) 的上下两个畴壁均已通过 \(L=6\) 精确演化交叉验证，磁化、
  完整电流、连通 \(C^{zz}\) 和 FCS 的最大误差均低于
  \(8.3\times10^{-10}\)；
- \(J_2=0\) 时分组与未分组后端的磁化、电流、\(C^{zz}\) 和 FCS 等价，
  最大差异 \(1.0\times10^{-8}<2\times10^{-7}\)；
- \(J_2\) 分组后端的真实中断—恢复测试通过，恢复轨迹与不中断孪生任务
  的五类输出逐位一致；
- `src/`、`scripts/`、`tests/` 严格编译通过；
- 正式矩量 bootstrap 恢复为 2000 个有效重复；
- 当前数据审计：43 个非盲态任务缺失，31 个阶段 B 未打开；
- 四个收敛代表条件均明确标成 `simulation_missing`；
- 开盲记录不存在，守卫在无显式确认或收敛未通过时拒绝执行。
- SCNet 小链预检作业 `23009272` 完成；
- 注册 coarse/FCS 资源标定作业 `23009308` 完成到 \(t=2\)，峰值内存
  334708 KiB、最大键维 136、磁化漂移 \(7.55\times10^{-15}\)；
- 12 个正式任务 `23009466`–`23009477` 全部在
  `xhacnormalb` 分区启动，首次审计为 12/12 运行、12/12 初始检查点、
  0 个非空错误日志；
- 依赖控制器 `23009668` 已排队等待这 12 个作业结束；它只自动恢复
  TIMEOUT、OOM 和节点类故障，代码失败、人工取消或检查点缺失会停止并
  留待审计；全部数据完成后自动运行冻结的剖面/宽度收敛门；
- 首批作业所用的精确 runner/backend 已冻结到
  `results_research_program/hpc/convergence_source_20260729/`。12/12
  任务的有效数值、1001 点输出网格和 canonical job hash 全部逐项相同；
  旧 runner 的真实 HDF5 checkpoint 由当前 runner 恢复后，磁化、电流、
  连通 \(C^{zz}\) 和 FCS 等全部数组最大差为 0；
- 续跑来源门已经同时装到控制器提交前和计算节点启动前。它只接受
  “首批 runner + 首批 backend”或“已验证当前 runner + 当前 backend”
  两个完整哈希对，任何混搭、源码改动、清单改动、非 \(J_2=0\) 条件或
  证据缺失都会停止续跑并标为 `needs_attention`；
- 本地 97 项测试通过；SCNet 上 12/12 任务均通过只读来源检查，部署前后
  权威提交记录、12 个 Slurm ID 和控制器 `23009668` 均未改变，部署过程
  新提交作业数为 0；
- Codex 心跳 `kharkov` 每小时检查一次队列、进度、资源、日志和控制器；
  正常运行不通知，失败、门槛结果或下一阶段启动时才回到本任务处理；
- 全部源码、环境、日志、检查点和原始数据均写入团队配额目录
  `/work/share/giggleliu/cfys01/kharkov_burgers_20260729`。
- \(J_2\) 集群预检脚本与本地证据已同步到团队目录；首次提交在生成作业号
  之前被账号级 `AssocGrpSubmitJobsLimit`（200/200）拒绝，已记录六小时
  退避且不会重复提交。这个状态不是物理或代码失败。
- 已批准的 production-v2 与运行中收敛清单完全隔离：34 个 A 条件和
  34 个 B 条件已经物化，A 中 32 个新计算、2 个 fine 数据复用，
  A/B 的 FCS 逻辑数分别为 7/3；构建器记录
  `submission_performed=false`；
- production-v2 的本地源闭包、精确零初态、既有 FCS/checkpoint 后端和
  分组 J2 兼容性均已通过，证据状态为
  `local_pass_cluster_pending`；计算节点脚本已准备但尚未提交；
- 两模随机求解器样本预算在不读取量子拟合误差的情况下冻结为：
  筛选 1024、最终至少 2048 条轨迹；
- 当前联合判别器通过 154 项本地测试，并精确报告 11 个缺失输入
  （9 个新数据集、2 个复用证明）；在这些输入到齐前不输出参数；
- 分层判决现在明确区分
  `independent_two_burgers_supported`、
  `coupled_two_mode_supported` 和
  `memory_or_more_modes_required`。
- Protocol v1.2 已在 Production-A 结果出现前冻结：标量、独立两 Burgers
  和耦合两模三种幸存预测均有资格进入独立 B 阶段；候选族失败和未决状态
  停止。解盲门与 34-job 事务控制器通过 170 项本地回归；SCNet 部署后
  编译通过，缺少 A/selection/unblinding 时的三次干跑均以退出码 2 阻断，
  未产生 submission、selection、unblinding、B bundle 或 B 数据。

实现校验报告：

- `results_research_program/tenpy_smoke/validation/REPORT.md`
- `results_research_program/tenpy_smoke/fcs_validation/REPORT.md`
- `results_research_program/tenpy_smoke/exact_validation/REPORT.md`
- `results_research_program/tenpy_smoke/resume_validation/REPORT.md`
- `results_research_program/tenpy_smoke/j2_grouped_validation/summary.json`
- `results_research_program/tenpy_smoke/j2_grouped_validation/grouped_equivalence/summary.json`
- `results_research_program/tenpy_smoke/j2_grouped_validation/resume_actual/summary.json`
- `results_research_program/tenpy_smoke/PREFLIGHT_REPORT.md`
- `results_research_program/hpc/j2_validation_20260730.json`
- `results_research_program/hpc/production_v2_validation_20260730.json`
- `results_research_program/production_manifest_v2.json`
- `results_research_program/tenpy_jobs_production_v2/execution_matrix.json`
- `results_research_program/two_mode/solver_budget.json`
- `results_research_program/two_mode/summary.json`
- `results_research_program/hpc/convergence_source_20260729/amendment.json`
- `results_research_program/hpc/convergence_source_20260729/local_validation.json`
- `results_research_program/hpc/convergence_source_20260729/scnet_deployment.json`
- `results_research_program/tenpy_jobs/execution_matrix.json`
- `results_research_program/tenpy_jobs_production_a/execution_matrix.json`
- `results_research_program/tenpy_jobs_production_b_locked/execution_matrix.json`
- `results_research_program/hpc/scnet_submission_20260729.json`
- `hpc/scnet/README.md`

## 当前外部计算

第一批清单中的 12 个 `stage="convergence"` 任务已经在 SCNet 运行：

1. `amp_mu005_up`；
2. `amp_mu005_down`；
3. `shape_double_wall`；
4. `background_p005_up`；

每个条件分别计算 coarse、medium、fine。需要保存磁化剖面；四个代表条件
还必须保存局域磁流。数据写入清单给定的 `output_path`，并满足
`ResearchDataset` 元数据规范。

运行数据校验：

```bash
python3.12 scripts/validate_research_datasets.py --require-complete
python3.12 scripts/run_convergence_audit.py --require-accepted
```

这里第一条在阶段 B 仍盲态时不应加 `--include-blinded`；实际操作可先只
检查非盲态记录。只有四个条件全部通过以下冻结门槛，才进入 production A：

\[
E_{\rm profile}\le 0.002,\qquad
E_W\le0.003.
\]

若失败，返回 `simulation_unresolved` 并加密度、缩小时间步或扩大系统，
不允许把数值误差写成物理证伪。

后端入口是 `scripts/run_tenpy_research_job.py`，可选依赖固定在
`requirements-tensor-network.txt`。正式提交前必须先在目标集群测量一个
缩短时间的粗网格任务的峰值内存和墙钟时间，尤其是含三个正计数场分支的
FCS 任务。现有本机 smoke 只证明算法和观测量实现，不提供 \(t=200\) 的资源
外推保证。

当前 12 个任务不因后续 \(J_2\) 扩展而重启。首批源码与当前源码的
\(J_2=0\) 等价性已经用真实中断—恢复和全部正式任务的静态身份双重证明，
每次后续 slice 仍必须重新通过冻结 amendment；因此“保留健康任务”不等于
放宽可复现性要求。

最近邻 purification TEBD 继续覆盖 \(\Delta=0.8,1,1.2\)。对
\(J_2=0.1\)，现已增加独立的二物理自旋分组后端，并通过本地精确对角化、
守恒、spin-flip、FCS、\(J_2=0\) 表示等价和真实中断—恢复验证。这里不把
本地结果直接当作集群生产许可：证据文件
`results_research_program/hpc/j2_validation_20260730.json` 当前状态为
`local_pass_cluster_pending`。只有 `hpc/scnet/j2_preflight.sbatch` 在
SCNet 计算节点上完整通过，证据状态才能升为严格的 `pass`；届时重建
production-A 清单应由当前的 29 ready / 2 blocked 变成 31 ready / 0
\(J_2\) blockers。

首次集群预检提交因团队账号同时提交作业上限 200/200 被 Slurm 在创建
作业前拒绝，因此没有作业号，也不能伪造成功提交记录。退避状态保存在
团队目录的 `jobs/j2_preflight_attempt.json`；心跳会在
`retry_not_before` 之后至多尝试一次。即使 \(J_2\) 集群门先通过，
production A 仍必须等待 12 个正式任务给出 `accepted` 收敛门，不能提前
启动。

## 生产和开盲顺序

1. 完成所有 production A，时间只到 \(t=200\)；
2. 用 \(50\!-\!150\) 拟合、\(150\!-\!200\) 验证；
3. 完成 27 个预注册交叉验证分片、聚合与 validation，冻结
   `validation_selection.json`；
4. 只在冻结状态属于
   `scalar_surrogate_not_rejected`、
   `independent_two_burgers_supported` 或
   `coupled_two_mode_supported` 时继续；若为
   `memory_or_more_modes_required` 或未决状态则停止；
5. 复核源码、配置、随机种子、A 阶段、分析和 selection 的全部 hash；
6. 先运行不带确认的预览命令，确认它拒绝开盲：

   ```bash
   python scripts/unblind_research_test.py --team-root "$TEAM_ROOT"
   ```

7. 人工确认后执行唯一一次不可逆命令：

   ```bash
   python scripts/unblind_research_test.py \
     --team-root "$TEAM_ROOT" --confirm-unblind
   ```

8. 对 Production B 做只读干跑，必须得到 34 个执行任务、3 个 FCS、
   0 个 A 脚本；之后才可显式 `--submit`；
9. 用 `--resume` 原子刷新状态，只允许登记的基础设施故障从 checkpoint
   恢复；
10. 完成 \(200\!-\!400\) 后重新生成跨初态、两模和总判决报告。

这里 Production B 的有限条件和有限时间窗结果可以反驳或支持登记的预测
定律，但不能把“未拒绝”提升为 Burgers 方程的全局严格证明。

## 已冻结的两模/FCS 分层判别

原先待选择的 FCS 设计点已由用户选择“推荐的分层判别方案”解决。确认性
判别只使用已冻结的 34 条 production-v2 条件，不再追加
\((A,B,A+B)\) 三元组。两模相对标量必须在留出窗改善至少 30%，且 2,000
次、10 时间单位分块的配对 bootstrap 95% 区间下界严格大于零。耦合两模
相对独立两模还必须改善至少 10% 且满足 \(\Delta\mathrm{BIC}\ge10\)。
如果所有登记模型失败，结论是“需要记忆或更多模”，不会在看见结果后增加
自由度。
