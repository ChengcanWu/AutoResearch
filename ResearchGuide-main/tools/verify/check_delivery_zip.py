# -*- coding: utf-8 -*-
"""把交付包解压到一个干净目录，从**解压出来的副本**跑测试。

这才是有说服力的验证：证明收到包的人解开就能跑，
而不是「在我这台机器上能跑」。
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

ZIP = pathlib.Path(r"C:\Users\<你的用户名>\Desktop\其他项目\ResearchGuide\启研-ResearchGuide-任务2-交付.zip")

tmp = pathlib.Path(tempfile.mkdtemp(prefix="delivery-check-"))
print(f"解压到: {tmp}\n")

with zipfile.ZipFile(ZIP) as z:
    z.extractall(tmp)

root = tmp / "AutoResearch" / "ResearchGuide-main"
print("=== 解压后的顶层结构 ===")
for p in sorted((tmp).iterdir()):
    print(f"  {p.name}")
print()
for p in sorted(root.iterdir()):
    if p.is_dir():
        n = sum(1 for _ in p.rglob("*") if _.is_file())
        print(f"  ResearchGuide-main/{p.name}/  ({n} 文件)")
    else:
        print(f"  ResearchGuide-main/{p.name}")

print(f"\n=== 从副本跑测试（{root}）===")
r = subprocess.run([sys.executable, "tools/verify/run_existing_tests.py"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=str(root))
tail = [l for l in (r.stdout or "").splitlines() if "passed" in l or "failed" in l or "error" in l]
print("  " + ("\n  ".join(tail[-4:]) if tail else "(无摘要)"))
print(f"  returncode = {r.returncode}")

if r.returncode != 0:
    print("\n--- stderr ---")
    print((r.stderr or "")[-2000:])

print("\n=== 从副本跑渲染层脚本 ===")
for s in ["verify_chat_layout.js", "verify_action_card.js",
          "verify_receipt_render.js", "verify_workbench_render.js"]:
    rr = subprocess.run(["node", f"tools/verify/{s}"], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", cwd=str(root))
    last = (rr.stdout or "").strip().splitlines()
    print(f"  {s:30} {last[-1] if last else '?':12} rc={rr.returncode}")

print("\n=== 服务能否起来（从副本起，验完杀掉）===")
print("  【两个坑，都踩过了】")
print("  1) 8100 是写死的端口。本机上若有旧服务在听，健康检查会打到**旧服务**，")
print("     于是「llm.enabled=true」这种结果毫无意义。所以先确认端口是空的。")
print("  2) 运行方式必须用 README 里那条 uv 命令——裸 `python server/main.py` 会")
print("     因为当前解释器没有 uvicorn 而失败，那是**验证方式**的问题，不是包的问题。")

# 先确认端口是空的，否则后面所有结论都不算数
import socket
_s = socket.socket()
_busy = _s.connect_ex(("127.0.0.1", 8100)) == 0
_s.close()
if _busy:
    print("  !! 8100 已被占用，本次验证无效。先停掉那个服务再跑。")
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(2)

UV_CMD = ["uv", "run", "--no-project", "--with", "fastapi", "--with", "uvicorn",
          "--with", "pydantic", "python", "server/main.py"]
proc = subprocess.Popen(UV_CMD, cwd=str(root),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace")
try:
    import urllib.request
    import time
    ok = False
    for _ in range(60):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8100/api/health", timeout=3) as resp:
                body = resp.read().decode()
            ok = True
            break
        except Exception:
            if proc.poll() is not None:
                break
    if ok:
        print("  起服务:", " ".join(UV_CMD))
        print("  /api/health →", body[:130])
        # 关键：副本目录里**没有** .env，所以这里必须是 enabled=false
        import json as _json
        cfg = _json.loads(body).get("llm", {})
        print(f"  llm.enabled = {cfg.get('enabled')}  （副本里没有 .env，期望 false）")
        if cfg.get("enabled"):
            print("  !! 副本里竟有可用密钥——说明包装进了密钥，必须排查")
            sys.exit(4)
        print("  ✔ 副本没有密钥，符合预期")
    else:
        print("  !! 没起来。输出：")
        print("  " + (proc.stdout.read() or "")[-1500:].replace("\n", "\n  "))
        sys.exit(5)
finally:
    proc.kill()
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-NetTCPConnection -State Listen -LocalPort 8100 -ErrorAction SilentlyContinue | "
                    "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                   capture_output=True, timeout=30)

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n清理完成（{tmp} 已删）")
