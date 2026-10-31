"""它真的看一眼他传的那张图。

之前这条链是断的：图片 → 识别 → 写进 records 表，宠物完全不知道有这回事。
所以他说「你怎么知道我做了这么久」，它手上只有 dry 的分钟数，
只好编一句「我闻到你袖口有咖啡味」——这是被逼出来的假话。

现在补上三件事：

- ``see``    把图交给视觉模型，只让它做**抽取**，不做抒情：
             APP、日期、时长、科目、题量、对错，看不清就 null，明令不许猜。
- ``to_facts`` 抽出来的东西进 facts，进不了的字段一律不写进 prompt。
- 宠物的话仍然由人设那一层生成，视觉层不碰语气——两件事分开，
  换模型不动性格，改性格不动视觉。

实测（2026-10-31，本机，158KB 粉笔截图）：gpt-4o-mini 7.0s，
读出「判断推理 / 15 题 / 对 9 题 / 23 分 51 秒」，与识别模块的落库结果一致。
qwen3-vl-flash 与 qwen-vl-max 在该中转站返回 404 InvalidParameter，不可用。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re

import httpx

from . import pet_llm

DEFAULT_MODEL = "gpt-4o-mini"

# 只要抽取，不要文采。让它抒情就一定会编——它没看过这个人，只见过这张图。
#
# 关键在「先逐行转写，再只从转写里取字段」这两步：
# 一步到位的抽取实测会把科目填进 app、把 modules 留空（真实 158KB 粉笔截图），
# 两段式之后 科目/题量/对错/时长 四项全对。转写也是它的证据链，
# 它后面说「图上写着 23 分 51 秒」时，那句话真的在图里。
EXTRACT_PROMPT = """你在读一张备考打卡截图。分两步，只输出一个 JSON：

第一步，把图上所有看得见的文字逐行照抄到 "lines"（最多 20 行，原样，不要总结）。
第二步，只从 lines 里抄出字段，抄不到就 null，不许猜、不许算、不许凑整：

{"lines":["..."],
 "app":"图上真的写了应用名才填，否则 null",
 "date":"MM-DD 或 null",
 "minutes":总用时分钟数或 null,
 "modules":[{"name":"科目名","questions":题数,"correct":答对数}],
 "evidence":"最能证明时长的原话，从 lines 里挑一句"}
"""

# 公考科目词表：用来判断模型填的模块名是不是真的图上有，
# 而不是它自己按常识补的。图上没写、词表里也没有，就当没看清。
KNOWN_SUBJECTS = (
    "数量关系", "资料分析", "判断推理", "言语理解", "常识判断", "申论",
    "图形推理", "定义判断", "类比推理", "逻辑判断", "数学运算", "资料汇总",
    "判断", "言语", "常识", "数量", "资料", "图推",
)

# 应用名白名单。为什么不信任模型自由发挥：实测它把「专项智能练习」填进了 app，
# 于是它开口就是「这张我看了，专页智能练习，判断推理……」——图上那行字是练习类型，
# 不是应用名。宁可不提应用名，也不能把一栏字说成一个应用。
KNOWN_APPS = (
    "粉笔", "华图", "中公", "腰果", "半月谈", "步知", "一起考教师", "上岸",
    "学习强国", "超格", "导氮", "格燃", "公务员考试", "刷题",
)

# 模型偶尔会把提示词里的占位说明当成答案抄回来（实测 app 被填成
# 「应用名（图上写了的才填）或 null」）。这种值必须当没填。
_PLACEHOLDER = ("或 null", "如果", "图上真的写了", "应用名", "科目名", "MM-DD", "看不清", "unknown", "n/a")


def config() -> dict:
    return {
        "model": os.environ.get("PET_VISION_MODEL") or DEFAULT_MODEL,
        "timeout": float(os.environ.get("PET_VISION_TIMEOUT") or 30),
    }


def fingerprint(image: bytes) -> str:
    """图片指纹。同一张图传两次，宠物不该看两遍，更不该记成两次学习。"""
    return hashlib.sha256(image or b"").hexdigest()[:32]


def _decode(data: str) -> bytes:
    """接受 data URL 或裸 base64。前端两种都可能给。"""
    s = (data or "").strip()
    if not s:
        return b""
    if s.startswith("data:"):
        s = s.split(",", 1)[-1]
    try:
        return base64.b64decode(s, validate=False)
    except Exception:
        return b""


def _as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"-?\d+", str(value))
    return int(m.group()) if m else None


def _clean_str(value, lines: str) -> str | None:
    """字符串字段的两道体检：不许照抄提示词，基本得在图上的字里出现过。"""
    s = str(value or "").strip()
    if not s or s.lower() in ("null", "none"):
        return None
    if any(p in s for p in _PLACEHOLDER):
        return None                    # 把说明文字当答案抄回来了
    # 「粉笔」这种应用名可能只在 logo 里，图上没有文字，所以不强求命中；
    # 但长度离谱或明显是句子，就不认。
    if len(s) > 16:
        return None
    return s


def _app(value) -> str | None:
    """应用名只认白名单里的。认不出就不提——把「专项智能练习」当应用名说出来，
    比不提应用名丢人得多。"""
    s = str(value or "").strip()
    if not s or len(s) > 12:
        return None
    for name in KNOWN_APPS:
        if name in s:
            return name
    return None


def parse(raw: str) -> dict | None:
    """从模型的回答里抠出那个 JSON。抠不出就当没看清——不猜。"""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    lines = [str(x).strip() for x in (data.get("lines") or []) if str(x).strip()]
    blob = " ".join(lines)

    modules = []
    for m in (data.get("modules") or []):
        if not isinstance(m, dict):
            continue
        name = _clean_str(m.get("name"), blob)
        if not name:
            continue
        # 图上没有、词表里也没有的科目，就是它按常识补的——不要
        if name not in blob and not any(k in name for k in KNOWN_SUBJECTS):
            continue
        modules.append({
            "name": name,
            "questions": _as_int(m.get("questions")),
            "correct": _as_int(m.get("correct")),
        })

    out = {
        "app": _app(data.get("app")),
        "date": _clean_str(data.get("date"), blob),
        "minutes": _as_int(data.get("minutes")),
        "modules": modules,
        "evidence": _clean_str(data.get("evidence"), blob),
        "lines": lines[:20],
    }
    # 一个能用的字段都没有，等于没看清
    if not out["modules"] and out["minutes"] is None:
        return None
    return out


def see(image: bytes, *, timeout: float | None = None) -> dict:
    """看一眼这张图。返回 ``{"ok": bool, "seen": {...}, "model": ..., "reason": ...}``。

    失败一律 ``ok=False``，绝不返回半真半假的猜测：
    猜出来的科目会被拼进 facts，然后被宠物当成真的说出来，那是最坏的结果。
    """
    cfg = config()
    out = {"ok": False, "seen": None, "model": cfg["model"], "raw": "", "reason": ""}
    if not image:
        out["reason"] = "没有图片"
        return out

    b64 = base64.b64encode(image).decode()
    body = {
        "model": cfg["model"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": EXTRACT_PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
            ],
        }],
        "temperature": 0,
        "max_tokens": 700,          # 逐行转写很占 token，300 会把 lines 截断
        "stream": False,
    }
    try:
        with httpx.Client(timeout=timeout or cfg["timeout"]) as c:
            r = c.post(
                pet_llm.config()["base_url"] + "/chat/completions",
                headers={"Authorization": "Bearer " + pet_llm.config()["api_key"],
                         "Content-Type": "application/json"},
                json=body,
            )
    except Exception as e:
        out["reason"] = f"{type(e).__name__}: {e}"
        return out

    if r.status_code >= 400:
        out["reason"] = f"HTTP {r.status_code}: {r.text[:120]}"
        return out

    try:
        raw = r.json()["choices"][0]["message"].get("content") or ""
    except Exception as e:
        out["reason"] = f"返回结构不对: {e}"
        return out
    out["raw"] = raw

    seen = parse(raw)
    if not seen:
        out["reason"] = "图上看不出有效信息"
        return out
    out["ok"] = True
    out["seen"] = seen
    return out


def summary(seen: dict) -> str:
    """一句话摘要，进 facts.sources 用的。只描述抽到的字段，不加形容词。"""
    bits = []
    if seen.get("app"):
        bits.append(seen["app"])
    if seen.get("date"):
        bits.append(seen["date"])
    for m in seen.get("modules") or []:
        piece = m["name"]
        if m.get("questions") is not None:
            piece += f" {m['questions']} 题"
            if m.get("correct") is not None:
                piece += f"对 {m['correct']} 题"
        bits.append(piece)
    if seen.get("minutes") is not None:
        bits.append(f"{seen['minutes']} 分钟")
    return "，".join(bits) or "一张图"
