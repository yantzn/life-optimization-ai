import pytest
import subprocess
import os

def test_cli_all_dry_run():
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    result = subprocess.run(
        ["python", "-m", "src.main", "--mode", "all"],
        capture_output=True,
        text=True,
        env=env,
        cwd="c:/work/sns-af"
    )
    assert result.returncode == 0
    assert "Pipeline execution completed successfully." in result.stderr or "Pipeline execution completed successfully." in result.stdout