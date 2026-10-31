#!/usr/bin/env python
"""一键启动全栈 demo：FastAPI + SQLite (8000) 与前端原型 (8899)。

用法：
    python start_fullstack.py            # 起服务并打开浏览器
    python start_fullstack.py --no-open  # 只起服务

按 Ctrl+C 一起关闭。
"""
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "B-module-backend"
FRONTEND = ROOT / "A-module-frontend"
PORT_API = 8000
PORT_WEB = 8899
DEMO_TODAY = "2026-10-31"  # 路演日期钉死，回放不漂移


def pick_python() -> str:
    for cand in (BACKEND / ".venv/Scripts/python.exe", BACKEND / ".venv/bin/python"):
        if cand.exists():
            return str(cand)
    return sys.executable


def main() -> int:
    if not (BACKEND / "app/main.py").exists():
        print("找不到后端目录，请在仓库根目录运行本脚本。")
        return 1

    env = {**os.environ, "HAMSTER_TODAY": DEMO_TODAY}
    py = pick_python()

    print(f"[1/2] 启动后端  http://127.0.0.1:{PORT_API}   (SQLite: B-module-backend/data/hamster.db)")
    api = subprocess.Popen(
        [py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT_API)],
        cwd=str(BACKEND),
        env=env,
    )

    print(f"[2/2] 启动前端  http://127.0.0.1:{PORT_WEB}/index.html")
    web = subprocess.Popen(
        [py, "-m", "http.server", str(PORT_WEB), "--bind", "127.0.0.1"],
        cwd=str(FRONTEND),
    )

    time.sleep(3)
    url = f"http://127.0.0.1:{PORT_WEB}/index.html"
    if "--no-open" not in sys.argv:
        webbrowser.open(url)

    print("\n演示地址：" + url)
    print("接口自检：" + f"http://127.0.0.1:{PORT_API}/api/health")
    print("按 Ctrl+C 结束。\n")

    try:
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (api, web):
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                except Exception:
                    p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
