"""Immutable reader-facing locale metadata for report generation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Tuple


@dataclass(frozen=True)
class ReportLocale:
    code: str
    html_lang: str
    output_suffix: str
    plot_directory: str
    labels: Mapping[str, str]
    section_titles: Tuple[str, ...]
    pdf_subject: str
    pdf_creator: str


EN_SECTION_TITLES = (
    "Executive Summary",
    "Conceptual Foundation",
    "Shared Computational Architecture",
    "Clean Ising Model",
    "Nishimori Random-Bond Ising Model",
    "Weak Self-Dual Majorana Network",
    "Cross-Model Comparison",
    "Error and Sensitivity Analysis",
    "Implementation and Reproducibility",
    "Conclusions",
    "Appendices",
)

ZH_SECTION_TITLES = (
    "执行摘要",
    "概念基础",
    "共享计算架构",
    "纯净 Ising 模型",
    "Nishimori 随机键 Ising 模型",
    "弱自对偶 Majorana 网络",
    "跨模型比较",
    "误差与敏感性分析",
    "实现与可复现性",
    "结论",
    "附录",
)


EN_LOCALE = ReportLocale(
    code="en",
    html_lang="en",
    output_suffix="",
    plot_directory="en",
    labels=MappingProxyType(
        {
            "technical_report": "Technical Report",
            "abstract": "Abstract",
            "contents": "Contents",
            "contents_aria": "Report contents",
            "section": "Section",
            "figure": "Figure",
            "table": "Table",
            "interpretation_limit": "Interpretation limit",
            "clean_result": "Clean Ising MC",
            "nishimori_result": "Nishimori",
            "weak_result": "Weak self-dual",
            "footer_team": "Team 卧龙凤雏",
            "footer_date": "Frozen-data report · 29 July 2026",
            "header_title": "THREE ROUTES TO CENTRAL CHARGE",
            "header_team": "TEAM WOLONG-FENGCHU",
        }
    ),
    section_titles=EN_SECTION_TITLES,
    pdf_subject="Integrated central-charge verification report",
    pdf_creator="Quantum Harness integrated report generator",
)

ZH_LOCALE = ReportLocale(
    code="zh",
    html_lang="zh-CN",
    output_suffix="-zh",
    plot_directory="zh",
    labels=MappingProxyType(
        {
            "technical_report": "技术报告",
            "abstract": "摘要",
            "contents": "目录",
            "contents_aria": "报告目录",
            "section": "第",
            "figure": "图",
            "table": "表",
            "interpretation_limit": "解读边界",
            "clean_result": "纯净 Ising 蒙特卡洛",
            "nishimori_result": "Nishimori",
            "weak_result": "弱自对偶",
            "footer_team": "卧龙凤雏团队",
            "footer_date": "冻结数据报告 · 2026 年 7 月 29 日",
            "header_title": "中心荷的三条验证路径",
            "header_team": "卧龙凤雏团队",
        }
    ),
    section_titles=ZH_SECTION_TITLES,
    pdf_subject="三模型中心荷验证综合技术报告",
    pdf_creator="Quantum Harness 中文综合报告生成器",
)


def get_locale(language: str) -> ReportLocale:
    key = language.strip().lower()
    try:
        return {"en": EN_LOCALE, "zh": ZH_LOCALE}[key]
    except KeyError as error:
        raise ValueError(f"unsupported report language: {language}") from error
