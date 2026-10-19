"""Smoke test the built wheel from a clean virtual environment."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv


ROOT = Path(__file__).resolve().parents[1]


class WheelInstallTest(unittest.TestCase):
    def test_installed_wheel_runs_devdeck_help(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            wheel_directory = temporary_path / "wheel"
            wheel_directory.mkdir()
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--wheel-dir",
                    str(wheel_directory),
                    str(ROOT),
                ],
                check=True,
            )
            wheels = list(wheel_directory.glob("avero_devdeck-*.whl"))
            if len(wheels) != 1:
                raise AssertionError(f"Expected one wheel, found {wheels}")

            environment = temporary_path / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            scripts_directory = environment / ("Scripts" if os.name == "nt" else "bin")
            python = scripts_directory / ("python.exe" if os.name == "nt" else "python")
            subprocess.run(
                [str(python), "-m", "pip", "install", str(wheels[0])],
                check=True,
            )

            executable = scripts_directory / ("devdeck.exe" if os.name == "nt" else "devdeck")
            result = subprocess.run(
                [str(executable), "--help"],
                check=True,
                capture_output=True,
                text=True,
            )
            if "usage: devdeck" not in result.stdout or "doctor" not in result.stdout:
                raise AssertionError(f"Unexpected devdeck --help output:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
