import os
import subprocess
import sys


def test_cli_run_mvp_dry_run(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["DRY_RUN"] = "true"
    env["LOCAL_FIRESTORE_PATH"] = str(tmp_path / "firestore.json")

    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "run-mvp", "--limit", "2"],
        capture_output=True,
        text=True,
        env=env,
        cwd="c:/work/sns-af",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "command_completed command=run-mvp" in result.stderr or "command_completed command=run-mvp" in result.stdout
