import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_e2e_server_refuses_to_start_without_explicit_test_flag():
    environment = os.environ.copy()
    environment.pop("TRAINSPOTTING_E2E_TEST", None)

    result = subprocess.run(
        [sys.executable, "-c", "import tests.e2e_app"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "requires TRAINSPOTTING_E2E_TEST=1" in result.stderr
