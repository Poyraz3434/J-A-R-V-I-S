import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ATLAS_DIR = ROOT / "atlas"
CLI_PATH = ATLAS_DIR / "dist" / "cli.js"
NODE_BIN = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"


def run_atlas_check() -> dict:
    """Python bridge: runs the compiled Atlas TypeScript service and returns JSON."""
    if not CLI_PATH.exists():
        raise FileNotFoundError(
            "Atlas build not found. Run: cd atlas && npm install && npm run build"
        )

    env = os.environ.copy()
    env.setdefault("NODE_ENV", "production")
    result = subprocess.run(
        [NODE_BIN, str(CLI_PATH)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        payload = {"ok": False, "error": stderr or stdout or "Atlas execution failed."}
        return payload

    matches = list(re.finditer(r"\{.*?\}", stdout, re.DOTALL))
    if not matches:
        return {"ok": False, "raw_output": stdout, "stderr": stderr}

    candidate = matches[-1].group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {"ok": False, "raw_output": stdout, "stderr": stderr}


if __name__ == "__main__":
    print(json.dumps(run_atlas_check(), ensure_ascii=False, indent=2))
