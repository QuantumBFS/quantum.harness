import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_plot_local_uncertainties_writes_png_and_pdf(tmp_path: Path) -> None:
    analysis = {
        "mps": {
            "comparisons": [
                {
                    "gamma": 1.56,
                    "gap": {"relative": 1e-7},
                    "r_xi": {"absolute": 2e-8},
                },
                {
                    "gamma": 1.565,
                    "gap": {"relative": 2e-7},
                    "r_xi": {"absolute": 3e-8},
                },
            ]
        },
        "mpo": {
            "crossing": {
                "status": "complete",
                "K24": {"gamma": 1.5633},
                "K32": {"gamma": 1.5632},
            },
            "comparisons": [
                {
                    "length": 32,
                    "gamma": 1.56,
                    "gap": {"relative": 1e-6},
                    "r_xi": {"absolute": -2e-7},
                },
                {
                    "length": 64,
                    "gamma": 1.56,
                    "gap": {"relative": 3e-6},
                    "r_xi": {"absolute": -5e-7},
                },
            ],
        },
    }
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis))
    environment = dict(os.environ)
    environment["MPLCONFIGDIR"] = str(tmp_path / "mpl")

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "plot_local_uncertainties.py"),
            "--analysis",
            str(analysis_path),
            "--output-prefix",
            str(tmp_path / "local-uncertainties"),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "local-uncertainties.png").stat().st_size > 0
    assert (tmp_path / "local-uncertainties.pdf").stat().st_size > 0
