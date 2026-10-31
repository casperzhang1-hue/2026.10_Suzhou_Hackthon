"""记忆：他说的每一句话，怎么变成它能想起来的事。

之前的状态是「没有记忆管理」——库里只有三条 seed 记忆，全是**系统写的旁白**，
比如 quote 写着「那天你学到凌晨两点」。模型读到它，就当成他说过的话，
于是回出「你上次说『学到凌晨两点』」。那是三处错误叠在一起：

1. 旁白被当成了原话（谁说的没标）
2. 他说的话从来不落库（没有写入路径）
3. 没有时间（41 天前和刚才，对它是一回事）

所以这个模块只做三件事，每件都对应上面一个错：

- ``extract``   把他的一句话抽成一条记忆，**存原话，不存摘要**
- ``remember``  写库，带 created_at、source、who
- ``view``      给模型看的形状：``who`` 标明「这话是他说的还是我给他记的旁白」

设计取向和 pet_persona 一致：规则优先，不调模型抽记忆。
调模型抽记忆要花钱、要不稳定、还可能把他的话改写走样——
而「改写走样」正是这一整轮 bug 的起点。
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

# 他这句话是不是在「交代一件可以记的事」
_PROMISE = ("我要", "我一定", "我答应", "我决定", "从明天", "明天我", "以后我", "下周我", "我发誓")
_FEELING = ("累", "困", "烦", "慌", "怕", "难受", "撑不住", "想哭", "焦虑", "崩", "学不动",
            "不想学", "看不进", "压力", "睡不着")
_PREFER = ("我讨厌", "我喜欢", "我最怕", "我受不了", "我偏爱", "我恨", "我爱")
_EVENT = ("今天", "昨天", "刚刚", "刚才", "上午", "下午", "晚上", "熬夜", "熬到", "刷了",
          "做了", "学了", "考了", "模考", "错", "对了", "卡住")

# 纯提问不算记忆。「我今天做得怎么样？」里的「今天」不该被记成事件
_QUESTION_TAIL = ("吗", "呢", "么", "?", "？")
_INTERROGATIVE = ("怎么", "为什么", "为啥", "多少", "几道", "几题", "哪", "是不是",
                  "能不能", "可不可以", "凭什么", "啥")

# 开头就是「你」的，是在问它、不是在说自己。
# 不加这条，「你怎么知道我做了这么长时间」会被当成一条事件记忆存进去，
# 然后它下次回答「你怎么知道」时，就理直气壮地说「你刚才跟我说的呀」——
# 出处指向他自己刚问的那句问话，等于没答。
_ABOUT_PET = re.compile(r"^\s*[你您]")

# 第一人称：有「我」才是他自己的话
_FIRST_PERSON = re.compile(r"我")

# 旁白句式：以「你」开头，或含「那天你」。这类是系统摘要，不是原话
_NARRATION = re.compile(r"^(那天|那晚|那次)?你|他说|用户")

# 否认句不是情绪记录。「我不累啊」是在反驳，不是在交代状态——
# 记下来之后，它下次就会拿这句当素材说「你刚说不累」，一句废话被复读三轮。
_DENIAL = re.compile(
    r"(?:不|没|没有|才不|并不|一点都不|压根不)[^，。！？、；]{0,4}?"
    r"(?:累|困|倦|难受|崩|烦|慌|焦虑|怕)"
)

MAX_QUOTE = 80

# 他告诉我他叫什么。这一条单独抽出来，因为「你该叫我什么」这类问题
# 只有拿到名字才答得对；没有名字就必须老实说不知道。
# 三个句式覆盖口语里的说法：「我叫张伟」「我名字叫张伟」「叫我小伟就行」。
_NAME_PATTERNS = (
    re.compile(r"我的名字(?:是|叫)([^\s，。！？、,.!?]{1,6})"),
    re.compile(r"我名字(?:是|叫)([^\s，。！？、,.!?]{1,6})"),
    re.compile(r"我叫([^\s，。！？、,.!?]{1,6})"),
    re.compile(r"(?:你|您)?(?:可以|就|以后|直接)?叫我([^\s，。！？、,.!?]{1,6})"),
)
# 抽出来的是这些，就是在问、不是在说
_NAME_STOP = {"什么", "啥", "什么名字", "啥名字", "什么呀", "啥呀", "谁", "名字", "啥名"}
# 抽完要剥掉的口语尾巴：「叫我小一就行」里的名字是「小一」
_NAME_TAIL = ("就行", "就好", "好了", "吧", "呀", "啦", "哦", "喔", "呗", "啊")


def extract_name(text: str) -> str | None:
    """他这句话里有没有他的名字。没有就返回 None。

    宁可漏记不要错记：「我叫什么」抽出来的「什么」必须挡掉，
    不然它会把「什么」当成他的名字，下次一本正经地喊他「什么」。
    """
    t = (text or "").strip()
    if not t:
        return None
    for pat in _NAME_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        name = m.group(1).strip("，。！？、,.!? ")
        stripped = True
        while stripped:                        # 尾巴可能叠两层：「小一就行啦」
            stripped = False
            for tail in _NAME_TAIL:
                if name.endswith(tail) and len(name) > len(tail):
                    name = name[: -len(tail)]
                    stripped = True
        if not name or name in _NAME_STOP:
            continue
        # 疑问词混进来的，一定是在问，不是在说（「我叫什么吗」「我叫啥」）
        if any(w in name for w in ("什么", "啥", "谁", "吗")):
            continue
        if len(name) > 6:
            continue
        # 「叫我一起」「叫我一声」这类不是名字
        if name.startswith(("一", "声", "一下")) or name.endswith(("一声", "一下")):
            continue
        return name
    return None


def current_name(memories: list[dict] | None) -> str | None:
    """他现在叫什么。取最近一条名字记忆——他改名了就按新的叫。"""
    for m in reversed(list(memories or [])):
        if m.get("type") == "name" and m.get("name"):
            return m["name"]
    return None



def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "")).strip("，。！？、 ")


def is_narration(quote: str) -> bool:
    """这条记忆是系统写的旁白，还是他本人的原话。

    判据只有一条硬的：**原话里一定有「我」**。他说自己，绕不开这个字。
    「那天你学到凌晨两点」「断了一天，第二天就回来了」都是系统给他记的一笔账，
    没有人会这样说自己。把它们当原话，它就会说出「你说过断一天……」——
    他没说过，这是第二次被当面戳穿的那种假。
    """
    q = (quote or "").strip()
    if not q:
        return True
    if q.startswith("我"):
        return False
    if _NARRATION.search(q):
        return True
    return "我" not in q


def classify(text: str) -> str | None:
    """这句话属于哪一类。返回 None 表示不值得记。"""
    t = (text or "").strip()
    if len(_norm(t)) < 3:
        return None
    if _ABOUT_PET.search(t):
        return None                      # 在问它，不是在说自己
    ask = t.rstrip("。！…~ ")
    if ask.endswith(_QUESTION_TAIL) and not any(w in t for w in ("我要", "我一定")):
        return None                      # 提问不是记忆
    if any(w in t for w in _INTERROGATIVE) and not any(w in t for w in _PROMISE):
        return None                      # 「我该怎么办」这种也不是
    if not _FIRST_PERSON.search(t):
        return None                      # 没有「我」，不是他在说自己
    if any(w in t for w in _PROMISE):
        return "promise"
    if any(w in t for w in _PREFER):
        return "prefer"
    # 情绪词要先剥掉否认再看：「我不累啊」里的「累」不是他的状态
    if any(w in _DENIAL.sub("", t) for w in _FEELING):
        return "feeling"
    if any(w in t for w in _EVENT):
        return "event"
    return None


def extract(text: str, *, known_modules: list[str] | None = None) -> dict | None:
    """他一句话进来，抽出一条能记的事。抽不出就返回 None——宁可漏记，不要瞎记。

    刻意不做摘要：``quote`` 存他的原话（截 80 字）。
    摘要会丢人称，而人称一丢，模型就会把旁白说成「你说过」。
    """
    name = extract_name(text)
    kind = "name" if name else classify(text)
    if not kind:
        return None
    quote = (text or "").strip()
    if len(quote) > MAX_QUOTE:
        quote = quote[:MAX_QUOTE]
    mod = next((m for m in (known_modules or []) if m and m in quote), None)
    item = {
        "id": "m_" + uuid.uuid4().hex[:10],
        "type": kind,
        "quote": quote,
        "days_ago": 0,
        "said_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "user",
        "who": "他",
    }
    if mod:
        item["module"] = mod
    if name:
        item["name"] = name          # 「你该叫我什么」只有这一个字段答得出来
    return item


def _when(m: dict) -> str:
    """「多久之前」要说人话。41 天前的安慰和刚才说的，语气完全不同。"""
    days = m.get("days_ago")
    if days is None:
        said = m.get("said_at") or ""
        return said[:10] if said else "有一阵了"
    days = int(days)
    if days <= 0:
        return "刚才"
    if days == 1:
        return "昨天"
    if days < 7:
        return f"{days} 天前"
    if days < 30:
        return f"{days // 7} 周前"
    return f"{days} 天前"


def view(m: dict) -> dict:
    """给模型看的记忆形状。

    ``who`` 是关键：``他`` = 他亲口说的原话，``旁白`` = 我给他记的一笔账。
    模型只能对 ``who=他`` 说「你说过」，对旁白只能说「我记得你……」。
    """
    quote = (m.get("quote") or "").strip()
    out = {
        "who": "旁白" if is_narration(quote) else "他",
        "when": _when(m),
        "text": quote,
        "kind": m.get("type"),
    }
    if m.get("module"):
        out["module"] = m["module"]
    return out


def remember(store, text: str, *, user_id: str = "demo_zhang",
             known_modules: list[str] | None = None,
             kind: str | None = None) -> dict | None:
    """把他的这句话记下来。重复的话不重复记（同一句 10 条以内算重复）。

    返回落库的那条，没记则返回 None。
    """
    item = extract(text, known_modules=known_modules)
    if not item:
        return None
    if kind:
        item["type"] = kind

    quote_n = _norm(item["quote"])
    for old in (getattr(store, "memories", None) or [])[-10:]:
        if _norm(old.get("quote") or "") == quote_n:
            return None                   # 同一句反复说，不刷屏也不刷库

    item["user_id"] = user_id
    store.add_memory(item)
    return item


def recent(memories: list[dict], n: int = 3) -> list[dict]:
    """最该被想起来的几条：他刚说的优先，旁白垫底。

    不做向量检索：路演现场要能一句话解释「为什么想起这件事」。
    """
    items = list(memories or [])
    if not items:
        return []

    def key(m: dict):
        # 他自己说的、且越近越靠前；旁白降权，因为它不是他的话
        return (
            0 if m.get("source") == "user" else 1,
            m.get("days_ago") if m.get("days_ago") is not None else 999,
        )

    return sorted(items, key=key)[:n]
