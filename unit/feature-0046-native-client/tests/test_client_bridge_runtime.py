"""전체 JS 모듈을 실제 DOM에서 실행한다. 위치 선택/실패/재시도/캐시/다중 토스트 계약."""
import json
import os
import subprocess
import shutil
import pytest
from pathlib import Path


def test_client_connection_flows():
    if not shutil.which("node"):
        pytest.skip("DOM verification requires Node; local Windows/DOM evidence is in TEST run 20260908-connect-discovery.")
    unit = Path(__file__).resolve().parents[1]
    run = subprocess.run(["node", str(unit / "tests/verify_client_connections_dom.mjs"), str(unit.parents[1])],
                         capture_output=True, text=True, timeout=30, env=dict(os.environ))
    if run.returncode == 2:
        pytest.skip("DOM verification requires jsdom; set DQA_JSDOM. See TEST run 20260908-connect-discovery.")
    assert run.returncode == 0, run.stdout + run.stderr
    results = json.loads(run.stdout.strip())
    assert len(results) == 12 and all(results.values()), results
