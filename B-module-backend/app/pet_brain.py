"""宠物的脑子：把事实包喂给模型，再把它说的话验一遍。

与 ``pet_chat.py`` 的分工（刻意分开，不是一个东西）：

- ``pet_chat.py``  模板嘴。规则拼装，2ms 返回，永不失败 —— 作为兜底永远保留。
- ``pet_brain.py`` 模型嘴。同一份事实，让模型说人话，但**只许转述、不许生成**。

为什么要三道防线（按成本从低到高）：

1. **prompt 贴语义标签**。同一个「资料分析」在库里能查到三个不同口径的数：
   模块历史累计 62.4%、承诺当时 73%、承诺本周 48%。模型分不清就必然张冠李戴
   （实测 glm-5.3-flash 就把 48% 说成「之前」）。所以 facts 里每个数字都带口径名。
2. **temperature=0.3 + 45 字上限**。压缩发挥空间，短答案的幻觉率显著低于长答案。
3. **输出后两道校验**：数字白名单（防编造）+ 分句归属（防张冠李戴）。
   任一道不过就返回 ``None``，调用方回落 ``pet_chat.reply()``。

路演口径：宁可它说一句笨的模板话，也不能说一句漂亮的假话。
"""
from __future__ import annotations

INTENTS = ("today", "weak", "promise")

# 与 pet_chat.MIN_SAMPLE 保持一致：题量不足不下弱项结论
MIN_SAMPLE = 30

SYSTEM_PROMPT = """你是「仓鼠陪跑」里的学习陪伴仓鼠，陪一个备考公务员的年轻人。

说话方式：
- 全部用中文口语，像一个熟人，不像客服。称呼用「你」，自称用「我」。
- 最多 45 个字，一到两句，不要分点，不要小标题，不要加表情符号。
- 可以有一点点情绪（心疼、得意、不服气），但不要夸张。
- 说到正确率一定要带「%」，说「52%」不要光说「52」。题量、分钟、天数也带上单位。

铁律（违反任何一条都是事故）：
1. 只允许使用 facts 里出现的数字。facts 里没有的数，一个字都不许出现。
2. 不许做任何计算、换算、估算、四舍五入。facts 给的是 60 就直接说 60，不要自己算成 0.6 或六成。
3. 每个数字都带了口径标签，必须按标签说：
   - `accuracy_pct` = 该模块历史累计正确率
   - `accuracy_when_promised_pct` = 他当初说那句话那天的正确率
   - `accuracy_this_week_pct` = 本周正确率
   这三者不可互换。不许把「本周」说成「以前」，也不许把「历史累计」说成「这周」。
4. 引用记忆时必须忠于 quote 的原文意思，不要改写、不要补充他没说过的内容。
5. 如果 facts 不足以回答，就说你记不清或没记下，不要用常识填补。
6. 不要提「数据」「模型」「系统」「facts」这类词，你是仓鼠，不是程序。"""


def _pct(x) -> int | None:
    """0.624 → 62。统一成整数百分比，模型不用做小数换算。"""
    return round(x * 100) if isinstance(x, (int, float)) else None


def _pick_memories(intent: str, memories: list[dict]) -> list[dict]:
    """按意图挑相关记忆。全塞进去会让模型抓错重点，也会拉长 prompt。

    - promise 意图：只给承诺类（它问的就是那句话）
    - weak 意图：只给和模块有关的记忆（承诺里提到了哪个模块）
    - today 意图：给全部，让模型自己挑一件说
    """
    items = list(memories or [])
    if intent == "promise":
        picked = [m for m in items if m.get("type") == "promise"]
        return picked or items[:2]
    if intent == "weak":
        return [m for m in items if m.get("module")] or items[:1]
    return items[:3]


def _memory_view(m: dict) -> dict:
    """记忆的统一形状。detail 是纯文本（如「210 分钟，60 题对 33 题」），
    里面也有数字，同样要能被白名单放过，所以单独抽出来给人看但不参与校验归属。"""
    view = {
        "kind": m.get("type"),
        "days_ago": m.get("days_ago"),
        "quote": m.get("quote"),
    }
    if m.get("module"):
        view["module"] = m["module"]
    then, week = _pct(m.get("then_accuracy")), _pct(m.get("week_accuracy"))
    if then is not None:
        view["accuracy_when_promised_pct"] = then
    if week is not None:
        view["accuracy_this_week_pct"] = week
    if m.get("detail"):
        view["detail"] = m["detail"]
    if m.get("question"):
        view["his_own_question"] = m["question"]
    return view


def build_facts(intent: str, *, today: dict, modules: list[dict], memories: list[dict]) -> dict:
    """拼事实包。所有数字在这一步就定型，模型只负责措辞。

    返回的 dict 会原样进 prompt，也会原样回给前端（前端要拿 facts 做自证）。
    """
    detail = (today or {}).get("detail") or {}
    gap = (today or {}).get("gap") or {}

    facts: dict = {
        "intent": intent,
        "today": {
            "recorded": bool((today or {}).get("has_record")),
            "minutes": int(detail.get("duration_minutes") or 0),
            "accuracy_pct": _pct(detail.get("accuracy")),
            "owed_this_week": gap.get("owed") or 0,
            "week_done": gap.get("week_done") or 0,
            "week_target": gap.get("week_target") or 0,
            "pet_state": (today or {}).get("user_state"),
        },
    }

    # 只保留够样本量的模块，避免「数量关系 100 题」被当成铁证时的口径争议
    pool = [
        {"name": m["module"], "accuracy_pct": _pct(m.get("accuracy")), "questions": m.get("questions")}
        for m in (modules or [])
        if (m.get("questions") or 0) >= MIN_SAMPLE and m.get("accuracy") is not None
    ]
    facts["modules"] = pool
    if pool:
        worst = min(pool, key=lambda m: m["accuracy_pct"])
        best = max(pool, key=lambda m: m["accuracy_pct"])
        facts["weakest_module"] = worst["name"]
        facts["strongest_module"] = best["name"]

    facts["memories"] = [_memory_view(m) for m in _pick_memories(intent, memories)]
    return facts


def allowed_numbers(facts: dict) -> list[int]:
    """事实包里所有出现过的整数 —— 答案里允许出现的数字全集。"""
    out: set[int] = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, bool):
            return
        elif isinstance(node, int):
            out.add(abs(node))
        elif isinstance(node, float):
            out.add(abs(int(round(node))))

    walk(facts)
    # detail 是自由文本（「210 分钟，60 题对 33 题」），里面的数也放行——
    # 但它们的归属不参与下面的分句校验，因为原句本身就是对的。
    for m in facts.get("memories") or []:
        import re

        for n in re.findall(r"\d+", str(m.get("detail") or "")):
            out.add(int(n))
    return sorted(out)


_MODULE_NUM_KEYS = ("accuracy_pct", "accuracy_when_promised_pct", "accuracy_this_week_pct")


def _ownership(facts: dict) -> dict[str, set[int]]:
    """模块名 → 允许和它出现在同一句里的数字。

    这是防「张冠李戴」的关键：判断推理正确率 67%，模型却写成「判断推理 48%」时，
    48 虽然在白名单里（它是资料分析的承诺数字），但因为它不属于判断推理，
    在分句校验里会被抓出来。
    """
    table: dict[str, set[int]] = {}
    for m in facts.get("modules") or []:
        table.setdefault(m["name"], set()).add(m["accuracy_pct"])
    for mem in facts.get("memories") or []:
        name = mem.get("module")
        if not name:
            continue
        nums = {mem.get(k) for k in ("accuracy_when_promised_pct", "accuracy_this_week_pct")}
        table.setdefault(name, set()).update(n for n in nums if n is not None)
    return table


_SPLIT = "。！？；，、\n"


def _clauses(text: str) -> list[str]:
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in _SPLIT:
            if buf.strip():
                out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def check(text: str, facts: dict) -> tuple[bool, str]:
    """两道校验。返回 (通过?, 不通过的原因)。原因只用于日志，不展示给用户。"""
    import re

    if not text or not text.strip():
        return False, "空回答"

    allowed = set(allowed_numbers(facts))
    found = [int(n) for n in re.findall(r"\d+", text)]
    stray = [n for n in found if n not in allowed]
    if stray:
        return False, f"出现事实包里没有的数字 {stray}"

    # 分句归属：一句话里点了某个模块名，这句话里的百分比必须是这个模块的
    own = _ownership(facts)
    pct_nums = {n for nums in own.values() for n in nums}
    for clause in _clauses(text):
        named = [name for name in own if name in clause]
        if len(named) != 1:
            continue  # 没提模块，或一句话点两个模块（比较句），跳过
        nums = {int(n) for n in re.findall(r"\d+", clause)}
        misplaced = {n for n in nums if n in pct_nums and n not in own[named[0]]}
        if misplaced:
            return False, f"「{named[0]}」被安上了别人的数字 {sorted(misplaced)}"
    return True, ""


def context(intent: str, *, today: dict, modules: list[dict], memories: list[dict]) -> dict:
    """给前端的完整上下文：事实包 + 数字白名单 + 给模型的人和问题。

    前端拿这个去调模型，调完自己跑一遍 check()，不过就回落到 /api/pet/chat 的模板。
    """
    facts = build_facts(intent, today=today, modules=modules, memories=memories)
    questions = {
        "today": "今天学得怎么样？",
        "weak": "我哪里最毛（最弱）？",
        "promise": "我之前答应过的那件事，现在怎么样了？",
    }
    return {
        "ok": True,
        "intent": intent,
        "question": questions.get(intent, "今天学得怎么样？"),
        "facts": facts,
        "allowed_numbers": allowed_numbers(facts),
        "system_prompt": SYSTEM_PROMPT,
        "topics": list(INTENTS),
    }
