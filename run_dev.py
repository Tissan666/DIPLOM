"""Run the Flask backend and React frontend together in one terminal."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
NODEJS_DIR_CANDIDATES = [
    Path(r"C:\Program Files\nodejs"),
    Path(r"C:\Program Files (x86)\nodejs"),
]


def resolve_python() -> str:
    """Prefer the local virtual environment when it exists."""
    if os.name == "nt":
        venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = ROOT_DIR / ".venv" / "bin" / "python"

    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def resolve_node_dir() -> Path | None:
    """Find a usable Node.js installation directory."""
    if os.name == "nt":
        for candidate in NODEJS_DIR_CANDIDATES:
            if (candidate / "node.exe").exists() and (candidate / "npm.cmd").exists():
                return candidate
        return None

    resolved = shutil.which("node")
    if not resolved:
        return None
    return Path(resolved).resolve().parent


def resolve_npm(node_dir: Path | None) -> str | None:
    """Return the first available npm executable."""
    candidates = ["npm.cmd", "npm"] if os.name == "nt" else ["npm"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    if node_dir:
        fallback = node_dir / ("npm.cmd" if os.name == "nt" else "npm")
        if fallback.exists():
            return str(fallback)
    return None


def build_env(extra_path: list[str] | None = None) -> dict[str, str]:
    """Build a child-process environment with optional PATH entries."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if extra_path:
        env["PATH"] = os.pathsep.join(extra_path + [env.get("PATH", "")])
    return env


def make_subprocess_command(executable: str, args: list[str]) -> list[str]:
    """Wrap Windows batch shims so Python can launch them reliably."""
    command = [executable, *args]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return ["cmd.exe", "/d", "/s", "/c", subprocess.list2cmdline(command)]
    return command


def make_npm_command(npm_executable: str, args: list[str]) -> list[str]:
    """Build an npm command, preferring node + npm-cli.js on Windows."""
    if os.name == "nt":
        npm_dir = Path(npm_executable).resolve().parent
        node_executable = npm_dir / "node.exe"
        npm_cli = npm_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if node_executable.exists() and npm_cli.exists():
            return [str(node_executable), str(npm_cli), *args]
    return make_subprocess_command(npm_executable, args)


def frontend_dependencies_need_install(package_json: Path) -> bool:
    """Return True when frontend dependencies are missing or older than manifests."""
    node_modules = FRONTEND_DIR / "node_modules"
    vite_executable = node_modules / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if not node_modules.exists() or not vite_executable.exists():
        return True

    package_lock = FRONTEND_DIR / "package-lock.json"
    npm_marker = node_modules / ".package-lock.json"
    install_timestamp = (npm_marker if npm_marker.exists() else node_modules).stat().st_mtime
    manifest_timestamps = [package_json.stat().st_mtime]
    if package_lock.exists():
        manifest_timestamps.append(package_lock.stat().st_mtime)

    return max(manifest_timestamps) > install_timestamp


def ensure_frontend_dependencies(npm_executable: str, extra_path: list[str] | None = None) -> bool:
    """Install frontend dependencies only when they are missing or stale."""
    package_json = FRONTEND_DIR / "package.json"
    if not frontend_dependencies_need_install(package_json):
        return True

    print("Frontend dependencies are missing or stale. Running npm install...")
    completed = subprocess.run(
        make_npm_command(npm_executable, ["install"]),
        cwd=str(FRONTEND_DIR),
        env=build_env(extra_path),
        check=False,
    )
    if completed.returncode != 0:
        print("npm install failed. Fix the frontend dependency issue and run again.")
        return False
    return True


def start_process(name: str, command: list[str], cwd: Path, extra_path: list[str] | None = None) -> subprocess.Popen[str]:
    """Start a child process with line-buffered combined output."""
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=build_env(extra_path),
    )


def stream_output(name: str, process: subprocess.Popen[str]) -> None:
    """Mirror child process logs into the current terminal."""
    if process.stdout is None:
        return

    for line in process.stdout:
        print(f"[{name}] {line.rstrip()}")


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate a process and its child tree."""
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Flask backend and React frontend together.")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Do not run npm install automatically when frontend dependencies are missing or stale.",
    )
    args = parser.parse_args()

    node_dir = resolve_node_dir()
    npm_executable = resolve_npm(node_dir)
    if not npm_executable:
        print("npm not found. Install Node.js LTS first, then run this command again.")
        return 1

    if not FRONTEND_DIR.exists():
        print("Frontend directory not found: expected ./frontend")
        return 1

    package_json = FRONTEND_DIR / "package.json"
    if not package_json.exists():
        print("package.json was not found in ./frontend")
        return 1

    python_executable = resolve_python()
    backend_command = [python_executable, "app.py"]
    frontend_command = make_npm_command(npm_executable, ["run", "dev"])
    extra_path = [str(node_dir)] if node_dir else None

    if not args.skip_install and not ensure_frontend_dependencies(npm_executable, extra_path=extra_path):
        return 1

    print("Starting backend and frontend in one terminal...")
    print(f"Backend command : {' '.join(backend_command)}")
    print(f"Frontend command: {' '.join(frontend_command)}")
    print("Expected URLs:")
    print("  Flask API     -> http://127.0.0.1:5000")
    print("  React UI      -> http://127.0.0.1:5173")
    print("Press Ctrl + C to stop both services.\n")

    backend = start_process("backend", backend_command, ROOT_DIR, extra_path=extra_path)
    frontend = start_process("frontend", frontend_command, FRONTEND_DIR, extra_path=extra_path)

    threads = [
        threading.Thread(target=stream_output, args=("backend", backend), daemon=True),
        threading.Thread(target=stream_output, args=("frontend", frontend), daemon=True),
    ]
    for thread in threads:
        thread.start()

    processes = {"backend": backend, "frontend": frontend}

    try:
        while True:
            for name, process in processes.items():
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"\n{name} exited with code {exit_code}. Stopping the remaining service...")
                    return exit_code
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping backend and frontend...")
        return 0
    finally:
        for process in processes.values():
            terminate_process_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
