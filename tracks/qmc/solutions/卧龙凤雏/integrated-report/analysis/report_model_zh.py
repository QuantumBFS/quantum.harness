"""三模型中心荷验证报告的简体中文、格式无关内容模型。"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence, Tuple

from analysis.locale import ZH_SECTION_TITLES
from analysis.report_model import (
    Callout,
    CodeBlock,
    Equation,
    Figure,
    PageBreak,
    Paragraph,
    ReportDocument,
    Section,
    Table,
)
from analysis.sources import Gate, ModelResult


def build_report_zh(models: Sequence[ModelResult]) -> ReportDocument:
    indexed = {model.slug: model for model in models}
    required = {"clean-ising", "nishimori-ising", "weak-self-dual"}
    if set(indexed) != required:
        raise ValueError("中文版综合报告必须且只能包含三个已批准模型")
    clean = indexed["clean-ising"]
    nishimori = indexed["nishimori-ising"]
    weak = indexed["weak-self-dual"]
    abstract = (
        "本报告利用已经冻结并通过科学门控的数值证据，验证三类临界体系中的中心荷提取。"
        "第一类是二维方格纯净 Ising 模型，它同时提供确定性的传递矩阵基准和 Wolff 团簇"
        "蒙特卡洛路线；第二类是 Nishimori 线上的淬火随机键 Ising 模型，它要求正确处理"
        "无序平均、跨宽度协方差和分层自助法；第三类是 Born 相关的弱自对偶 Majorana "
        "测量网络，它用高斯协方差矩阵传播量子轨迹，并从 Shannon 自由能率提取有效中心荷。"
        f"三条随机估计分别为 {clean.estimate:.6f}、{nishimori.estimate:.6f} 和 "
        f"{weak.estimate:.6f}，其声明区间分别与目标 0.5、0.464 和 0.447 相容。"
        "报告的重点不只是数值接近：每项结果都说明估计量为什么成立、有限尺寸公式如何得到、"
        "参数为什么这样设置、误差怎样传播、哪些系统误差仍然存在，以及独立物理校验如何降低"
        "“代码运行正常但实现了错误模型”的风险。"
    )
    return ReportDocument(
        title="中心荷的三条验证路径",
        subtitle="纯净 Ising、Nishimori 无序与弱自对偶 Majorana 动力学",
        author="卧龙凤雏团队 · Quantum Harness 挑战 #122",
        abstract=abstract,
        sections=(
            _executive(clean, nishimori, weak),
            _foundation(),
            _architecture(),
            _clean_section(clean),
            _nishimori_section(nishimori),
            _weak_section(weak),
            _comparison(clean, nishimori, weak),
            _errors(clean, nishimori, weak),
            _implementation(),
            _conclusions(clean, nishimori, weak),
            _appendices(clean, nishimori, weak),
        ),
    )


def _executive(
    clean: ModelResult, nishimori: ModelResult, weak: ModelResult
) -> Section:
    rows = tuple(
        (
            _model_name(model.slug),
            f"{model.estimate:.6f}",
            f"{model.standard_error:.6f}",
            f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]",
            f"{model.target:.3f}",
            f"{model.runtime_s:.1f}",
            "通过",
        )
        for model in (clean, nishimori, weak)
    )
    return Section(
        ZH_SECTION_TITLES[0],
        "executive-summary",
        (
            Paragraph(
                "中心荷（central charge，c）是二维临界点长距离自由度的一种紧凑度量。"
                "在共形场论中，它控制圆柱或环面自由能的普适 Casimir 修正。数值计算面对的"
                "困难是：这个修正远小于随系统宽度增长的体项。因而，一条看起来平滑的拟合曲线"
                "并不足以构成验证；还必须控制采样噪声、时间相关、跨宽度相关、有限尺寸偏差、"
                "浮点稳定性，以及模型或归一化约定被悄悄实现错误的可能性。"
            ),
            Paragraph(
                "三项研究构成一架逐级增加难度的梯子。纯净 Ising 中，传递矩阵给出接近确定性"
                "的参考答案，Wolff 团簇采样与热力学积分则提供独立随机路线。Nishimori 模型把"
                "统一耦合替换成淬火随机符号，因此必须在固定无序历史上先求热配分函数，再平均"
                " log Z；同一无序行还被用于多个宽度，故误差分析必须保留协方差。弱自对偶网络"
                "不再采样平衡自旋，而是连续采样依赖当前量子态的 Born 结果；可观测量也从普通"
                "自由能变成 Shannon 信息率。"
            ),
            Table(
                "主要数值结果",
                ("模型", "估计值", "标准误", "95% 置信区间", "目标", "运行时间/秒", "门控"),
                rows,
                "为了让三行都具有采样区间，纯净 Ising 行列出蒙特卡洛结果；其独立传递矩阵"
                f"结果为 {clean.exact_estimate:.6f}。运行时间是冻结工作流的实测值，不应跨"
                "硬件直接解释成算法复杂度。"
            ),
            Callout(
                "核心结论",
                "三项估计的声明区间都包含各自基准值。这表示现有冻结数据在所报精度下没有分辨出"
                "显著偏差；它并不表示估计值与目标严格相等，也不表示未测试的有限尺寸修正为零。",
                "result",
            ),
            Paragraph(
                f"纯净路线得到 c={clean.estimate:.6f}，95% 区间为 "
                f"[{clean.ci95[0]:.6f}, {clean.ci95[1]:.6f}]；确定性传递矩阵给出 "
                f"{clean.exact_estimate:.6f}。普通淬火 Nishimori 估计为 "
                f"c_eff={nishimori.estimate:.6f}，区间 "
                f"[{nishimori.ci95[0]:.6f}, {nishimori.ci95[1]:.6f}]。弱自对偶估计为 "
                f"c_eff={weak.estimate:.6f}，区间 "
                f"[{weak.ci95[0]:.6f}, {weak.ci95[1]:.6f}]。所有冻结结果中的必需门控均通过。"
            ),
            Figure(
                Path("generated/zh/central-charge-intervals.png"),
                "三个模型的中心荷估计、置信区间与基准目标。",
                "三个中心荷估计及 95% 置信区间与各自基准值的并列比较。",
                "不同模型的误差来源和有限尺寸公式不同，因此区间宽度只能描述各自工作流，"
                "不能单独用来给模型或算法排序。",
            ),
            Paragraph(
                "本报告使用“验证”一词时采用操作性含义：预先声明的统计区间覆盖目标，同时"
                "模型专属的物理、数值与采样门控通过。验证不是数学证明，而是一组可复现、"
                "可反驳的证据链。任何一个必要环节失败——例如随机键频率错误、Born 概率不依赖"
                "状态，或拟合窗口变化造成巨大漂移——都应阻止发布一个看似正确的中心荷数字。"
            ),
        ),
    )


def _foundation() -> Section:
    return Section(
        ZH_SECTION_TITLES[1],
        "conceptual-foundation",
        (
            PageBreak(),
            Paragraph(
                "临界点的相关长度发散，微观格点细节在远距离被重整化，只留下少数普适量。"
                "二维共形场论把尺度与角度变换组织成强约束结构，中心荷 c 出现在能量动量张量"
                "代数、纠缠熵以及有限尺寸自由能中。这里选择有限尺寸自由能，是因为三种模型"
                "都能在长圆柱上形成一个逐层累积的对数归一化率，即使“层”的物理意义不同。"
            ),
            Equation(
                "f(L) = f_infinity + s pi c/(6 L^2) + O(L^-4)",
                "f(L) 是每面积或等价归一化后的自由能密度，f_infinity 是非普适体项，"
                "s 由自由能与 log Z 的符号约定决定。中心荷位于很小的 L^-2 曲率中；"
                "L^-4 项代表最领先的无关算符修正。忽略该项会让最小宽度对斜率产生过大影响。",
                "1",
            ),
            Paragraph(
                "“有效中心荷”（effective central charge，c_eff）用于含无序或信息论测度的"
                "体系。它仍然是相应有限尺寸 Casimir 项的系数，但未必等同于一个幺正"
                "平衡共形场论的普通 c。这个术语提醒读者：必须连同所平均的概率测度、所取的"
                "对数以及归一化方式一起解释数字。0.464 与 0.522 的区别正来自不同复制数或"
                "Born 权重，而不是同一估计量的两种精度。"
            ),
            Equation(
                "estimate = bulk term + universal Casimir term + correction terms",
                "三条路线都使用这一逻辑。体项携带大部分幅值，Casimir 项携带中心荷，"
                "修正项吸收尚未进入渐近区的宽度效应。拟合窗口必须事先冻结，并用替代窗口"
                "诊断；若先观察结果再挑最接近目标的窗口，置信区间便不再反映选择过程。",
                "2",
            ),
            Paragraph(
                "统计误差与系统误差要严格分开。增加蒙特卡洛步数通常让标准误按有效独立样本数"
                "的平方根下降，但不会自动消除有限宽度偏差、错误符号、错误边界条件或错误随机"
                "集合。扩大 L 范围主要帮助区分 L^-2 信号与更高阶修正；增加独立副本或流主要"
                "帮助估计跨样本波动；精确恒等式和小系统枚举则针对实现错误。"
            ),
            Equation(
                "SE(mean) ~= sigma sqrt(2 tau_int / N)",
                "N 是测量数，tau_int 是积分自相关时间。若连续样本相关，直接把 N 当作独立"
                "样本数会低估误差。三种工作流都把序列分块，并在恰当独立单位上重采样：纯净"
                "Ising 使用蒙特卡洛块，Nishimori 使用保持宽度向量的副本—行块，弱自对偶使用"
                "独立轨迹流及其层块。",
                "3",
            ),
            Table(
                "三个模型中“随机性”的不同含义",
                ("模型", "被随机采样的对象", "确定性求和对象", "必须保留的相关"),
                (
                    ("纯净 Ising", "热平衡自旋团簇", "传递矩阵基准", "同一链内的时间相关"),
                    ("Nishimori", "淬火随机键历史", "固定键历史下的边界自旋", "同一无序行产生的跨宽度相关"),
                    ("弱自对偶", "依赖当前态的 Born 结果", "高斯协方差更新代数", "同一轨迹内的时空相关"),
                ),
                "相同的“bootstrap”名称不能掩盖重采样单位不同。错误地逐行独立重采样会破坏"
                "设计中的协方差结构，从而给出没有物理意义的误差条。",
            ),
            Callout(
                "阅读公式的原则",
                "首先确认被拟合的是 F、−F、log Z、每格点密度还是每层信息率；其次确认宽度"
                "归一化；最后再检查 Casimir 系数的符号和 6/π 转换。大多数数量级正确但中心荷"
                "错误的问题，都能在这三步中被定位。",
                "principle",
            ),
        ),
    )


def _architecture() -> Section:
    return Section(
        ZH_SECTION_TITLES[2],
        "shared-architecture",
        (
            Paragraph(
                "所有计算密集的随机采样与状态演化均由 Rust 完成。Rust 提供可预测的内存布局、"
                "显式浮点类型、并行迭代器以及编译期所有权和索引检查，适合运行数分钟到数小时"
                "的生产模拟。Python 只在原子化数据文件写出后介入，负责模式校验、聚合、回归、"
                "bootstrap 和绘图。这个边界既满足“蒙特卡洛用 Rust、数据处理与图表用 Python”"
                "的要求，也防止交互式分析代码改变随机内核。"
            ),
            Paragraph(
                "三项 Rust 模拟统一采用 Xoshiro256++。基种子不会直接复用于所有宽度和副本；"
                "程序用模型标识、宽度、副本或轨迹编号及用途派生稳定的流键。因而，并行线程的"
                "调度顺序不会决定某个物理流拿到哪段随机数。相同配置与流键可逐字节重放，"
                "不同流又不会因简单复用种子而产生意外相关。"
            ),
            CodeBlock(
                "确定性随机流派生",
                "key = hash(base_seed, model_tag, width, replica, purpose)\n"
                "rng = Xoshiro256PlusPlus::seed_from_u64(key)\n"
                "for block in assigned_blocks:\n"
                "    estimate = simulate_block(rng, state)\n"
                "    write_atomic(stream_key, block, estimate)",
                "流键属于科学记录的一部分。原子替换避免中断后留下外观有效的半截 JSON；"
                "稳定键使已经完成且摘要哈希一致的流可以安全复用。",
            ),
            Paragraph(
                "原始输出保存分块记录，而不只保存一个总均值。分块让分析能够检查前后半程漂移、"
                "副本间差异、自相关与单个异常流的影响。块的含义随模型变化：纯净 Ising 以 "
                "Wolff sweeps 分块，Nishimori 以随机传递行分块，Majorana 网络以电路层分块。"
                "块长度必须大于主要相关尺度，但也要留下足够多块供协方差和 bootstrap 估计。"
            ),
            Table(
                "共享流水线与模型专属部分",
                ("阶段", "共享原则", "模型专属实现"),
                (
                    ("配置", "先校验后运行；生产门控冻结", "临界耦合、宽度、流数量和几何"),
                    ("采样", "独立可重放的 Xoshiro256++ 流", "团簇、随机键行或 Born 结果"),
                    ("状态", "稳定更新并记录不变量", "自旋、2^L 向量或协方差矩阵"),
                    ("聚合", "保留块与独立流身份", "热平均、淬火平均或条件熵平均"),
                    ("拟合", "体项 + Casimir 项 + 领先修正", "符号、宽度幂次与协方差矩阵"),
                    ("验证", "必需门控失败即停止", "精确 c、恒等式或小系统轨迹枚举"),
                ),
                "共享的是科学纪律，不是强迫三种模型使用同一个统计公式。",
            ),
            Paragraph(
                "manifest 记录完整配置、软件版本、命令、种子、线程数、运行时间和 SHA-256。"
                "加载器拒绝未知 schema、缺文件、空表、无穷值、目标值冲突和必需门控失败。"
                "生成报告前后会再次比较来源指纹，防止报告一半来自旧数据、一半来自刚被覆盖的"
                "新数据。正式 HTML/PDF 先写临时文件，所有验证通过后才原子替换。"
            ),
            Paragraph(
                "Python 分析也保持确定性：bootstrap 种子固定，表格排序稳定，Matplotlib 元数据"
                "固定，PDF 构建启用 invariant 模式。确定性不是为了把随机误差“变没”，而是为了"
                "把数据变化与软件噪声区分开。若来源不变却生成不同摘要或图像，工作流本身就需要"
                "调查，不能把差异误认为新的物理信号。"
            ),
        ),
    )


def _clean_section(model: ModelResult) -> Section:
    return Section(
        ZH_SECTION_TITLES[3],
        model.slug,
        (
            PageBreak(),
            Paragraph(
                "二维方格纯净 Ising 模型是整套工作流的校准基准。每个格点自旋 "
                "s_i=±1，只与最近邻相互作用；周期边界把有限格点卷成环面。临界耦合固定为"
                "精确值 K_c=0.4406867935097714，目标中心荷为 c=1/2。由于没有淬火无序，"
                "我们可以同时使用传递矩阵和热蒙特卡洛，从两套近乎独立的数值假设获得答案。"
            ),
            Equation(
                "Z(K) = sum_{s} exp[K sum_<ij> s_i s_j]",
                "配分函数对所有自旋构型求和。这里采用无量纲耦合 K，哈密顿量符号与后续"
                "热力学积分保持一致。周期边界、每格点归一化和自由能符号若有任何一处不一致，"
                "都将改变有限尺寸斜率，因此精确传递矩阵是非常有力的约定校验。",
                "4",
            ),
            Paragraph(
                "矩阵自由传递算法保存长度 2^L 的边界向量，却不构造 2^L×2^L 稠密矩阵。"
                "横向相互作用先逐构型乘权，纵向两态因子再按位作用；一次更新复杂度约为 "
                "O(L 2^L)。幂迭代提取主特征值，严格的特征值与残差容差使当前宽度上的结果"
                "可视为确定性参考。小 L 还可与显式稠密矩阵逐元素比较。"
            ),
            CodeBlock(
                "矩阵自由传递作用",
                "v = horizontal_weights * input\n"
                "for site in 0..L:\n"
                "    v = apply_two_state_vertical_factor(v, site, K)\n"
                "normalize v and accumulate log_norm\n"
                "repeat until eigenvalue and residual tolerances pass",
                "算法只保存 2^L 向量。被移出的归一化对数给出每行自由能，既避免溢出，也保留"
                "所需物理量。此路线不依赖 Wolff 随机数或积分网格。",
            ),
            Paragraph(
                "随机路线采用 Wolff 团簇更新。临界附近，大相关畴使单自旋 Metropolis 更新"
                "发生临界慢化；Wolff 从一个种子自旋出发，按耦合决定的成键概率生长同向团簇，"
                "再整体翻转。长波模式因此能够集体移动，但连续团簇更新仍非完全独立，所以"
                "测量按 320 sweeps 分块，并用四个独立副本检查链间一致性。"
            ),
            Equation(
                "F(K_c) = -N log 2 + integral_0^Kc <H>_K dK",
                "蒙特卡洛直接估计期望值而非绝对配分函数。K=0 时 Z=2^N 提供精确锚点；"
                "在 129 点网格上对平均能量做 Simpson 积分可重建临界自由能。嵌套 65 点"
                "网格复用细网格节点，用于检验离散积分误差是否小于当前采样误差。",
                "5",
            ),
            Paragraph(
                "热力学积分的优点是不用估计极小的绝对概率；代价是每个 K 点的采样误差会相关地"
                "传播到所有宽度的自由能。bootstrap 在块层级重采样完整积分曲线，再对每个抽样"
                "结果做有限尺寸拟合，因而置信区间包含积分噪声与回归传播，而不是只对最终斜率"
                "套一个独立同分布公式。"
            ),
            Equation(
                "g(L)/L = f_infinity - pi c/(6 L^2) + a/L^4",
                "主拟合使用 L_min=6；L_min=4 和 8 是预先声明的稳定性诊断。传递矩阵与蒙特"
                "卡洛使用相同符号、边界和拟合设计矩阵，所以二者一致同时检查自由能归一化、"
                "Casimir 系数和 c=6 beta/pi 的转换。",
                "6",
            ),
            Callout(
                "纯净基准结果",
                f"传递矩阵得到 c={model.exact_estimate:.6f}；独立 Wolff/积分路线得到 "
                f"c={model.estimate:.6f}，SE={model.standard_error:.6f}，95% 区间 "
                f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]。两者均与精确值 0.5 相容。",
                "result",
            ),
            *_model_figures(model.slug),
            _parameter_table(model),
            _gate_table(model),
            Paragraph(
                "主要随机限制来自热力学积分噪声经有限尺寸斜率放大。更多 sweeps 可以降低"
                "这一标准误，但不会替代嵌套网格检查或拟合窗口检查。传递矩阵远比蒙特卡洛精确，"
                "却不应被用来“校正”随机结果；保留两套独立代码，才能让一致性真正约束符号、"
                "边界与分析约定，而不是让一条路线抄写另一条路线的答案。"
            ),
        ),
    )


def _nishimori_section(model: ModelResult) -> Section:
    return Section(
        ZH_SECTION_TITLES[4],
        model.slug,
        (
            PageBreak(),
            Paragraph(
                "Nishimori 随机键 Ising 模型给每条最近邻键赋符号 tau_ij。正号为铁磁键，"
                "负号为反铁磁键；负键概率 p 会制造挫折，使某些回路不能同时满足所有键。"
                "无序是淬火的（quenched disorder）：必须先对固定键历史求热配分函数，再对"
                "log Z 做无序平均。若先平均 Z 再取对数，就变成退火集合并改变所测普适量。"
            ),
            Equation(
                "P(tau_ij=-1)=p,    K_N=(1/2) log((1-p)/p)",
                "Nishimori 线把耦合 K_N 与负键概率绑在一起。当前 p=0.1092212，"
                "K_N=1.049360476302568。这一关系带来精确 gauge 恒等式，可同时检查随机键"
                "分布、耦合符号、传递核和自由能归一化。",
                "7",
            ),
            Callout(
                "为什么目标是 0.464，而不是 0.522",
                "本报告计算普通淬火平均 E[log Z] 的有效中心荷，基准约为 0.464。约 0.522 "
                "属于相关问题中的 Born 权重或更高复制数对象；二者使用不同集合权重，不能把"
                "一个数字当作另一个数字的有限采样修正。",
                "warning",
            ),
            Paragraph(
                "对每个随机传递行，Rust 在 2^L 个边界自旋态上应用水平键与垂直键因子。"
                "每行后用 L1 范数归一化以避免上溢，并累计被移出的 log 范数。长随机矩阵乘积"
                "的主 Lyapunov 指数就是逐行 log 配分函数率；再除以行数与宽度得到淬火密度 "
                "phi_L。热边界自旋被传递向量确定性求和，随机性只来自键历史。"
            ),
            CodeBlock(
                "淬火随机传递乘积估计量",
                "for replica in disorder_replicas:\n"
                "    v = positive_initial_vector()\n"
                "    for row in burn_in + measured_rows:\n"
                "        tau = sample_bonds(xoshiro256pp)\n"
                "        v = apply_random_transfer(v, tau, K_N)\n"
                "        scale = l1_norm(v)\n"
                "        v /= scale\n"
                "        if measured: block_log_norm += log(scale)\n"
                "average block_log_norm/(rows*L) after each disorder history",
                "逐行归一化不是任意数值技巧；每个 log(scale) 正是 Lyapunov 自由能估计量所需"
                "的增量。Xoshiro256++ 产生可重放的键行。",
            ),
            Paragraph(
                "最大宽度的随机键行会切成嵌套前缀，同时供所有更小宽度使用。这种 common-"
                "disorder 设计显著降低不同 L 之差的噪声，而中心荷正来自这些差的微小曲率。"
                "代价是宽度之间高度相关。bootstrap 必须把一个副本—块的完整宽度向量一起"
                "重采样；若逐宽度独立抽样，会破坏刻意设计的协方差并误报 c_eff 标准误。"
            ),
            Equation(
                "phi_L = phi_infinity + pi c_eff/(6 L^2) + a/L^4",
                "phi 是 log 配分函数密度，因此 Casimir 项符号与常规负自由能写法相反。"
                "主拟合包含 L^-4 修正并使用全部当前宽度；L_min=6 作为诊断窗口，用配对"
                "bootstrap 计算两窗口差异，避免把高度相关的两个估计当作独立。",
                "8",
            ),
            Paragraph(
                "本报告当前使用的圆柱宽度为 L = 4, 6, 8, 10, 12, 14；更大宽度的模拟尚未"
                "纳入本版冻结数据。每个宽度向量有 8 个独立无序副本，每副本丢弃 4,096 行，"
                "测量 2,097,152 行，块长 16,384 行，即每副本 128 块。增加步骤会降低无序"
                "采样标准误；增加 L=16、18 等宽度则更直接检验有限尺寸修正，两者解决的问题"
                "不同。"
            ),
            Equation(
                "d phi/dK |_(K_N) = 2 tanh(K_N)",
                "Nishimori 内能恒等式用 delta K=10^-4 的中心有限差分检验。正负扰动重用完全"
                "相同的键行，大幅抵消无序噪声。当前导数与解析值的绝对差约 7.46e-5；这一"
                "单一检查同时覆盖耦合定义、键符号、传递归一化和 Nishimori 线关系。",
                "9",
            ),
            Callout(
                "Nishimori 结果",
                f"普通淬火估计为 c_eff={model.estimate:.6f}，"
                f"SE={model.standard_error:.6f}，95% 区间 "
                f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]。基准 0.464 位于区间内，"
                "全部必需科学门控通过。",
                "result",
            ),
            *_model_figures(model.slug),
            _parameter_table(model),
            _gate_table(model),
            Paragraph(
                "这里的主要随机不确定性是无序历史间波动，而不是固定键历史内的热自旋抽样，"
                "因为传递操作已经确定性求和边界自旋。有限宽度修正是另一项系统误差。当前"
                "配对窗口差异与零相容，说明数据没有分辨出显著 L_min 漂移；它仍不能证明所有"
                "L^-6 或非解析修正均可忽略。后续扩尺寸时必须更新运行时间门控和拟合诊断，"
                "不能只把新点附到旧图上。"
            ),
        ),
    )


def _weak_section(model: ModelResult) -> Section:
    return Section(
        ZH_SECTION_TITLES[5],
        model.slug,
        (
            PageBreak(),
            Paragraph(
                "弱自对偶模型是受测量的 Majorana 网络，而非平衡自旋体系。高斯态可用实反对称"
                "协方差矩阵 Gamma 表示，避免保存指数大的多体波函数。电路层交替测量 onsite "
                "与 bond Majorana 双线性算符；theta=pi/4 且两类弱测量强度相等时，一个 "
                "Majorana 平移交换电、磁描述，形成统计意义上的自对偶。"
            ),
            Paragraph(
                "高斯协方差方法让 L=32 的生产宽度可行，但物理约束必须持续监测。纯高斯态满足"
                "Gamma^T=-Gamma 且 Gamma^2=-I（允许浮点误差）。弱测量对应 Gamma 的分式"
                "线性更新；周期性稳定化把数值漂移投影回纯态流形，同时记录稳定化前的最大"
                "不变量误差。若只修正而不记录误差，就可能把不稳定算法伪装成稳定轨迹。"
            ),
            Equation(
                "P(s|Gamma) = [1 + s tanh(beta) <i gamma_a gamma_b>_Gamma]/2",
                "二元结果 s 的概率依赖当前 Gamma，因此结果在空间和时间上 Born 相关。"
                "若把每个 s 替换为独立公平符号，就会实现另一个无序集合。当前 "
                "beta=asinh(1)=0.881373587019543，概率始终由被测双线性期望决定。",
                "10",
            ),
            Paragraph(
                "直接 Shannon 估计量累计已发生结果的 surprise：−log P(s|Gamma)。实现采用"
                "Rao–Blackwell 化条件熵估计量：抽取 s 之前先记录该二元测量的条件熵。对条件"
                "期望求平均去除了额外掷硬币噪声，却不改变总体均值；状态更新仍使用真实抽出的"
                "s，所以物理轨迹分布未被替换。"
            ),
            Equation(
                "H_2(q) = -q log q - (1-q) log(1-q)",
                "q 是其中一个结果的条件概率。每次测量贡献一个二元熵，随后按测量行归一化。"
                "一个电路周期包含 onsite 与 bond 两行；漏掉这个二因子会同时重标度体信息率"
                "与 Casimir 系数，可能给出外观稳定却数值错误的 c_eff。",
                "11",
            ),
            CodeBlock(
                "Born 相关高斯轨迹",
                "Gamma = vacuum_covariance(L)\n"
                "for layer in burn_in + measured_layers:\n"
                "    for measurement_row in [onsite, bond]:\n"
                "        for (a,b) in row_pairs:\n"
                "            q = born_probability(Gamma, a, b, beta)\n"
                "            if measured: entropy_sum += binary_entropy(q)\n"
                "            s = sample_bernoulli(q, xoshiro256pp)\n"
                "            Gamma = weak_gaussian_update(Gamma, a, b, s, beta)\n"
                "    periodically_stabilize_and_check(Gamma)",
                "熵记录被 Rao–Blackwell 化，协方差更新仍使用 Xoshiro256++ 抽出的结果。"
                "因此降低的是估计量方差，而不是改变 Born 轨迹。",
            ),
            Equation(
                "gamma_1(L) = f_infinity L - pi c_eff/(6 L) + a/L^3",
                "gamma_1 是每纵向层的 Shannon 自由能率，主项随圆周 L 线性增长，普适项因此"
                "表现为 1/L。把等式除以 L 后，就得到与另外两章相同的 L^-2 Casimir 结构。"
                "主拟合用 L^-3 修正，替代拟合检查更高最小宽度、扩展修正和删除单个大宽度。",
                "12",
            ),
            Paragraph(
                "最终冻结数据使用偶数宽度 6 到 32，每个宽度 128 条独立轨迹流；预热层数为 "
                "20L，测量层数为 200L，块长为 5L。偶数宽度保持网络几何与 sector 约定。"
                "增加单流长度改善时间平均，增加独立流数改善轨迹间采样和 bootstrap 尾部；"
                "两者不能被一个总步数简单替代。"
            ),
            Paragraph(
                "自对偶性通过时空符号 tile 的电、磁涡旋密度检查。单边缺陷会产生相邻两类"
                "涡旋，构成小几何精确测试；生产数据则对配对的电减磁密度除以其标准误。"
                "观测 z=-1.460，位于预设双侧 95% 阈值内。自对偶只要求集合平均相等，"
                "不要求每条随机轨迹逐层电磁相等。"
            ),
            Callout(
                "弱自对偶结果",
                f"估计为 c_eff={model.estimate:.6f}，SE={model.standard_error:.6f}，"
                f"95% 区间 [{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]。目标 0.447 位于"
                "区间内，全部必需门控通过。",
                "result",
            ),
            *_model_figures(model.slug),
            _parameter_table(model),
            _gate_table(model),
            Paragraph(
                "最强剩余系统误差是有限尺寸模型选择。主 L^-3 修正、不同 L_min、删除 L=30、"
                "加倍块长和额外预热形成约 0.00553 的中心扩散；最大配对漂移约 0.594 个标准误。"
                "这些检查支持当前分辨率上的稳定性，但不意味着任何可能的修正模型都已穷尽。"
                "有效样本量与一阶滞后相关只诊断采样，不诊断错误的 Born 概率或有限尺寸展开。"
            ),
        ),
    )


def _comparison(
    clean: ModelResult, nishimori: ModelResult, weak: ModelResult
) -> Section:
    models = (clean, nishimori, weak)
    return Section(
        ZH_SECTION_TITLES[6],
        "cross-model-comparison",
        (
            PageBreak(),
            Paragraph(
                "最有价值的比较不是把三个数字排成名次，而是观察同一普适思想怎样落到三种"
                "不同数值对象上。长圆柱都有体贡献和依赖圆周的 Casimir 修正，中心荷来自小"
                "修正的系数；变化的是所累计的对数或信息率、概率平均顺序、相关结构和可用校验。"
            ),
            Table(
                "估计量与验证路线比较",
                ("模型", "有限尺寸可观测量", "随机来源", "强校验", "相对目标 z"),
                tuple(
                    (
                        _model_name(model.slug),
                        _observable(model.slug),
                        _sampler(model.slug),
                        _oracle(model.slug),
                        f"{(model.estimate-model.target)/model.standard_error:+.2f}",
                    )
                    for model in models
                ),
                "z=(估计−目标)/SE 只是标准化摘要。数据集合、修正项和协方差结构不同，"
                "相同 z 并不表示证据强度完全相同。",
            ),
            Paragraph(
                "纯净 Ising 的蒙特卡洛样本是热自旋构型，热力学积分从 K=0 精确锚点恢复"
                "绝对自由能。Nishimori 的蒙特卡洛样本是淬火键行，边界自旋在每个固定历史上"
                "由传递向量求和。弱自对偶的样本是状态依赖 Born 结果，协方差矩阵携带前序"
                "测量记忆。三者都“使用随机数”，但随机数所代表的测度完全不同。"
            ),
            Figure(
                Path("generated/zh/target-deviation.png"),
                "三个估计相对各自目标的标准误偏差。",
                "把估计与目标之差除以各自标准误，以统一尺度展示覆盖关系。",
                "该标准化不包含所有模型系统误差，也不能比较目标本身的理论不确定性。",
            ),
            Paragraph(
                "纯净结果的传递矩阵路线几乎不含采样噪声，蒙特卡洛区间主要来自团簇块和积分。"
                "Nishimori 区间必须保留 common-disorder 的跨宽度协方差。弱自对偶区间来自"
                "独立轨迹流的配对 bootstrap，并利用 Rao–Blackwell 条件熵减少单次结果噪声。"
                "所以不能用同一个“每点误差棒”公式重算三者。"
            ),
            Figure(
                Path("generated/zh/precision-runtime.png"),
                "三个冻结工作流的区间半宽和记录运行时间。",
                "并列展示报告精度与端到端运行时间，强调二者相关但不等价。",
                "运行时间依赖硬件、并行度和实现；柱高不是算法复杂度或模型难度的绝对排名。",
            ),
            Paragraph(
                "强校验也互补。纯净模型以精确 c=1/2 和传递矩阵为 oracle；Nishimori 以负键"
                "频率与内能恒等式检查集合约定；弱自对偶以小系统稠密 Born 枚举、高斯不变量和"
                "电磁自对偶检查轨迹物理。每个校验只约束一组失效模式，必须与采样、拟合和"
                "运行时间门控共同阅读。"
            ),
            Figure(
                Path("generated/zh/validation-gates.png"),
                "三种模型的必需科学门控覆盖矩阵。",
                "绿色表示该模型具有并通过相应类别的必需门控；灰色表示模型使用不同的专属检查。",
                "门控数量不能用于模型排名，因为每个门控约束的失效模式和统计功效不同。",
            ),
            Callout(
                "共同原则",
                "普适系数只能在非普适体项、相关噪声和有限尺寸修正都被显式建模后解释。"
                "看似相同的拟合形式不意味着相同的数据生成过程；可信度来自模型专属证据链。",
                "principle",
            ),
        ),
    )


def _errors(
    clean: ModelResult, nishimori: ModelResult, weak: ModelResult
) -> Section:
    return Section(
        ZH_SECTION_TITLES[7],
        "error-analysis",
        (
            Paragraph(
                "误差预算分成四层：随机采样、相关与重采样、有限尺寸模型、实现与数值误差。"
                "报告的标准误和 95% 区间主要量化前两层；替代窗口和修正项诊断第三层；精确"
                "oracle、不变量与恒等式针对第四层。把四层压成一个数字会制造虚假的确定性。"
            ),
            Table(
                "主要误差来源、诊断与改进方法",
                ("来源", "主要影响", "当前诊断", "正确改进"),
                (
                    ("有限采样", "置信区间变宽", "块 bootstrap、独立副本/流", "增加有效独立样本"),
                    ("时间相关", "朴素标准误偏小", "块长、ESS、一阶滞后", "延长链并增大到合理块长"),
                    ("跨宽度相关", "斜率协方差错误", "共同无序与配对重采样", "保留完整宽度向量"),
                    ("有限宽度", "中心荷发生偏移", "L_min 与修正项变体", "增加更大 L 并检验渐近模型"),
                    ("积分离散", "纯净自由能偏移", "65/129 点嵌套网格", "细化网格而非只加 sweeps"),
                    ("浮点漂移", "状态离开物理流形", "残差与高斯不变量", "稳定化并记录修正前误差"),
                    ("集合实现错误", "得到另一个普适量", "恒等式、Born 枚举、自对偶", "修正模型定义与采样核"),
                ),
                "每项改进只针对特定机制。增加蒙特卡洛步数不能修复错误的集合，也不能自动"
                "消除有限尺寸偏差。",
            ),
            Paragraph(
                f"纯净蒙特卡洛标准误为 {clean.standard_error:.6f}。在自相关结构不变的理想"
                "条件下，把有效测量量扩大四倍可使标准误约减半；实际收益取决于团簇块的 "
                "tau_int。若积分网格已成为主导误差，继续增加每个 K 点 sweeps 的收益会饱和，"
                "此时应先比较嵌套网格而不是盲目延长链。"
            ),
            Paragraph(
                f"Nishimori 标准误为 {nishimori.standard_error:.6f}，比纯净路线大，原因不是"
                "传递操作不精确，而是稀有无序历史造成样本间波动。增加 measurement_rows "
                "主要缩小统计区间；增加 L=16、18 等宽度主要检验 L^-4 修正和渐近区。当前"
                "结果只含 L=4 至 14，因此不能用更多行数代替更大宽度。"
            ),
            Paragraph(
                f"弱自对偶标准误为 {weak.standard_error:.6f}。Rao–Blackwell 化已经去除"
                "条件 Bernoulli 的一部分方差，剩余波动来自状态轨迹与跨层相关。增加每宽度"
                "独立流数可改善轨迹集合覆盖；增加每流层数改善时间平均。拟合变体中心扩散则"
                "属于有限尺寸系统误差，不能简单加到标准误后宣称成为严格置信区间。"
            ),
            Equation(
                "total discrepancy = statistical fluctuation + finite-size bias + implementation bias",
                "三项成分没有理由互相独立或服从同一分布。本报告只对统计部分给出频率学区间，"
                "对有限尺寸部分报告敏感性，对实现偏差使用通过/失败的 oracle 约束。这样的"
                "分层陈述比未经论证地平方相加更诚实。",
                "13",
            ),
            Callout(
                "增加蒙特卡洛步数能否提高精度？",
                "能，前提是新增样本贡献新的有效信息。标准误理想地按 1/sqrt(N_eff) 下降；"
                "但步数不改变有限尺寸展开、目标集合或代码约定。若目标是更窄区间，应增加"
                "有效独立样本；若目标是减少有限尺寸偏差，应优先增加宽度并做稳定性拟合。",
                "warning",
            ),
        ),
    )


def _implementation() -> Section:
    return Section(
        ZH_SECTION_TITLES[8],
        "implementation",
        (
            PageBreak(),
            Paragraph(
                "实现按单一职责拆分：配置解析器只负责校验宽度、样本预算、容差和临界常数；"
                "几何模块只定义相互作用或测量配对；数值核只更新自旋、传递向量或协方差矩阵；"
                "采样器拥有 RNG 与流状态并输出块记录；schema 层只负责序列化；Python 加载器"
                "在拟合之前拒绝不兼容数据。边界清晰使每个小系统 oracle 能直接对准一个模块。"
            ),
            Paragraph(
                "可恢复性以完整流为单位。完成的流文件包含 schema、完整配置、流身份和所有块；"
                "manifest 保存 SHA-256。重启时只有配置和摘要完全一致的流才按字节复用。"
                "这比向一个巨型文件追加更安全，因为中断不会留下难以判断是否完整的尾记录，"
                "线程调度变化也不会重分配随机数。"
            ),
            CodeBlock(
                "分析数据流",
                "manifest, blocks, oracles = validate_and_load(run_dir)\n"
                "summary = aggregate_with_model_specific_covariance(blocks)\n"
                "fits = fit_finite_size_family(summary)\n"
                "bootstrap = resample_declared_independent_units(blocks)\n"
                "gates = evaluate_predeclared_checks(fits, oracles, diagnostics)\n"
                "write_processed_tables_plots_and_report(summary, fits, gates)",
                "“模型专属协方差”必须显式出现。一个通用逐行 bootstrap 虽然代码更短，"
                "却会在至少一个数据集中破坏物理相关结构。",
            ),
            Table(
                "关键实现原则",
                ("原则", "具体机制", "防止的失效"),
                (
                    ("确定性", "按键派生 Xoshiro256++ 流", "线程调度改变样本"),
                    ("原子性", "临时文件验证后替换", "半成品被当作正式结果"),
                    ("兼容性", "schema 与完整配置相等", "不同运行被混合分析"),
                    ("完整性", "SHA-256 来源清单", "文件被静默替换或损坏"),
                    ("语言边界", "Rust 采样；Python 处理和绘图", "探索性分析污染数值内核"),
                    ("预声明", "冻结主拟合与必需门控", "事后挑选有利窗口"),
                    ("独立校验", "精确恒等式与小系统稠密比较", "错误方程产生正确外观"),
                ),
                "这些不是一般软件口号；每项都对应一条可能产生科学误导的具体路径。",
            ),
            Paragraph(
                "小规模精确测试具有不成比例的价值。纯净传递作用可在小 L 与稠密矩阵比较；"
                "Nishimori 随机键生成器可检查边缘频率、共享前缀和小传递乘积；Majorana "
                "协方差更新可与稠密 Hilbert 空间枚举每条短 Born 轨迹。先建立符号与归一化，"
                "再运行大规模统计，可显著缩短错误定位链。"
            ),
            Paragraph(
                "生产门控以结构化数据保存，而不是藏在报告文字中。每个门控含名称、准则、"
                "观测值、是否必需和通过状态；必需门控失败使分析非零退出。诊断配置可以显式"
                "关闭生产门控，但不得把诊断运行标成最终结果。报告列出门控，防止一个漂亮的"
                "中心荷掩盖热化失败、无序频率失败或高斯不变量漂移。"
            ),
            Paragraph(
                "复现顺序是：先验证 Rust 单元测试与锁文件，再检查配置和冻结 manifest；"
                "若要重跑模拟，保持相同流键和线程无关调度；随后运行 Python schema、拟合与"
                "bootstrap 测试；最后从已验证的 processed 表生成图表与报告。重新生成本报告"
                "不会运行蒙特卡洛，也不会改变任何中心荷估计。"
            ),
            Callout(
                "报告生成器的职责边界",
                "生成器读取已完成的冻结证据、重绘中文图表并排版 HTML/PDF。它不产生新的"
                "随机数、不修改结果目录，也不把翻译后的文字当作数值来源。",
                "principle",
            ),
        ),
    )


def _conclusions(
    clean: ModelResult, nishimori: ModelResult, weak: ModelResult
) -> Section:
    return Section(
        ZH_SECTION_TITLES[9],
        "conclusions",
        (
            PageBreak(),
            Paragraph(
                "三条路线共同验证了从有限尺寸 Casimir 项提取中心荷的计算思想，同时展示了"
                "“相同公式、不同测度”带来的实现差异。纯净 Ising 用精确传递矩阵校准整套"
                "符号与拟合；Nishimori 用普通淬火平均验证约 0.464，而不是 0.522；弱自对偶"
                "网络用状态条件 Born 采样和 Shannon 信息率验证约 0.447。"
            ),
            Paragraph(
                f"最终冻结估计为：纯净蒙特卡洛 {clean.estimate:.6f}，传递矩阵 "
                f"{clean.exact_estimate:.6f}；Nishimori {nishimori.estimate:.6f}；"
                f"弱自对偶 {weak.estimate:.6f}。所有目标都位于对应声明区间内，且模型专属"
                "必需门控通过。因此，结论是“与基准相容且工作流内部一致”，而不是“精确测得"
                "理论常数到小数点后六位”。"
            ),
            Paragraph(
                "可信度来自冗余：确定性与随机路线、边缘频率与精确恒等式、协方差不变量与稠密"
                "轨迹枚举、主拟合与预声明变体分别约束不同错误。任何单个校验都不充分；它们"
                "组成的证据链使一个失效模式同时逃过所有检查的可能性显著降低。"
            ),
            Paragraph(
                "下一步最有价值的改进是给 Nishimori 加入 L=16、18 等宽度，同时用试运行"
                "评估指数增长的 2^L 传递成本，再决定每个新宽度的测量行数。更长链可缩窄区间，"
                "更大宽度可控制渐近偏差；正式更新必须同时重建配对协方差、拟合窗口、门控、"
                "中文与英文报告，而不能只更新标题数字。"
            ),
            Callout(
                "可迁移的经验",
                "先定义测度和归一化，再设计独立 oracle；保存足够细的块级数据；用正确独立"
                "单位估计误差；把有限尺寸偏差与采样误差分开；最后才解释一个中心荷数字。",
                "result",
            ),
        ),
    )


def _appendices(
    clean: ModelResult, nishimori: ModelResult, weak: ModelResult
) -> Section:
    models = (clean, nishimori, weak)
    provenance_rows = tuple(
        (
            _model_name(model.slug),
            str(len(model.provenance)),
            next(iter(model.provenance.values()))[:16] + "…",
            f"{model.runtime_s:.3f}",
        )
        for model in models
    )
    return Section(
        ZH_SECTION_TITLES[10],
        "appendices",
        (
            PageBreak(),
            Table(
                "符号与术语速查",
                ("符号/术语", "含义"),
                (
                    ("c", "普通临界体系的中心荷"),
                    ("c_eff", "由指定无序或信息论测度的 Casimir 项定义的有效中心荷"),
                    ("L", "周期圆柱的圆周宽度"),
                    ("K, K_c, K_N", "无量纲耦合、纯净临界耦合和 Nishimori 线耦合"),
                    ("p", "Nishimori 模型的负键概率"),
                    ("phi_L", "淬火 log 配分函数密度"),
                    ("gamma_1(L)", "弱自对偶网络的 Shannon 自由能率"),
                    ("SE", "在声明重采样模型下的标准误"),
                    ("ESS", "考虑相关后的有效样本量"),
                    ("L_min", "有限尺寸拟合中保留的最小宽度"),
                    ("oracle", "不依赖主要估计路径的精确或高精度校验"),
                ),
                "同一个符号只有连同单位、符号约定与概率测度一起给出才完整。",
            ),
            Table(
                "冻结来源与运行摘要",
                ("模型", "纳入来源文件数", "首个 SHA-256 前缀", "运行时间/秒"),
                provenance_rows,
                "完整相对路径和 SHA-256 保存在来源适配器读取的 provenance 映射中；"
                "报告构建前后比较该映射以检测中途变化。",
            ),
            PageBreak(),
            Table(
                "参考文献与理论锚点",
                ("主题", "正式书目信息"),
                (
                    ("二维 Ising 精确解", "L. Onsager, Phys. Rev. 65, 117 (1944)."),
                    ("有限尺寸与共形不变性", "H. W. J. Blöte, J. L. Cardy, and M. P. Nightingale, Phys. Rev. Lett. 56, 742 (1986)."),
                    ("有限尺寸自由能", "I. Affleck, Phys. Rev. Lett. 56, 746 (1986)."),
                    ("Wolff 团簇算法", "U. Wolff, Phys. Rev. Lett. 62, 361 (1989)."),
                    ("Nishimori 线", "H. Nishimori, Prog. Theor. Phys. 66, 1169 (1981)."),
                    ("随机键 Ising 临界性", "J. L. Jacobsen and J. Cardy, Nucl. Phys. B 515, 701 (1998)."),
                    ("高斯费米子方法", "S. Bravyi, Quantum Inf. Comput. 5, 216 (2005)."),
                    ("Rao–Blackwell 定理", "C. R. Rao, Bull. Calcutta Math. Soc. 37, 81 (1945); D. Blackwell, Ann. Math. Stat. 18, 105 (1947)."),
                ),
                "论文题名、期刊、卷页和年份保持正式出版形式；正文中的物理解释使用中文。",
            ),
            Paragraph(
                "参数解释遵循“数值—物理含义—误差作用”三层结构。宽度 L 控制有限尺寸偏差；"
                "副本或流数 R 控制独立样本覆盖；burn-in 抑制初态边界效应；measurement "
                "预算控制随机精度；block 长度决定相关结构如何进入 bootstrap；稳定化间隔与"
                "不变量容差控制高斯数值漂移；delta K 平衡有限差分截断与浮点/采样噪声。"
            ),
            Paragraph(
                "本中文版基于 2026-07-29 冻结证据生成。它与英文版并存，正文、表格、图题、"
                "坐标轴、图例和注释均中文化；Rust/Python 标识符和可执行代码保持原样以便与"
                "仓库逐行对应。当前 Nishimori 宽度明确为 L = 4, 6, 8, 10, 12, 14。"
            ),
            Callout(
                "复现检查清单",
                "确认仓库提交与锁文件；验证三个来源目录及哈希；运行报告测试；以同一来源同时"
                "构建英文和中文；检查中文 PDF 每一页与 HTML 窄屏布局；记录页数、图片数和"
                "最终 SHA-256。任何缺字、截断、来源变化或必需门控失败都应阻止发布。",
                "oracle",
            ),
        ),
    )


def _model_figures(slug: str) -> Tuple[Figure, ...]:
    captions: Mapping[str, Tuple[str, str, str]]
    if slug == "clean-ising":
        captions = {
            "central_charge_comparison.png": ("独立中心荷估计", "传递矩阵与蒙特卡洛估计同精确值比较。", "一致性不替代热化和积分收敛诊断。"),
            "energy_vs_k.png": ("热力学积分曲线", "各宽度的平均能量密度随 K 变化。", "平滑性不能量化样本间相关。"),
            "fit_stability.png": ("拟合窗口稳定性", "比较 L_min=4、6、8 的中心荷。", "主窗口在看图前已经冻结。"),
            "free_energy_scaling.png": ("纯净自由能标度", "精确与蒙特卡洛自由能密度随 1/L² 的变化。", "良好拟合不能排除模拟范围外的更高阶修正。"),
            "integration_convergence.png": ("积分网格收敛", "嵌套 65/129 点 Simpson 网格比较。", "它检验当前精度下的网格分辨率，而非给出严格积分上界。"),
            "replica_diagnostics.png": ("链与副本诊断", "前后半程漂移和副本差异同门槛比较。", "有限诊断无法证明指数稀有构型全部被访问。"),
        }
    elif slug == "nishimori-ising":
        captions = {
            "central_charge_bootstrap.png": ("Nishimori bootstrap", "有效中心荷的分层配对自助分布。", "区间依赖副本—块足以代表无序波动的假设。"),
            "fit_window_stability.png": ("Nishimori 窗口稳定性", "主 L_min=4 与诊断 L_min=6 的配对比较。", "两个窗口不能穷尽所有无关算符修正。"),
            "free_energy_fit.png": ("Nishimori 自由能拟合", "淬火密度与含 L^-4 修正的有限尺寸拟合。", "小残差本身不能验证无序集合。"),
            "negative_bond_frequency.png": ("负键频率", "观测负键概率与配置 p 的比较。", "边缘频率不能检验 RNG 的全部时空相关。"),
            "nishimori_energy_identity.png": ("Nishimori 内能恒等式", "共同无序中心差分与解析恒等式比较。", "单一恒等式不能识别每一种传递核错误。"),
            "sampling_stability.png": ("无序采样稳定性", "前后半程及删一副本估计。", "对极稀有无序尾部的统计功效仍有限。"),
        }
    else:
        captions = {
            "convergence-ess.png": ("轨迹收敛", "各宽度 ESS 与一阶滞后相关。", "ESS 不诊断有限尺寸模型偏差。"),
            "finite-size-scaling.png": ("弱自对偶有限尺寸标度", "Shannon 自由能率的体项、1/L 项与修正。", "视觉尺度受体项主导，需结合残差图。"),
            "fit-stability.png": ("弱自对偶拟合稳定性", "比较最小宽度、预热、块长和删宽度变体。", "已测变体不包含所有可能修正。"),
            "residuals.png": ("弱自对偶拟合残差", "学生化残差随宽度的结构。", "无明显趋势支持但不证明展开唯一。"),
            "self-duality.png": ("电磁自对偶", "电、磁涡旋密度的配对比较。", "集合自对偶不要求单轨迹逐点相等。"),
        }
    return tuple(
        Figure(
            Path(f"generated/zh/{slug}/{filename}"),
            alt,
            caption,
            limit,
        )
        for filename, (alt, caption, limit) in captions.items()
    )


def _parameter_table(model: ModelResult) -> Table:
    translations = _parameter_copy(model.slug)
    rows = []
    for symbol, value, _, _ in model.parameters:
        meaning, role = translations[symbol]
        rows.append((symbol, value, meaning, role))
    return Table(
        f"{_model_name(model.slug)} 参数设置",
        ("参数", "数值", "物理/算法含义", "对误差或复现的作用"),
        tuple(rows),
        "数值直接来自冻结 manifest；中文解释不作为数值来源。",
    )


def _gate_table(model: ModelResult) -> Table:
    return Table(
        f"{_model_name(model.slug)} 科学门控",
        ("内部名称", "中文解释", "观测值", "必需", "状态"),
        tuple(
            (
                gate.name,
                _gate_description(gate),
                _format_value(gate.value),
                "是" if gate.required else "否",
                "通过" if gate.passed else "失败",
            )
            for gate in model.gates
        ),
        "内部名称保持与 gates.json 一致以便追踪；必需门控失败会阻止生产报告。",
    )


def _parameter_copy(slug: str) -> Mapping[str, Tuple[str, str]]:
    shared = {
        "L": ("周期圆柱宽度", "控制有限尺寸偏差"),
        "R": ("独立副本或轨迹流数", "控制独立样本波动"),
        "RNG": ("确定性伪随机数生成器", "保证可重放且流间隔离"),
    }
    specific = {
        "clean-ising": {
            "K_c": ("方格 Ising 精确临界耦合", "固定评估点"),
            "M/L": ("环面纵横比", "抑制纵向有限尺寸效应"),
            "N_K": ("热力学积分网格点数", "控制积分离散误差"),
            "N_therm": ("丢弃的 Wolff sweeps", "抑制初始化偏差"),
            "N_meas": ("每网格点测量 sweeps", "控制统计精度"),
            "N_block": ("每个存储块的 sweeps", "保留自相关结构"),
        },
        "nishimori-ising": {
            "p": ("负键概率", "定义淬火无序分布"),
            "K_N": ("Nishimori 线耦合", "锁定热权重与无序权重"),
            "N_burn": ("丢弃的传递行", "抑制初始向量偏差"),
            "N_meas": ("每副本测量行数", "控制自由能统计精度"),
            "N_block": ("每个 bootstrap 块的行数", "保留序列相关"),
            "delta K": ("中心有限差分步长", "平衡截断误差与噪声"),
        },
        "weak-self-dual": {
            "theta": ("自对偶电路角", "固定各向同性弱自对偶点"),
            "beta": ("弱测量耦合", "决定 Born 更新强度"),
            "N_burn/L": ("每单位宽度的预热层数", "抑制边界瞬态"),
            "N_meas/L": ("每单位宽度的测量层数", "控制信息率精度"),
            "N_block/L": ("每单位宽度的块层数", "支持自相关估计"),
            "N_stab": ("协方差稳定化间隔", "控制不变量漂移"),
            "epsilon_Gamma": ("高斯不变量容差", "拒绝数值无效轨迹"),
        },
    }
    return {**shared, **specific[slug]}


def _gate_description(gate: Gate) -> str:
    names = {
        "exact_accuracy": "传递矩阵估计与 c=1/2 一致",
        "mc_accuracy": "蒙特卡洛估计与 c=1/2 一致",
        "mc_interval": "蒙特卡洛 95% 区间包含 c=1/2",
        "integration": "嵌套热力学积分网格一致",
        "exact_window": "精确拟合对 L_min 稳定",
        "mc_window": "蒙特卡洛拟合对 L_min 稳定",
        "thermalization": "前后半程漂移低于阈值",
        "replicas": "独立副本差异低于阈值",
        "runtime": "运行时间低于声明上限",
    }
    if gate.name in names:
        return names[gate.name]
    tokens = gate.name.replace("_", " ")
    return f"冻结门控“{tokens}”满足其预声明数值准则"


def _model_name(slug: str) -> str:
    return {
        "clean-ising": "纯净 Ising",
        "nishimori-ising": "Nishimori 随机键 Ising",
        "weak-self-dual": "弱自对偶 Majorana 网络",
    }[slug]


def _observable(slug: str) -> str:
    return {
        "clean-ising": "热力学积分自由能密度",
        "nishimori-ising": "淬火传递 Lyapunov 密度",
        "weak-self-dual": "Born Shannon 自由能率",
    }[slug]


def _sampler(slug: str) -> str:
    return {
        "clean-ising": "热 Wolff 团簇",
        "nishimori-ising": "淬火随机键行",
        "weak-self-dual": "状态条件 Born 结果",
    }[slug]


def _oracle(slug: str) -> str:
    return {
        "clean-ising": "精确传递矩阵与 c=1/2",
        "nishimori-ising": "Nishimori 内能恒等式",
        "weak-self-dual": "稠密高斯/Born 轨迹一致性",
    }[slug]


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    return str(value)
