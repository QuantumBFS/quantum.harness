import pytest

from analysis.locale import EN_LOCALE, ZH_LOCALE, get_locale


def test_locale_lookup_is_explicit_and_complete():
    assert get_locale("en") is EN_LOCALE
    assert get_locale(" ZH ") is ZH_LOCALE
    assert ZH_LOCALE.html_lang == "zh-CN"
    assert ZH_LOCALE.output_suffix == "-zh"
    assert ZH_LOCALE.labels["contents"] == "目录"
    assert ZH_LOCALE.labels["figure"] == "图"
    assert ZH_LOCALE.labels["table"] == "表"
    assert ZH_LOCALE.labels["section"] == "第"
    assert EN_LOCALE.output_suffix == ""


def test_locale_lookup_rejects_unknown_language():
    with pytest.raises(ValueError, match="unsupported report language"):
        get_locale("fr")


def test_locales_define_all_renderer_labels():
    required = {
        "technical_report",
        "abstract",
        "contents",
        "contents_aria",
        "section",
        "figure",
        "table",
        "interpretation_limit",
        "clean_result",
        "nishimori_result",
        "weak_result",
        "footer_team",
        "footer_date",
        "header_title",
        "header_team",
    }
    assert required <= EN_LOCALE.labels.keys()
    assert required <= ZH_LOCALE.labels.keys()
