"""Run the repository's standard tests, syntax checks, and GUI smoke test."""
from __future__ import annotations

import os
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.packaging_validation import validate_frozen_layout, validate_source_package


def check_syntax() -> int:
    source_roots = (ROOT, ROOT / "services", ROOT / "tests", ROOT / "plugins", ROOT / "atlas")
    files = set(ROOT.glob("*.py"))
    for source_root in source_roots[1:]:
        if source_root.is_dir():
            files.update(source_root.rglob("*.py"))
    for source_file in sorted(files):
        if "__pycache__" in source_file.parts:
            continue
        compile(source_file.read_text(encoding="utf-8-sig"), str(source_file), "exec")
    return len(files)


def run(
    label: str,
    args: list[str],
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> None:
    print(f"\n== {label} ==", flush=True)
    subprocess.run(args, cwd=ROOT, env=env, check=True, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package-dir",
        type=Path,
        help="PyInstaller onedir çıktısını da çalıştırıp --self-test ile doğrula.",
    )
    args = parser.parse_args()
    package_errors = validate_source_package(ROOT)
    if package_errors:
        raise SystemExit("\n".join(package_errors))
    print("PyInstaller source manifest OK", flush=True)
    checked = check_syntax()
    print(f"Python syntax OK ({checked} project files)", flush=True)
    run(
        "Unit tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
    )
    smoke_env = os.environ.copy()
    smoke_env["QT_QPA_PLATFORM"] = "offscreen"
    run("GUI smoke test", [sys.executable, "tests/_smoke.py"], smoke_env)
    package_dir = args.package_dir or (ROOT / "dist" / "JARVIS")
    if package_dir.exists():
        package_errors = validate_frozen_layout(package_dir)
        if package_errors:
            raise SystemExit("\n".join(package_errors))
        print("Existing frozen package layout OK", flush=True)
        if args.package_dir:
            executable = package_dir / "JARVIS.exe"
            try:
                run(
                    "Frozen application self-test",
                    [str(executable), "--self-test"],
                    {**os.environ, "JARVIS_SHARE_CONTEXT": ""},
                    timeout=30,
                )
            except OSError as exc:
                if getattr(exc, "winerror", None) != 4551:
                    raise
                print(
                    "Frozen runtime self-test SKIPPED: Windows App Control "
                    "blocked this locally built executable (WinError 4551).",
                    flush=True,
                )
    print("\nAll validation checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
