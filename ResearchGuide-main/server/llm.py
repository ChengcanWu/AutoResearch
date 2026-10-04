# -*- coding: utf-8 -*-
"""OpenAI 兼容 LLM 调用。未配置密钥时返回 None，调用方回退规则版。

环境变量（也可写在项目根目录 .env）：
  LLM_API_KEY   必填才会真正请求
  LLM_BASE_URL  默认 https://api.deepseek.com/v1
  LLM_MODEL     默认 deepseek-flash。DeepSeek 的 /models 只剩 deepseek-flash、deepseek-v4-pro；
                旧名 deepseek-chat 已列入停用，目前仍被路由到 deepseek-flash 的非思考模式。
                deepseek-flash 默认开思考（贵、慢），这里对 DeepSeek 默认关掉，见 _deepseek_extras()。
  LLM_REASONING_EFFORT  可选 low/high/max，只在支持的模型上填写
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    path = _ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


def config() -> dict:
    key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    ).strip()
    base = (os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
    model = (os.environ.get("LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "deepseek-flash").strip()
    return {"enabled": bool(key), "base_url": base, "model": model, "has_key": bool(key)}


def enabled() -> bool:
    return config()["enabled"]


def apply_config(base_url: str, api_key: str, model: str, *, persist: bool = True) -> dict:
    """运行时写入环境变量，并可选落盘到 .env（已在 gitignore）。"""
    base = (base_url or "https://api.deepseek.com/v1").strip().rstrip("/")
    key = (api_key or "").strip()
    name = (model or "deepseek-flash").strip()
    if not key:
        raise ValueError("API key is required")
    if not base.startswith("https://"):
        raise ValueError("base_url must start with https://")
    os.environ["LLM_BASE_URL"] = base
    os.environ["LLM_API_KEY"] = key
    os.environ["LLM_MODEL"] = name
    if persist:
        _save_dotenv(base, key, name)
    return config()


def _save_dotenv(base: str, key: str, model: str) -> None:
    """只改这三行，其余配置和注释原样保留（原来整份重写，会把别的变量冲掉）。"""
    path = _ROOT / ".env"
    want = {"LLM_BASE_URL": base, "LLM_API_KEY": key, "LLM_MODEL": model}
    old = path.read_text(encoding="utf-8").splitlines() if path.exists() else ["# 本地密钥，勿提交。由页面「连接模型」写入。"]
    out = []
    for line in old:
        name = line.split("=", 1)[0].strip()
        if not line.lstrip().startswith("#") and name in want:
            out.append(f"{name}={want.pop(name)}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in want.items()]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def probe() -> dict:
    """发一次极短请求，确认密钥和地址可用。"""
    cfg = config()
    if not cfg["enabled"]:
        return {"ok": False, "error": "未配置 API key"}
    text = chat("只回复 ok 两个字母。", "ping", temperature=0, timeout=20)
    if not text:
        return {"ok": False, "error": "请求失败，请检查地址、密钥和网络", "model": cfg["model"]}
    return {"ok": True, "model": cfg["model"], "base_url": cfg["base_url"], "sample": text[:40]}


def _post(url: str, key: str, payload: dict, timeout: int) -> tuple[dict | None, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), ""
    except urllib.error.HTTPError as exc:
        return None, f"http {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"network {type(exc).__name__}"
    except json.JSONDecodeError:
        return None, "bad json"


def _deepseek_extras(cfg: dict, effort: str) -> dict:
    """DeepSeek 的 deepseek-flash 默认开思考：没设推理强度就显式关掉，省钱也省时间。别的服务不加这个字段。"""
    if "api.deepseek.com" not in cfg["base_url"] or effort:
        return {}
    return {"thinking": {"type": "disabled"}}


def chat(system: str, user: str, *, temperature: float = 0.4, timeout: int = 25,
         json_mode: bool = False, tag: str = "chat", max_tokens: int = 2000) -> str | None:
    """返回助手文本；失败或未配置返回 None。网络错误、429、5xx 重试一次。"""
    cfg = config()
    if not cfg["enabled"]:
        return None
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    payload: dict = {
        "model": cfg["model"],
        "temperature": temperature,
        "max_tokens": max_tokens,  # 封顶：出错的长输出不会无限计费
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    effort = (os.environ.get("LLM_REASONING_EFFORT") or "").strip()
    if effort:
        payload["reasoning_effort"] = effort
    payload.update(_deepseek_extras(cfg, effort))
    url = cfg["base_url"] + "/chat/completions"
    t0 = time.time()
    data, err = None, ""
    for attempt in range(2):
        data, err = _post(url, key, payload, timeout)
        retry = err.startswith("network") or err in ("http 429", "http 500", "http 502", "http 503", "http 504")
        if data is not None or not retry or attempt == 1:
            break
        time.sleep(0.8)
    text = None
    if data is not None:
        try:
            text = (data["choices"][0]["message"]["content"] or "").strip() or None
        except (KeyError, IndexError, TypeError):
            err = "bad payload"
    usage = (data or {}).get("usage") or {}
    print(json.dumps({
        "llm": tag, "model": cfg["model"], "ok": bool(text), "ms": int((time.time() - t0) * 1000),
        "tokens": usage.get("total_tokens"), "error": err or None,
    }, ensure_ascii=False))
    return text


def chat_json(system: str, user: str, *, timeout: int = 30, tag: str = "json") -> dict | None:
    text = chat(system + "\n只输出一个 JSON 对象，不要 Markdown 代码块。", user, temperature=0.2,
                timeout=timeout, json_mode=True, tag=tag)
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
