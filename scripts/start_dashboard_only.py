"""Start only the dashboard (FastAPI + uvicorn) without trading service.

Usage:
  python scripts/start_dashboard_only.py [--port 8888] [--host 0.0.0.0]

This is useful for isolating dashboard uptime from the trading loop.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_python_path():
    venv_path = Path('.venv')
    if venv_path.exists():
        if sys.platform == "win32":
            candidate = venv_path / "Scripts" / "python.exe"
        else:
            candidate = venv_path / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def main():
    parser = argparse.ArgumentParser(description="Start dashboard only")
    parser.add_argument('--port', type=int, default=8888, help='Dashboard port')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Dashboard host')
    args = parser.parse_args()

    python_path = get_python_path()

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    uv_log = log_dir / "dashboard-uvicorn.log"
    uv_out = open(uv_log, "a", encoding="utf-8")

    cmd = [
        python_path,
        "-u",
        "-m",
        "uvicorn",
        "dashboard_pro:app",
        "--host",
        args.host,
        "--port",
        str(args.port)
    ]

    print(f"Starting dashboard on http://{args.host}:{args.port} ... (logs -> {uv_log})")
    print("Command:", " ".join(cmd))

    # Launch uvicorn; leave running in foreground so user can stop with Ctrl+C
    proc = subprocess.Popen(cmd, cwd=Path(__file__).parent.parent, stdout=uv_out, stderr=uv_out)
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("Stopping dashboard...")
        proc.terminate()
    finally:
        uv_out.close()


if __name__ == "__main__":
    main()
