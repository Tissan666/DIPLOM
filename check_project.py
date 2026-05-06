"""Run the main local project checks from one command."""

from __future__ import annotations

import subprocess
from pathlib import Path

from run_dev import (
    FRONTEND_DIR,
    ROOT_DIR,
    build_env,
    ensure_frontend_dependencies,
    make_npm_command,
    resolve_node_dir,
    resolve_npm,
    resolve_python,
)

PYTHON_CHECK_TARGETS = [
    "analysis_history.py",
    "app.py",
    "check_backend.py",
    "collect_reviews.py",
    "detect.py",
    "evaluate.py",
    "train.py",
    "fake_rating_detector",
    "review_scraper_detector",
]


def run_step(name: str, command: list[str], cwd: Path, extra_path: list[str] | None = None) -> bool:
    """Run a check step and return whether it passed."""
    print(f"\n== {name} ==", flush=True)
    print(" ".join(command), flush=True)
    completed = subprocess.run(command, cwd=str(cwd), env=build_env(extra_path), check=False)
    if completed.returncode != 0:
        print(f"{name} failed with exit code {completed.returncode}.", flush=True)
        return False
    print(f"{name} passed.", flush=True)
    return True


def main() -> int:
    node_dir = resolve_node_dir()
    npm_executable = resolve_npm(node_dir)
    if not npm_executable:
        print("npm not found. Install Node.js LTS first, then run this command again.", flush=True)
        return 1

    extra_path = [str(node_dir)] if node_dir else None
    if not ensure_frontend_dependencies(npm_executable, extra_path=extra_path):
        return 1

    python_executable = resolve_python()
    checks = [
        (
            "Python syntax check",
            [python_executable, "-m", "compileall", "-q", *PYTHON_CHECK_TARGETS],
            ROOT_DIR,
        ),
        ("Frontend typecheck", make_npm_command(npm_executable, ["run", "typecheck"]), FRONTEND_DIR),
        ("Frontend build", make_npm_command(npm_executable, ["run", "build"]), FRONTEND_DIR),
    ]

    for name, command, cwd in checks:
        if not run_step(name, command, cwd, extra_path=extra_path):
            return 1

    print("\nAll project checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
