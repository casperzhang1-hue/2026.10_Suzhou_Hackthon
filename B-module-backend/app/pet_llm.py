"""本地开源模型的唯一出口。

设计原则：**只认 OpenAI 兼容协议**。Ollama、vLLM、LM Studio、llama.cpp server、
one-api 网关全都说这套，所以换模型只改环境变量，不改一行代码：

    PET_LLM_BASE_URL  默认 http://127.0.0.1:11434/v1   （Ollama）
    PET_LLM_MODEL     默认 qwen2.5:7b-instruct          （开源权重，Apache-2.0）
    PET_LLM_API_KEY   默认 ollama                       （本地服务不校验，占位用）

本模块的边界很窄：**只管跟模型把话说完**，不管人设（pet_persona）、
不管事实（pet_brain）、不管校验（pet_brain.check）。
这样换模型不动性格，改性格不动网络层。

为什么不像识别模块那样走云通道：那条通道规定只能前端直连、禁止服务端代理；
而本地模型是我们自己的进程，没有这个限制，走后端反而更好——
超时、限流、串行队列、失败降级都能在后端一处收口。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b-instruct"


class LLMError(RuntimeError):
    """模型不可用或答非所问。调用方应当降级，不要重试。"""


def load_env() -> None:
    """把 .env 读进环境变量。

    不引 python-dotenv，因为这里只需要支持 ``KEY=VALUE`` 一种写法；
    多一个依赖就多一次「装不上」的机会，而这套东西是要在别人的笔记本上跑的。
    已存在的环境变量优先，方便临时覆盖（PET_LLM_MODEL=xxx python start.py）。
    """
    roots = [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent.parent.parent]
    for root in roots:
        env_file = root / ".env"
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def config() -> dict:
    return {
        "base_url": (os.environ.get("PET_LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("PET_LLM_MODEL") or DEFAULT_MODEL,
        "api_key": os.environ.get("PET_LLM_API_KEY") or "ollama",
        "timeout": float(os.environ.get("PET_LLM_TIMEOUT") or 25),
        "max_tokens": int(os.environ.get("PET_LLM_MAX_TOKENS") or 96),
    }


def _headers(cfg: dict) -> dict:
    return {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }


def _client(cfg: dict, **kw) -> httpx.Client:
    timeout = httpx.Timeout(connect=1.5, read=cfg["timeout"], write=10.0, pool=3.0)
    return httpx.Client(timeout=kw.pop("timeout", timeout), **kw)


def probe(timeout: float = 1.6) -> dict:
    """探活：本机有没有一个能用的开源模型在跑。

    前端开机问一次，决定这一局到底走「模型嘴」还是「模板嘴」。
    故意做得很便宜（GET /models，1.6 秒），失败立刻返回，绝不让页面等。
    """
    cfg = config()
    out = {
        "available": False,
        "provider": "openai-compatible",
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "models": [],
        "reason": "",
    }
    try:
        with _client(cfg, timeout=httpx.Timeout(connect=1.2, read=timeout, write=timeout, pool=1.0)) as c:
            r = c.get(cfg["base_url"] + "/models", headers=_headers(cfg))
            if r.status_code >= 400:
                out["reason"] = f"HTTP {r.status_code}"
                return out
            data = r.json()
        ids = [m.get("id") for m in (data.get("data") or []) if isinstance(m, dict)]
        out["models"] = [i for i in ids if i]
        out["available"] = True
        # 配置的模型名不在列表里（比如 Ollama 里实际叫 qwen2.5:7b）时，
        # 用列表里第一个可用的，避免「服务活着但模型名写错」被误判成不可用
        if out["models"] and cfg["model"] not in out["models"]:
            out["model"] = out["models"][0]
            out["reason"] = f"配置的模型 {cfg['model']} 不在列表里，改用 {out['model']}"
    except Exception as e:  # 连不上、DNS、端口没开，一律视为不可用
        out["reason"] = f"{type(e).__name__}: {e}"
    return out


def _extract(payload: dict) -> str:
    try:
        msg = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"返回结构不对: {payload}") from e
    content = msg.get("content")
    if isinstance(content, list):  # 有些服务把内容拆成多段
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return (content or "").strip()


def chat(messages: list[dict], *, temperature: float = 0.75, max_tokens: int | None = None) -> str:
    """一次性要答案（非流式）。

    刻意不用流式：宠物的话短，流式省不下多少时间，却把「先校验再上屏」
    变成「先上屏再校验」——后者一旦答错，用户已经看见了。
    """
    cfg = config()
    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or cfg["max_tokens"],
        "stream": False,
    }
    try:
        with _client(cfg) as c:
            r = c.post(cfg["base_url"] + "/chat/completions", headers=_headers(cfg), json=body)
    except httpx.TimeoutException as e:
        raise LLMError(f"超时 {cfg['timeout']}s") from e
    except Exception as e:
        raise LLMError(f"连不上 {cfg['base_url']}: {e}") from e

    if r.status_code >= 400:
        raise LLMError(f"模型报错 HTTP {r.status_code}: {r.text[:200]}")
    return _extract(r.json())


def stream_chat(messages: list[dict], *, temperature: float = 0.75, max_tokens: int | None = None) -> Iterable[str]:
    """流式版本。目前不用，留给以后要逐字上屏的场合（已在 curl 上验过 Ollama/vLLM 均通）。"""
    cfg = config()
    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or cfg["max_tokens"],
        "stream": True,
    }
    with _client(cfg) as c:
        with c.stream("POST", cfg["base_url"] + "/chat/completions", headers=_headers(cfg), json=body) as r:
            if r.status_code >= 400:
                raise LLMError(f"模型报错 HTTP {r.status_code}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    return
                try:
                    delta = json.loads(chunk)["choices"][0].get("delta") or {}
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                piece = delta.get("content")
                if piece:
                    yield piece


def describe() -> str:
    """给日志/接口用的一行说明，例：qwen2.5:7b-instruct @ 127.0.0.1:11434。"""
    cfg = config()
    host = cfg["base_url"].split("//", 1)[-1]
    return f"{cfg['model']} @ {host}"


if __name__ == "__main__":  # 手动排查用：python -m app.pet_llm
    t0 = time.time()
    info = probe()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if info["available"]:
        print(chat([{"role": "user", "content": "用五个字说你在"}]), f"({int((time.time() - t0) * 1000)}ms)")
