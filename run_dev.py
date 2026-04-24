"""Run the Flask backend and React frontend together in one terminal."""

from __future__ import annotations

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


def start_process(name: str, command: list[str], cwd: Path, extra_path: list[str] | None = None) -> subprocess.Popen[str]:
    """Start a child process with line-buffered combined output."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if extra_path:
        env["PATH"] = os.pathsep.join(extra_path + [env.get("PATH", "")])
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
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
    frontend_command = [npm_executable, "run", "dev"]

    print("Starting backend and frontend in one terminal...")
    print(f"Backend command : {' '.join(backend_command)}")
    print(f"Frontend command: {' '.join(frontend_command)}")
    print("Expected URLs:")
    print("  Flask API     -> http://127.0.0.1:5000")
    print("  React UI      -> http://127.0.0.1:5173")
    print("Press Ctrl + C to stop both services.\n")

    extra_path = [str(node_dir)] if node_dir else None
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
