"""Server'ni to'liq ajratilgan (detached) holda ishga tushiradi.

Ishlatish: python daemon.py [port]
"""

import os
import subprocess
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "8000"
ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = "/tmp/ai_srv.log"

pid = os.fork()
if pid > 0:
    print(f"Server boshlanyapti: http://localhost:{PORT} (pid {pid})")
    sys.exit(0)

os.setsid()
sys.stdout.flush()
with open(LOG, "w") as f:
    subprocess.run(
        [
            os.path.join(ROOT, "venv", "bin", "uvicorn"),
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            PORT,
        ],
        cwd=ROOT,
        stdout=f,
        stderr=subprocess.STDOUT,
    )
