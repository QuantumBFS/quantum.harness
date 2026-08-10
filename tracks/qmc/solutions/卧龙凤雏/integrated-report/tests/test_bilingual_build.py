from build_report import build, build_all


def test_chinese_build_writes_only_chinese_outputs(repo_root):
    english_html = repo_root / "output/html/three-model-central-charge-report.html"
    english_pdf = repo_root / "output/pdf/three-model-central-charge-report.pdf"
    before = (english_html.read_bytes(), english_pdf.read_bytes())

    result = build(repo_root, language="zh")

    assert result.language == "zh"
    assert result.html.name == "three-model-central-charge-report-zh.html"
    assert result.pdf.name == "three-model-central-charge-report-zh.pdf"
    assert result.html_verification.passed
    assert result.pdf_verification.passed
    assert (english_html.read_bytes(), english_pdf.read_bytes()) == before


def test_all_build_returns_english_then_chinese(repo_root):
    results = build_all(repo_root)

    assert [item.language for item in results] == ["en", "zh"]
    assert all(item.html.exists() and item.pdf.exists() for item in results)
    assert all(item.html_verification.passed for item in results)
    assert all(item.pdf_verification.passed for item in results)
