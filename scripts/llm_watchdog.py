"""LLM 看门狗：探测本地 llama.cpp，连续失败自动重启

背景：本地 LLM 曾出现"孤儿进程退化 → HTTP 500/空流 → 客服静默走兜底"，
本脚本作为独立守护进程（systemd/task scheduler 常驻）解决：
  - 每 interval 秒探测 /v1/models
  - 连续 failures 次失败 → 用标准命令重启（日志落 logs/llm_watchdog_*.log）
  - 重启后等待就绪，成功则恢复计数并记录

用法：
    python scripts/llm_watchdog.py                    # 常驻守护
    python scripts/llm_watchdog.py --once             # 单次检查（CI/手动）
    python scripts/llm_watchdog.py --interval 30 --failures 2
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import settings

_LOG_DIR = Path(settings.chroma_persist_dir).parent / "logs"  # data/../logs -> workspace/logs
_LOG_DIR = (Path(__file__).resolve().parent.parent / "logs")


def check_llm(timeout: float = 3.0, deep: bool = True) -> bool:
    """探测 LLM 是否可用

    deep=True（默认）：发最小生成请求（max_tokens=1），
    能识别"models 接口存活但生成 500"的降级态（本项目反复出现的退化问题）；
    deep=False：仅 GET /v1/models（快速存活检查）。
    """
    base = f"http://{settings.local_llm_host}:{settings.local_llm_port}"
    if not deep:
        try:
            with urllib.request.urlopen(base + "/v1/models", timeout=timeout) as r:
                return r.status == 200
        except Exception:
            return False
    body = json.dumps({
        "model": "local-qwen3-1.7b",
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 1,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        base + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def restart_llm() -> bool:
    """用标准命令重启 llama.cpp（复用启动参数），返回是否拉起成功

    先杀掉旧进程释放端口（关键：退化态旧进程往往仍占着 8001，
    不杀则新进程绑定失败，永远无法恢复）。
    """
    _kill_port_process(settings.local_llm_port)
    time.sleep(2)
    out = open(_LOG_DIR / "llm_watchdog_out.log", "ab")
    err = open(_LOG_DIR / "llm_watchdog_err.log", "ab")
    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", settings.local_llm_model_path,
        "--host", settings.local_llm_host,
        "--port", str(settings.local_llm_port),
        "--n_ctx", str(settings.local_llm_ctx),
        "--n_threads_batch", "4",
        "--chat_template_kwargs", '{"enable_thinking": false}',
    ]
    try:
        subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent.parent),
                         stdout=out, stderr=err, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # 等待就绪（最多 120s）
        deadline = time.time() + 120
        while time.time() < deadline:
            if check_llm():
                return True
            time.sleep(3)
        return False
    except Exception:
        return False


def _kill_port_process(port: int) -> bool:
    """杀掉监听指定端口的进程（psutil），返回是否有进程被终止"""
    import psutil

    killed = False
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
            try:
                p = psutil.Process(conn.pid)
                p.kill()
                p.wait(timeout=5)
                killed = True
                print(f"  已终止旧 LLM 进程 pid={conn.pid}")
            except Exception:
                pass
    return killed


def run(interval: int, failures: int, once: bool) -> int:
    consecutive = 0
    restarts = 0
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        if check_llm():
            consecutive = 0
            if once:
                print(f"[{datetime.utcnow().isoformat()}] LLM OK")
                return 0
        else:
            consecutive += 1
            print(f"[{datetime.utcnow().isoformat()}] LLM 探测失败 {consecutive}/{failures}")
            if consecutive >= failures:
                print("触发 LLM 重启...")
                ok = restart_llm()
                restarts += 1
                if ok:
                    consecutive = 0
                    print(f"LLM 已恢复（累计重启 {restarts} 次）")
                else:
                    print("LLM 重启失败，稍后重试")
                if once:
                    return 0 if ok else 1
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--failures", type=int, default=2)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.interval, args.failures, args.once))
