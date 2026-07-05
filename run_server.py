import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
PG_DATA = ROOT / ".devdata" / "pgdata"
PG_LOG = ROOT / ".devdata" / "pg.log"
PG_CTL = Path(r"C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe")

PG_PORT = 55433
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
VOICE_SCRIPT = BACKEND_DIR / "model" / "text_to_speach" / "test.py"


def listen_pids(port: int) -> list[int]:
    if os.name != "nt":
        return []
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue "
            "| Select-Object -ExpandProperty OwningProcess"
        ),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return sorted(set(pids))


def kill_pids(pids: list[int]) -> None:
    if not pids:
        return
    if os.name == "nt":
        for pid in pids:
            print(f"[ports] killing process {pid}")
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout).strip()
                print(f"[ports] taskkill failed for {pid}: {message or 'unknown error'}")
    else:
        for pid in pids:
            print(f"[ports] killing process {pid}")
            os.kill(pid, signal.SIGTERM)


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def find_free_port(start_port: int, max_tries: int = 50) -> int:
    for port in range(start_port, start_port + max_tries):
        if not is_port_open(port):
            return port
    raise RuntimeError(f"No free TCP port found in range {start_port}..{start_port + max_tries - 1}")


def backend_python() -> Path:
    exe = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not exe.exists():
        raise FileNotFoundError(f"Backend venv was not found: {exe}")
    return exe


def npm_command() -> str:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise FileNotFoundError("npm was not found in PATH")
    return npm


def run_checked(name: str, command: list[str], cwd: Path) -> None:
    print(f"[{name}] {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd, env=os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def start_postgres() -> None:
    if is_port_open(PG_PORT):
        print(f"[postgres] already listening on 127.0.0.1:{PG_PORT}")
        return
    if not PG_CTL.exists():
        raise FileNotFoundError(f"pg_ctl was not found: {PG_CTL}")
    if not PG_DATA.exists():
        raise FileNotFoundError(f"Postgres data directory was not found: {PG_DATA}")

    PG_LOG.parent.mkdir(parents=True, exist_ok=True)
    print(f"[postgres] starting on 127.0.0.1:{PG_PORT}")
    command = [
        str(PG_CTL),
        "-D",
        str(PG_DATA),
        "-l",
        str(PG_LOG),
        "-o",
        f"-p {PG_PORT} -h 127.0.0.1",
        "start",
    ]
    run_checked("postgres", command, ROOT)

    for _ in range(30):
        if is_port_open(PG_PORT):
            print("[postgres] ready")
            return
        time.sleep(0.5)
    raise TimeoutError("Postgres did not start in time")


def stream_output(name: str, process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{name}] {line}", end="")


def start_process(
    name: str,
    command: list[str],
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    print(f"[{name}] starting: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", **(extra_env or {})},
    )
    threading.Thread(target=stream_output, args=(name, process), daemon=True).start()
    return process


def wait_for_url(url: str, name: str, timeout_seconds: int = 30) -> None:
    print(f"[{name}] waiting for {url}")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    print(f"[{name}] ready")
                    return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"{name} did not become ready in {timeout_seconds}s")


def wait_for_port_closed(port: int, timeout_seconds: int = 10) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_port_open(port):
            return True
        time.sleep(0.5)
    return not is_port_open(port)


def should_kill_busy_port(name: str, port: int, kill_existing: bool) -> bool:
    pids = listen_pids(port)
    pid_text = ", ".join(map(str, pids)) or "unknown"
    print(f"[{name}] port {port} is already busy. PID: {pid_text}")
    if kill_existing:
        return True

    command = f'& "{sys.executable}" "{Path(__file__).resolve()}" --kill-existing'
    print("Run this full command to stop old hidden servers automatically:")
    print(f"  {command}")
    answer = input(f"Stop old {name} process now? [y/N]: ").strip().lower()
    return answer in {"y", "yes", "д", "да"}


def resolve_port(name: str, preferred_port: int, kill_existing: bool) -> int:
    if not is_port_open(preferred_port):
        return preferred_port

    should_kill = should_kill_busy_port(name, preferred_port, kill_existing)
    if should_kill:
        pids = listen_pids(preferred_port)
        kill_pids(pids)
        if wait_for_port_closed(preferred_port):
            print(f"[{name}] port {preferred_port} is free")
            return preferred_port

        pids = listen_pids(preferred_port)
        pid_text = ", ".join(map(str, pids)) or "unknown"
        print(f"[{name}] port {preferred_port} is still busy. PID: {pid_text}")
        print(f"[{name}] using another visible port instead")
    else:
        print(f"[{name}] old server stays on port {preferred_port}; using another visible port instead")

    fallback_port = find_free_port(preferred_port + 1)
    print(f"[{name}] selected port {fallback_port}")
    return fallback_port


def stop_processes(processes: list[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    time.sleep(1)
    for process in processes:
        if process.poll() is None:
            process.terminate()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    kill_existing = "--kill-existing" in sys.argv
    start_voice = "--voice" in sys.argv

    print("Karavay dev server")
    print(f"root: {ROOT}")
    if start_voice:
        print("[voice] enabled: Vosk recognizer will be started after backend is ready")

    backend_port = resolve_port("backend", BACKEND_PORT, kill_existing)
    frontend_port = resolve_port("frontend", FRONTEND_PORT, kill_existing)

    py = backend_python()
    npm = npm_command()

    start_postgres()
    run_checked("alembic", [str(py), "-m", "alembic", "upgrade", "head"], BACKEND_DIR)

    processes = [
        start_process(
            "backend",
            [str(py), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port), "--reload"],
            BACKEND_DIR,
        ),
        start_process(
            "frontend",
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port)],
            FRONTEND_DIR,
            extra_env={"VITE_API_BASE_URL": f"http://127.0.0.1:{backend_port}/api"},
        ),
    ]

    if start_voice:
        if not VOICE_SCRIPT.exists():
            print(f"[voice] script was not found: {VOICE_SCRIPT}")
        else:
            wait_for_url(f"http://127.0.0.1:{backend_port}/health", "backend")
            processes.append(
                start_process(
                    "voice",
                    [str(py), str(VOICE_SCRIPT)],
                    ROOT,
                    extra_env={
                        "VOICE_GRAMMAR_URL": f"http://127.0.0.1:{backend_port}/api/voice/grammar",
                        "VOICE_TRANSCRIPT_URL": f"http://127.0.0.1:{backend_port}/api/voice/transcript",
                    },
                )
            )

    print(f"\nOpen: http://127.0.0.1:{frontend_port}")
    print(f"API:  http://127.0.0.1:{backend_port}/api")
    print("Press Ctrl+C to stop backend and frontend.\n")
    webbrowser.open(f"http://127.0.0.1:{frontend_port}")

    try:
        while True:
            for process in processes:
                code = process.poll()
                if code is not None:
                    stop_processes(processes)
                    print(f"Process exited with code {code}")
                    return code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        stop_processes(processes)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
