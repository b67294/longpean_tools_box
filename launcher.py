import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


PYTHON_EXE = Path(r"C:\Users\melonedoe\miniconda3\python.exe")
HOST = "127.0.0.1"
PORT = 8765


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    python_exe = PYTHON_EXE if PYTHON_EXE.exists() else Path(sys.executable)
    url = f"http://{HOST}:{PORT}"

    process = None
    if not is_port_open(HOST, PORT):
        process = subprocess.Popen(
            [
                str(python_exe),
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                HOST,
                "--port",
                str(PORT),
            ],
            cwd=base_dir,
        )
        for _ in range(50):
            if is_port_open(HOST, PORT):
                break
            time.sleep(0.1)

    webbrowser.open(url)

    if process is not None:
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()


if __name__ == "__main__":
    main()
