"""One shared fact model for the English and Chinese technical reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .locale import get_locale
from .plots import PLOT_NAMES, plot_data_hashes


@dataclass(frozen=True)
class Paragraph:
    text: str


@dataclass(frozen=True)
class Equation:
    expression: str
    explanation: str


@dataclass(frozen=True)
class Figure:
    source: str
    caption: str
    inference_limit: str


@dataclass(frozen=True)
class Table:
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    note: str


@dataclass(frozen=True)
class Callout:
    title: str
    text: str
    tone: str = "principle"


Block = Paragraph | Equation | Figure | Table | Callout


@dataclass(frozen=True)
class Section:
    slug: str
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class ReportDocument:
    language: str
    title: str
    subtitle: str
    abstract: str
    author: str
    status: str
    exploratory_label: str
    sections: tuple[Section, ...]
    numeric_facts: dict[str, Any]
    figure_data_hashes: tuple[str, ...]


def build_report(summary: dict, locale: str) -> ReportDocument:
    language = get_locale(locale)
    text = _english(summary) if locale == "en" else _chinese(summary)
    facts = _numeric_facts(summary)
    figures = tuple(
        Figure(
            source=f"plots/{locale}/{name}",
            caption=text["figure_captions"][index],
            inference_limit=text["figure_limits"][index],
        )
        for index, name in enumerate(PLOT_NAMES)
    )
    sections = (
        Section("summary", text["titles"][0], (Callout(text["status"], text["summary"], "result"), figures[0])),
        Section("concepts", text["titles"][1], (Paragraph(text["concepts"]), Equation("σ(θ,φ)=sinθ cosφ X + sinθ sinφ Y + cosθ Z", text["measurement_axis"]))),
        Section("mapping", text["titles"][2], (Paragraph(text["mapping"]), Equation("J(θ)=atanh(cosθ)", text["coupling"]), figures[2])),
        Section("symmetry", text["titles"][3], (Paragraph(text["symmetry"]), figures[1])),
        Section("gaussian", text["titles"][4], (Paragraph(text["gaussian"]), Equation("Γ′ = R Γ Rᵀ", text["rotation"]))),
        Section("born", text["titles"][5], (Paragraph(text["born"]), figures[8])),
        Section("parameters", text["titles"][6], (_parameter_table(summary, locale), figures[9])),
        Section("oracles", text["titles"][7], (Paragraph(text["oracles"]), _oracle_table(summary, locale))),
        Section("xy", text["titles"][8], (Paragraph(text["xy"]), figures[0])),
        Section("diii", text["titles"][9], (Paragraph(text["diii"]), figures[1], figures[3])),
        Section("casimir", text["titles"][10], (Equation("γ₁(L)=f∞L−π(c_eff α)/(6L)+a/L³", text["casimir"]), figures[4], figures[5])),
        Section("anisotropy", text["titles"][11], (Paragraph(text["anisotropy"]), Equation("α=gL/(2πΔ)", text["alpha_equation"]), figures[6], figures[7])),
        Section("errors", text["titles"][12], (Paragraph(text["errors"]), Callout(text["claim_title"], text["claim"], "warning"))),
        Section("reproducibility", text["titles"][13], (Paragraph(text["reproducibility"]), _inventory_table(summary, locale))),
    )
    return ReportDocument(
        language=locale,
        title=language.labels["title"],
        subtitle=language.labels["subtitle"],
        abstract=text["abstract"],
        author=language.labels["team"],
        status=summary["status"],
        exploratory_label=language.labels["exploratory"],
        sections=sections,
        numeric_facts=facts,
        figure_data_hashes=plot_data_hashes(summary),
    )


def _numeric_facts(summary: dict) -> dict[str, Any]:
    return {
        "status": summary["status"],
        "xy_bracket": summary.get("xy", {}).get("bracket"),
        "diii_bracket": summary.get("diii", {}).get("bracket"),
        "casimir_amplitude": summary.get("casimir", {}).get("amplitude"),
        "casimir_interval": summary.get("casimir", {}).get("amplitude_interval"),
        "delta": summary.get("anisotropy", {}).get("delta"),
        "alpha": summary.get("anisotropy", {}).get("alpha"),
        "alpha_interval": summary.get("anisotropy", {}).get("alpha_interval"),
        "alpha_stable": summary.get("anisotropy", {}).get("alpha_stable"),
        "central_charge_published": summary.get("central_charge", {}).get("published"),
        "central_charge": summary.get("central_charge", {}).get("value"),
        "central_charge_interval": summary.get("central_charge", {}).get("interval"),
        "elapsed_seconds": summary.get("run", {}).get("elapsed_seconds"),
        "effective_sample_size": summary.get("bootstrap", {}).get("effective_sample_size"),
        "negative_control_z": summary.get("negative_control", {}).get("z_score"),
    }


def _parameter_table(summary: dict, locale: str) -> Table:
    run = summary.get("run", {})
    if locale == "zh":
        columns = ("参数", "设定", "意义")
        rows = (
            ("宽度 L", ", ".join(map(str, run.get("widths", []))), "有限尺寸标度"),
            ("独立流", str(run.get("streams", "")), "流级不确定度"),
            ("普通停止", str(run.get("ordinary_stop_seconds", "")), "停止启动新任务"),
            ("硬停止", str(run.get("hard_stop_seconds", "")), "仅保留原子化收尾"),
        )
        note = "所有时间均从生产模拟与分析流水线开始计时。"
    else:
        columns = ("Parameter", "Setting", "Meaning")
        rows = (
            ("Widths L", ", ".join(map(str, run.get("widths", []))), "finite-size scaling"),
            ("Independent streams", str(run.get("streams", "")), "stream-level uncertainty"),
            ("Ordinary stop", str(run.get("ordinary_stop_seconds", "")), "stop launching new work"),
            ("Hard stop", str(run.get("hard_stop_seconds", "")), "atomic finalization only"),
        )
        note = "Times are measured from the production simulation and analysis pipeline."
    return Table("参数设置" if locale == "zh" else "Parameter settings", columns, rows, note)


def _oracle_table(summary: dict, locale: str) -> Table:
    data = summary.get("oracles", {})
    columns = ("检验", "最大误差") if locale == "zh" else ("Oracle", "maximum error")
    rows = (
        ("稠密 Born 概率" if locale == "zh" else "dense Born probability", _scientific(data.get("dense_probability_error"))),
        ("稠密协方差" if locale == "zh" else "dense covariance", _scientific(data.get("dense_covariance_error"))),
        ("弱自对偶极限" if locale == "zh" else "weak self-dual limit", _scientific(data.get("weak_limit_error"))),
    )
    return Table("科学预言机" if locale == "zh" else "Scientific oracles", columns, rows, "通过门槛后方可运行生产扫描。" if locale == "zh" else "Production is gated on these checks.")


def _inventory_table(summary: dict, locale: str) -> Table:
    hashes = summary.get("hashes", {})
    columns = ("对象", "SHA-256") if locale == "zh" else ("Artifact", "SHA-256")
    rows = tuple((name, value) for name, value in sorted(hashes.items()))
    return Table("代码与数据清单" if locale == "zh" else "Code and data inventory", columns, rows, "哈希绑定冻结输入。" if locale == "zh" else "Hashes bind the report to frozen inputs.")


def _scientific(value: object) -> str:
    return "not recorded" if value is None else f"{float(value):.3e}"


def _english(summary: dict) -> dict[str, Any]:
    amplitude = summary.get("casimir", {}).get("amplitude")
    alpha = summary.get("anisotropy", {}).get("alpha")
    return {
        "titles": (
            "Executive result and scope",
            "Basic concepts: monitoring and phases",
            "Surface-code mapping and effective couplings",
            "Why generic DIII differs from the XY class-D line",
            "Gaussian covariance implementation",
            "Conditional Born sampling and the IID negative control",
            "Parameters, runtime budget, and estimator meanings",
            "Independent mathematical and physical oracles",
            "Reproduction of the known XY transition",
            "Exploratory generic-DIII phase evidence",
            "Casimir amplitude and finite-size correction",
            "Spatial-temporal anisotropy calibration",
            "Uncertainty, sensitivity, and claim boundary",
            "Reproducibility and code/data inventory",
        ),
        "status": "Exploratory status",
        "summary": f"The frozen status is {summary['status']}. The directly fitted universal candidate is c_eff α={amplitude}; α={alpha} is reported only with its window-stability gate.",
        "concepts": "Repeated quantum measurements can either preserve extended Majorana correlations or localize them. The metal-insulator distinction is diagnosed from size trends, entanglement-arc model weights, correlations, and record free energy rather than from one smooth curve.",
        "measurement_axis": "The two angles define the physical single-qubit measurement axis.",
        "mapping": "The surface-code Born tensor network maps to alternating Gaussian measurements and rotations. The real coupling controls information gain; the complex phase controls norm-preserving Majorana rotation.",
        "coupling": "This converts the polar measurement angle into a real monitoring strength.",
        "symmetry": "The XY line has a special class-D block decomposition. Moving to θ=0.45π with nonzero azimuth removes that decomposition and realizes the generic DIII cut targeted by the open challenge.",
        "gaussian": "Rust evolves a real antisymmetric 2L×2L covariance matrix. Rational measurement updates and orthogonal rotations preserve purity, while entropy follows from duplicated singular values of restricted covariance matrices.",
        "rotation": "Every unitary Majorana gate acts by congruence on the covariance matrix.",
        "born": "Xoshiro256++ draws conditional Born outcomes. The Rao-Blackwellized binary entropy is accumulated before each draw. Unbiased IID signs are a deliberately nonphysical diagnostic and never enter physical summaries.",
        "oracles": "Dense Hilbert-space enumeration at L=2 checks joint probabilities, covariances, and entropy independently. Analytic angle limits, the frozen weak-self-dual kernel, exact-Y swaps, and class-D decomposition residuals guard sign and factor conventions.",
        "xy": "The XY scan is a validation gate: its finite-size bracket must overlap the declared reference window before any generic-DIII claim is considered.",
        "diii": "The generic scan compares area, logarithmic, squared-logarithmic, and Page-augmented arc models across widths. A transition bracket requires persistent opposite phase evidence on adjacent angles.",
        "casimir": "The coefficient of 1/L is the directly observed product c_eff α; the L^-3 term absorbs leading finite-size drift.",
        "anisotropy": "Spatial parity correlations determine Δ, while the leading temporal Lyapunov gap determines α. Window changes and block deletions must agree before dividing the Casimir amplitude by α.",
        "alpha_equation": "This calibration makes the spacetime conversion explicit instead of assuming isotropy.",
        "errors": "Uncertainty is hierarchical: streams are resampled first and complete blocks second. Sensitivity checks change minimum width, corrections, phase brackets, correlation windows, and Lyapunov block deletions.",
        "claim_title": "Claim boundary",
        "claim": "This is an exploratory finite-size result, not a final universal constant. If α is unstable, the report publishes c_eff α only and suppresses standalone c_eff.",
        "reproducibility": "All physics sampling is implemented in Rust; Python only validates frozen artifacts, fits models, bootstraps, plots, and renders reports. Stream JSON, block CSV, refinement requests, and reports are bound by SHA-256.",
        "abstract": "We reproduce the known XY-line learning transition, then test a generic symmetry-class-DIII measurement cut with Born-sampled Gaussian Majorana trajectories. The report explains the mapping, algorithms, parameters, finite-size analysis, anisotropy calibration, uncertainty, and strict exploratory claim gates.",
        "figure_captions": (
            "XY validation scan and declared reference window.",
            "Generic DIII coarse evidence and selected refinement bracket.",
            "Representative entanglement arcs across angles and widths.",
            "Arc-model coefficients used to distinguish area, logarithmic, and squared-logarithmic behavior.",
            "Casimir finite-size fit with residuals.",
            "Hierarchical bootstrap distribution of c_eff α.",
            "Spatial parity decay and temporal Lyapunov gaps.",
            "Anisotropy sensitivity to analysis windows.",
            "Born sampling compared with the nonphysical IID-sign control.",
            "Runtime allocation and effective sample size.",
        ),
        "figure_limits": tuple("Finite widths and declared fit windows limit interpretation." for _ in range(10)),
    }


def _chinese(summary: dict) -> dict[str, Any]:
    amplitude = summary.get("casimir", {}).get("amplitude")
    alpha = summary.get("anisotropy", {}).get("alpha")
    return {
        "titles": (
            "核心结果与适用范围",
            "基础概念：监测、金属相与绝缘相",
            "表面码映射与有效耦合",
            "一般 DIII 与 XY 线上 D 类的区别",
            "高斯协方差实现原理",
            "条件 Born 采样与 IID 负对照",
            "参数、运行预算与估计量含义",
            "独立数学与物理预言机",
            "已知 XY 转变的复现",
            "一般 DIII 相证据的探索分析",
            "Casimir 振幅与有限尺寸修正",
            "空间—时间各向异性标定",
            "误差、敏感性与结论边界",
            "可复现性及代码数据清单",
        ),
        "status": "探索性状态",
        "summary": f"冻结结果状态为 {summary['status']}。直接拟合的普适候选量是 c_eff α={amplitude}；α={alpha} 只有通过窗口稳定性门槛后才用于推导中心荷。",
        "concepts": "重复量子测量既可能保留延展的 Majorana 关联，也可能使其局域化。金属—绝缘体判别同时依赖尺寸趋势、纠缠弧模型权重、空间关联和记录自由能，不能由一条平滑曲线单独决定。",
        "measurement_axis": "两个角度共同确定物理单比特测量轴。",
        "mapping": "表面码 Born 张量网络可映射成交替的高斯测量和旋转。实耦合控制信息获取强度，复相位控制保持范数的 Majorana 旋转。",
        "coupling": "该式把测量极角转换为实数监测强度。",
        "symmetry": "XY 线具有特殊的 D 类分块结构。取 θ=0.45π 且方位角非零会破除该分块，从而进入开放挑战所要求的一般 DIII 截面。",
        "gaussian": "Rust 演化实反对称的 2L×2L 协方差矩阵。分式测量更新与正交旋转保持纯度；子区协方差奇异值成对重复，据此计算纠缠熵。",
        "rotation": "每个幺正 Majorana 门都以合同变换作用于协方差矩阵。",
        "born": "Xoshiro256++ 按条件 Born 概率抽样。在抽样前累计二元熵，从而得到 Rao—Blackwell 化估计。无偏 IID 符号仅作为非物理诊断，绝不进入物理汇总。",
        "oracles": "在 L=2 上独立枚举稠密 Hilbert 空间，核对联合概率、协方差与纠缠熵。解析角度极限、冻结的弱自对偶内核、精确 Y 点交换以及 D 类分块残差共同约束符号和系数。",
        "xy": "XY 扫描是前置验证门槛：只有有限尺寸转变区间与预先声明的参考窗口重叠，才讨论一般 DIII 结论。",
        "diii": "一般截面在多个宽度上比较面积律、对数、平方对数和含 Page 项的纠缠弧模型。相邻角度必须持续显示相反相证据，才能形成转变括区。",
        "casimir": "1/L 项的系数直接给出乘积 c_eff α；L^-3 项吸收领先有限尺寸漂移。",
        "anisotropy": "空间宇称关联给出 Δ，领先时间 Lyapunov 能隙给出 α。只有空间窗口与时间块删除检验相互一致，才允许用 α 除 Casimir 振幅。",
        "alpha_equation": "该标定显式处理时空尺度换算，不预设各向同性。",
        "errors": "不确定度采用分层重采样：先重采样独立流，再重采样完整块。敏感性分析改变最小宽度、修正项、相括区、关联窗口及 Lyapunov 块删除方案。",
        "claim_title": "结论边界",
        "claim": "这是探索性的有限尺寸结果，并非最终普适常数。若 α 不稳定，报告只发布 c_eff α，并禁止给出独立 c_eff。",
        "reproducibility": "所有物理采样均由 Rust 实现；Python 只负责冻结数据验证、拟合、自举、绘图和报告渲染。流 JSON、块 CSV、细化请求与报告均由 SHA-256 绑定。",
        "abstract": "本研究先复现已知 XY 线学习诱导转变，再用条件 Born 采样的高斯 Majorana 轨迹检验一般 DIII 对称类测量截面。报告系统说明映射、算法、参数、有限尺寸分析、各向异性标定、误差来源和严格的探索性结论门槛。",
        "figure_captions": (
            "XY 验证扫描与预先声明的参考窗口。",
            "一般 DIII 粗扫描证据与选定细化括区。",
            "不同角度和宽度下的代表性纠缠弧。",
            "区分面积律、对数与平方对数行为的弧模型系数。",
            "含残差的 Casimir 有限尺寸拟合。",
            "c_eff α 的分层自举分布。",
            "空间宇称衰减与时间 Lyapunov 能隙。",
            "各向异性对分析窗口的敏感性。",
            "Born 采样与非物理 IID 符号负对照。",
            "运行时间分配与有效样本量。",
        ),
        "figure_limits": tuple("解读受有限宽度和预先声明拟合窗口约束。" for _ in range(10)),
    }
