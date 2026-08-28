"""Frontend syntax gate — a broken ES module once blanked the whole SPA.

Every frontend .js file must parse as a valid ES module.  Skips gracefully
when `node` is unavailable, but fails loudly otherwise."""
import shutil
import subprocess
import tempfile
from pathlib import Path

JS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "assets" / "js"


def test_all_frontend_modules_parse():
    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("node not available")

    failures = []
    with tempfile.NamedTemporaryFile(suffix=".mjs", delete=False) as tmp:
        tmp_path = tmp.name
    for f in sorted(JS_DIR.rglob("*.js")):
        Path(tmp_path).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        r = subprocess.run([node, "--check", tmp_path], capture_output=True)
        if r.returncode != 0:
            failures.append(f"{f.name}: {r.stderr.decode()[:200]}")
    assert not failures, "\n".join(failures)
