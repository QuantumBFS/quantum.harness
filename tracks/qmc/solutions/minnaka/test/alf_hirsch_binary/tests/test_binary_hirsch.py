#!/usr/bin/env python3
"""Regression tests for the binary Hirsch field in ALF 2.4."""

from __future__ import annotations

import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Optional
import unittest


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
BRIDGE_SCRIPTS = PROJECT_ROOT.parent / "pqmc_cp_bridge" / "scripts"
sys.path.insert(0, str(BRIDGE_SCRIPTS))
from path_archive import ArchiveReader  # noqa: E402

ALF_ROOT = PROJECT_ROOT / "ALF"
DEFAULT_EXECUTABLE = ALF_ROOT / "Prog" / "ALF.out"
START_PARAMETERS = (
    ALF_ROOT / "Scripts_and_Parameters_files" / "Start" / "parameters"
)
START_SEEDS = ALF_ROOT / "Scripts_and_Parameters_files" / "Start" / "seeds"

DT = 0.05
U = 4.0


def replace_assignment(text: str, name: str, value: str, count: int = 1) -> str:
    pattern = re.compile(
        rf"(?m)^(\s*{re.escape(name)}\s*=\s*)[^!\n]*(.*)$",
        re.IGNORECASE,
    )
    updated, replacements = pattern.subn(
        lambda match: f"{match.group(1)}{value}{match.group(2)}",
        text,
        count=count,
    )
    if replacements != count:
        raise AssertionError(
            f"expected {count} assignment(s) for {name}, found {replacements}"
        )
    return updated


def make_smoke_parameters(
    hirsch_binary: Optional[bool] = True,
    ham_u: float = U,
    trial_boundary_mode: Optional[int] = None,
    export_trial_orbitals: Optional[bool] = None,
    archive_paths: bool = False,
    archive_ensemble: int = 1,
    theta: float = 10.0,
    beta: float = 1.0,
) -> str:
    text = START_PARAMETERS.read_text(encoding="utf-8")
    text = replace_assignment(text, "ham_name", '"Hubbard_Plain_Vanilla"')
    text = replace_assignment(text, "L1", "4", count=1)
    text = replace_assignment(text, "L2", "4", count=1)
    text = replace_assignment(text, "NSweep", "2")
    text = replace_assignment(text, "NBin", "1", count=1)
    text = replace_assignment(text, "Ltau", "0", count=1)
    if archive_paths:
        qmc_start = text.index("&VAR_QMC")
        qmc_end_match = re.search(r"(?m)^/\s*$", text[qmc_start:])
        if qmc_end_match is None:
            raise AssertionError("unterminated VAR_QMC group")
        qmc_end = qmc_start + qmc_end_match.start()
        qmc_group = text[qmc_start:qmc_end]
        qmc_group += "Archive_paths = .T.\n"
        qmc_group += "Archive_stride = 1\n"
        qmc_group += "Archive_after_sweep = 0\n"
        qmc_group += f"Archive_ensemble = {archive_ensemble}\n"
        qmc_group += "Archive_chain_id = 0\n"
        qmc_group += "Archive_file = 'paths.qhpath'\n"
        qmc_group += f"Archive_selected_hash = '{'0' * 64}'\n"
        qmc_group += f"Archive_trial_hash = '{'1' * 64}'\n"
        text = text[:qmc_start] + qmc_group + text[qmc_end:]

    group_start = text.index("&VAR_Hubbard_Plain_Vanilla")
    group_end_match = re.search(r"(?m)^/\s*$", text[group_start:])
    if group_end_match is None:
        raise AssertionError("unterminated VAR_Hubbard_Plain_Vanilla group")
    group_end = group_start + group_end_match.start()
    group = text[group_start:group_end]
    group = replace_assignment(group, "ham_T", "1.d0")
    group = replace_assignment(group, "ham_chem", "0.d0")
    group = replace_assignment(group, "ham_U", f"{ham_u:.16g}d0")
    group = replace_assignment(group, "Dtau", "0.05d0")
    group = replace_assignment(group, "Beta", f"{beta:.16g}d0")
    group = replace_assignment(group, "Projector", ".T.")
    group = replace_assignment(group, "Theta", f"{theta:.16g}d0")
    group = replace_assignment(group, "Symm", ".T.")
    if hirsch_binary is not None:
        fortran_logical = ".T." if hirsch_binary else ".F."
        group += f"Hirsch_binary = {fortran_logical}\n"
    if trial_boundary_mode is not None:
        group += f"Trial_boundary_mode = {trial_boundary_mode}\n"
    if export_trial_orbitals is not None:
        logical = ".T." if export_trial_orbitals else ".F."
        group += f"Export_trial_orbitals = {logical}\n"
    return text[:group_start] + group + text[group_end:]


def parse_scalar(info: str, label: str) -> float:
    match = re.search(
        rf"(?m)^\s*{re.escape(label)}\s*:\s*"
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?)",
        info,
    )
    if match is None:
        raise AssertionError(f"missing scalar '{label}' in info")
    return float(match.group(1).replace("D", "E").replace("d", "e"))


def run_alf(executable: Path, run_dir: Path, parameters: str) -> subprocess.CompletedProcess:
    (run_dir / "parameters").write_text(parameters, encoding="utf-8")
    shutil.copy2(START_SEEDS, run_dir / "seeds")
    env = os.environ.copy()
    env.update(
        {
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "I_MPI_PIN": "1",
            "I_MPI_PIN_DOMAIN": "core",
        }
    )
    return subprocess.run(
        ["mpirun", "-np", "1", str(executable)],
        cwd=run_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )


def read_real_matrix(path: Path) -> list[list[float]]:
    tokens = path.read_text(encoding="utf-8").split()
    rows = int(tokens[0])
    cols = int(tokens[1])
    values = [float(value) for value in tokens[2:]]
    if len(values) != rows * cols:
        raise AssertionError(f"wrong matrix value count in {path}")
    return [
        values[row * cols : (row + 1) * cols] for row in range(rows)
    ]


def orthonormality_residual(matrix: list[list[float]]) -> float:
    rows = len(matrix)
    cols = len(matrix[0])
    return max(
        abs(
            sum(matrix[row][left] * matrix[row][right] for row in range(rows))
            - (1.0 if left == right else 0.0)
        )
        for left in range(cols)
        for right in range(cols)
    )


class AnalyticalIdentityTest(unittest.TestCase):
    def test_archive_uses_eleven_chain_bits(self) -> None:
        source = (
            ALF_ROOT / "Prog" / "Path_archive_mod.F90"
        ).read_text(encoding="utf-8")
        self.assertIn("chain_id >= 2048", source)
        self.assertIn("shiftl(1_int64, 49)", source)
        self.assertIn("shiftl(int(archive_chain, int64), 49)", source)

    def test_all_four_local_occupations(self) -> None:
        lam = math.acosh(math.exp(DT * U / 2.0))
        for n_up, n_down in ((0, 0), (1, 0), (0, 1), (1, 1)):
            magnetization = n_up - n_down
            lhs = math.exp(DT * U * magnetization * magnetization / 2.0)
            rhs = 0.5 * sum(
                math.exp(s * lam * magnetization) for s in (-1.0, 1.0)
            )
            self.assertAlmostEqual(
                lhs,
                rhs,
                delta=16.0 * sys.float_info.epsilon * max(1.0, abs(lhs)),
            )


class RealExecutableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        executable = Path(
            os.environ.get("ALF_EXECUTABLE", str(DEFAULT_EXECUTABLE))
        ).resolve()
        if not executable.is_file():
            raise AssertionError(f"missing executable: {executable}")
        cls.executable = executable

    def test_binary_hirsch_real_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-hirsch-test-") as tmp:
            run_dir = Path(tmp)
            completed = run_alf(
                self.executable, run_dir, make_smoke_parameters()
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"ALF binary-Hirsch smoke failed:\n{completed.stdout}",
            )

            info = (run_dir / "info").read_text(encoding="utf-8")
            self.assertIn("HS transformation: binary Hirsch spin", info)
            lam = parse_scalar(info, "Hirsch lambda")
            self.assertAlmostEqual(
                math.cosh(lam),
                math.exp(DT * U / 2.0),
                delta=2.0e-14,
            )
            self.assertEqual(parse_scalar(info, "L1"), 4.0)
            self.assertEqual(parse_scalar(info, "L2"), 4.0)
            self.assertEqual(parse_scalar(info, "# of particles"), 8.0)
            self.assertEqual(parse_scalar(info, "Theta"), 10.0)
            self.assertEqual(parse_scalar(info, "Tau_max"), 1.0)
            self.assertEqual(parse_scalar(info, "Ham_U"), 4.0)

            dtau_match = re.search(
                r"(?m)^\s*dtau,Ltrot_eff\s*:\s*"
                r"([-+\d.EeDd]+)\s+(\d+)",
                info,
            )
            self.assertIsNotNone(dtau_match)
            assert dtau_match is not None
            self.assertAlmostEqual(
                float(dtau_match.group(1).replace("D", "E")), DT
            )
            self.assertEqual(int(dtau_match.group(2)), 420)

            confout = run_dir / "confout_0"
            values = [int(value) for value in confout.read_text().split()]
            fields = values[2:]
            self.assertTrue(fields)
            self.assertEqual(set(fields), {-1, 1})

    def test_archive_contains_each_frozen_sweep(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-archive-test-") as tmp:
            run_dir = Path(tmp)
            completed = run_alf(
                self.executable,
                run_dir,
                make_smoke_parameters(archive_paths=True),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            archive = ArchiveReader(run_dir / "paths.qhpath")
            records = list(archive.records())
            self.assertEqual(len(records), 2)
            self.assertEqual(archive.scan().complete_records, 2)
            self.assertEqual(archive.header.ltrot, 420)
            self.assertEqual(archive.header.nsites, 16)
            self.assertEqual(archive.header.ensemble_code, 1)
            self.assertEqual(
                [record.sweep_id for record in records], [1, 2]
            )
            self.assertTrue(all(record.endpoint_present for record in records))
            self.assertTrue(
                all(
                    abs(record.central_etot - record.central_ekin -
                        record.central_epot) < 1.0e-10
                    for record in records
                )
            )
            self.assertTrue(
                all(abs(record.central_npart - 16.0) < 1.0e-9
                    for record in records)
            )
            confout_values = [
                int(value)
                for value in (run_dir / "confout_0").read_text().split()
            ]
            self.assertEqual(
                records[-1].fields, tuple(confout_values[2:])
            )
            completed_again = run_alf(
                self.executable,
                run_dir,
                make_smoke_parameters(archive_paths=True),
            )
            self.assertEqual(
                completed_again.returncode, 0, completed_again.stdout
            )
            appended = list(ArchiveReader(
                run_dir / "paths.qhpath"
            ).records())
            self.assertEqual(len(appended), 4)
            self.assertEqual(
                [record.sample_id for record in appended],
                sorted({record.sample_id for record in appended}),
            )

    def test_archive_does_not_change_the_markov_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-archive-off-") as left:
            with tempfile.TemporaryDirectory(
                prefix="alf-archive-on-"
            ) as right:
                off_dir = Path(left)
                on_dir = Path(right)
                off = run_alf(
                    self.executable, off_dir, make_smoke_parameters()
                )
                on = run_alf(
                    self.executable, on_dir,
                    make_smoke_parameters(archive_paths=True),
                )
                self.assertEqual(off.returncode, 0, off.stdout)
                self.assertEqual(on.returncode, 0, on.stdout)
                self.assertEqual(
                    (off_dir / "confout_0").read_bytes(),
                    (on_dir / "confout_0").read_bytes(),
                )
                number = re.compile(
                    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
                )
                off_energy = [
                    float(value.replace("D", "E"))
                    for value in number.findall(
                        (off_dir / "Ener_scal").read_text()
                    )
                ]
                on_energy = [
                    float(value.replace("D", "E"))
                    for value in number.findall(
                        (on_dir / "Ener_scal").read_text()
                    )
                ]
                self.assertEqual(len(off_energy), len(on_energy))
                self.assertLess(
                    max(abs(a - b) for a, b in zip(off_energy, on_energy)),
                    5.0e-4,
                )

    def test_default_remains_four_valued(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-stock-test-") as tmp:
            run_dir = Path(tmp)
            completed = run_alf(
                self.executable,
                run_dir,
                make_smoke_parameters(hirsch_binary=None),
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"ALF default-mode smoke failed:\n{completed.stdout}",
            )
            info = (run_dir / "info").read_text(encoding="utf-8")
            self.assertIn(
                "HS transformation: four-valued discrete spin", info
            )
            values = [int(value) for value in (run_dir / "confout_0").read_text().split()]
            fields = values[2:]
            self.assertTrue(fields)
            self.assertTrue(set(fields).issubset({-2, -1, 1, 2}))
            self.assertTrue(any(abs(field) == 2 for field in fields))

    def test_binary_hirsch_rejects_nonrepulsive_u(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-hirsch-invalid-") as tmp:
            run_dir = Path(tmp)
            completed = run_alf(
                self.executable,
                run_dir,
                make_smoke_parameters(hirsch_binary=True, ham_u=0.0),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "Hirsch_binary requires repulsive Ham_U > 0",
                completed.stdout,
            )

    def test_export_free_trial_orbitals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-export-trial-") as tmp:
            run_dir = Path(tmp)
            completed = run_alf(
                self.executable,
                run_dir,
                make_smoke_parameters(
                    trial_boundary_mode=0,
                    export_trial_orbitals=True,
                ),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            up = read_real_matrix(run_dir / "trial_I_up.dat")
            down = read_real_matrix(run_dir / "trial_I_down.dat")
            self.assertEqual((len(up), len(up[0])), (16, 8))
            self.assertEqual((len(down), len(down[0])), (16, 8))
            self.assertLess(orthonormality_residual(up), 1.0e-12)
            self.assertLess(orthonormality_residual(down), 1.0e-12)
            self.assertLess(
                max(
                    abs(up[row][col] - down[row][col])
                    for row in range(16)
                    for col in range(8)
                ),
                1.0e-14,
            )
            site_rows = (run_dir / "site_map.dat").read_text().splitlines()
            self.assertEqual(len(site_rows), 16)
            parsed_sites = [
                tuple(int(value) for value in row.split())
                for row in site_rows
            ]
            self.assertEqual(
                {alf for alf, _cpp, _x, _y in parsed_sites},
                set(range(1, 17)),
            )
            self.assertEqual(
                {cpp for _alf, cpp, _x, _y in parsed_sites},
                set(range(16)),
            )
            for _alf, cpp, x, y in parsed_sites:
                self.assertIn(x, range(4))
                self.assertIn(y, range(4))
                self.assertEqual(cpp, y * 4 + x)

    def test_mixed_boundary_requires_trial_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-mixed-missing-") as tmp:
            completed = run_alf(
                self.executable,
                Path(tmp),
                make_smoke_parameters(trial_boundary_mode=1),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("trial_T_up.dat", completed.stdout)

    def test_mixed_boundary_uses_two_explicit_flavors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="alf-mixed-valid-") as tmp:
            root = Path(tmp)
            export_dir = root / "export"
            export_dir.mkdir()
            exported = run_alf(
                self.executable,
                export_dir,
                make_smoke_parameters(export_trial_orbitals=True),
            )
            self.assertEqual(exported.returncode, 0, exported.stdout)

            mixed_dir = root / "mixed"
            mixed_dir.mkdir()
            shutil.copy2(
                export_dir / "trial_I_up.dat",
                mixed_dir / "trial_T_up.dat",
            )
            shutil.copy2(
                export_dir / "trial_I_down.dat",
                mixed_dir / "trial_T_down.dat",
            )
            completed = run_alf(
                self.executable,
                mixed_dir,
                make_smoke_parameters(trial_boundary_mode=1),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            info = (mixed_dir / "info").read_text(encoding="utf-8")
            self.assertIn("Trial boundary mode: 1", info)
            self.assertIn("WF_R: free", info)
            self.assertIn("WF_L: UHF file", info)
            self.assertIn("Explicit flavor propagation: T", info)
            self.assertGreater(parse_scalar(info, "Spin-up overlap before normalization"), 1.0e-10)
            self.assertGreater(parse_scalar(info, "Spin-down overlap before normalization"), 1.0e-10)

    def test_mixed_boundary_rejects_bad_orbitals(self) -> None:
        cases = {
            "wrong shape": "15 8\n" + "0\n" * 120,
            "nonfinite": "16 8\nnan\n" + "0\n" * 127,
            "nonorthogonal": "16 8\n" + "1\n" * 128,
        }
        for label, content in cases.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory(
                    prefix="alf-mixed-invalid-"
                ) as tmp:
                    run_dir = Path(tmp)
                    (run_dir / "trial_T_up.dat").write_text(
                        content, encoding="utf-8"
                    )
                    (run_dir / "trial_T_down.dat").write_text(
                        content, encoding="utf-8"
                    )
                    completed = run_alf(
                        self.executable,
                        run_dir,
                        make_smoke_parameters(trial_boundary_mode=1),
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertRegex(
                        completed.stdout,
                        r"trial_T|orbital",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
