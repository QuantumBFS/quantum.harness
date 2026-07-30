from decimal import Decimal
from pathlib import Path

from xxzcert.schema import LevelCertificate
from xxzcert.verify import verify_level


def test_every_published_level_verifies():
    paths = sorted(Path("outputs/final").glob("**/*.json"))
    assert paths
    for path in paths:
        report = verify_level(path)
        assert report.ok, (path, report.errors)


def test_every_benchmark_delta_is_published():
    expected = {
        Decimal("-2"),
        Decimal("-1"),
        Decimal("-0.5"),
        Decimal("0"),
        Decimal("0.5"),
        Decimal("0.9"),
        Decimal("1"),
        Decimal("1.1"),
        Decimal("2"),
    }
    actual = {
        LevelCertificate.read(path).delta
        for path in Path("outputs/final").glob("**/*.json")
    }
    assert actual == expected


def test_published_sequences_use_monotone_envelopes():
    grouped: dict[Decimal, list[LevelCertificate]] = {}
    for path in Path("outputs/final").glob("grid/**/*.json"):
        certificate = LevelCertificate.read(path)
        grouped.setdefault(certificate.delta, []).append(certificate)
    for certificates in grouped.values():
        ordered = sorted(certificates, key=lambda item: item.level)
        lowers = [item.certified_lower for item in ordered]
        uppers = [item.certified_upper for item in ordered]
        assert lowers == sorted(lowers)
        assert uppers == sorted(uppers, reverse=True)
