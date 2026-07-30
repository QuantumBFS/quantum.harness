"""Complete English and Simplified Chinese report localization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Locale:
    code: str
    html_lang: str
    labels: dict[str, str]


EN = Locale(
    code="en",
    html_lang="en",
    labels={
        "title": "Learning-Induced Metal-Insulator Transition",
        "subtitle": "Exploratory DIII monitored-Majorana study with an XY-line validation gate",
        "exploratory": "EXPLORATORY RESULT",
        "contents": "Contents",
        "section": "Section",
        "figure": "Figure",
        "table": "Table",
        "interpretation": "Interpretation limit",
        "team": "Team 卧龙凤雏",
        "page": "Page",
        "xy_scan": "XY phase-evidence scan",
        "diii_scan": "Generic DIII phase-evidence scan",
        "evidence": "phase-evidence score",
        "phi": "measurement azimuth φ/π",
        "entropy": "entropy S",
        "interval": "interval length ℓ",
        "coefficient": "fitted coefficient",
        "gamma": "record free-energy rate γ_1(L)",
        "width": "width L",
        "residual": "fit residual",
        "count": "bootstrap count",
        "amplitude": "Casimir amplitude c_eff α",
        "correlation": "|connected parity correlation|",
        "distance": "distance r",
        "gap": "temporal Lyapunov gap",
        "alpha": "anisotropy α",
        "mean": "mean diagnostic",
        "minutes": "minutes",
        "ess": "effective sample size",
        "data": "data",
        "fit": "fit",
    },
)

ZH = Locale(
    code="zh",
    html_lang="zh-CN",
    labels={
        "title": "学习诱导的金属—绝缘体转变",
        "subtitle": "以 XY 线验证为前置门槛的 DIII 类受监测 Majorana 探索研究",
        "exploratory": "探索性结果",
        "contents": "目录",
        "section": "第",
        "figure": "图",
        "table": "表",
        "interpretation": "解读边界",
        "team": "卧龙凤雏团队",
        "page": "第",
        "xy_scan": "XY 相证据扫描",
        "diii_scan": "一般 DIII 相证据扫描",
        "evidence": "相证据得分",
        "phi": "测量方位角 φ/π",
        "entropy": "纠缠熵 S",
        "interval": "区间长度 ℓ",
        "coefficient": "拟合系数",
        "gamma": "记录自由能率 γ_1(L)",
        "width": "宽度 L",
        "residual": "拟合残差",
        "count": "自举计数",
        "amplitude": "Casimir 振幅 c_eff α",
        "correlation": "连通宇称关联绝对值",
        "distance": "距离 r",
        "gap": "时间 Lyapunov 能隙",
        "alpha": "各向异性 α",
        "mean": "诊断均值",
        "minutes": "分钟",
        "ess": "有效样本量",
        "data": "数据",
        "fit": "拟合",
    },
)


def get_locale(language: str) -> Locale:
    try:
        return {"en": EN, "zh": ZH}[language.lower()]
    except KeyError as error:
        raise ValueError(f"unsupported report locale: {language}") from error
