"""宠物的「嘴」：把数据库里的真实数字拼成人话。

三条硬规则：

1. **每个数字都能溯源**。回答里的时长、正确率、缺口、承诺日期，全部来自
   ``service.today_view`` / ``db.module_stats`` / ``memories``，函数不自己造数。
2. **取不到就说取不到**。宁可回一句「这个我没记下」，也不编一个像样的数字——
   路演现场被追问「这个 48% 哪来的」时必须能点开接口自证。
3. **不做自由生成**。模板 + 真实数据，2 毫秒返回。这是刻意的：识别那一步已经
   依赖了外部模型（且实测有非确定性），宠物这张嘴不能再赌一次网络。
"""
from __future__ import annotations

INTENTS = ("today", "weak", "promise")

# 弱项统计的最小样本量：低于这个题量不给结论，避免「只做了 3 题」被说成弱项
MIN_SAMPLE = 30


def _pct(x: float | None) -> str:
    return f"{round(x * 100)}%" if isinstance(x, (int, float)) else "—"


def answer_today(today: dict) -> dict:
    gap = (today.get("gap") or {}).get("owed") or 0
    detail = today.get("detail") or {}
    facts = {"has_record": bool(today.get("has_record")), "owed": gap}

    if not today.get("has_record"):
        text = (f"今天还没看到你的截图。这周还欠 {gap} 次。" if gap
                else "今天还没打卡。这周的账我记着，不催你。")
        return {"text": text, "facts": facts}

    minutes = int(detail.get("duration_minutes") or 0)
    acc = detail.get("accuracy")
    facts.update({"minutes": minutes, "accuracy": acc})
    head = f"今天 {minutes} 分钟" + (f"，正确率 {_pct(acc)}。" if acc is not None else "，正确率没识别出来。")
    tail = f"这周还欠 {gap} 次。" if gap else "这周已经平了。"
    return {"text": head + tail, "facts": facts}


def answer_weak(modules: list[dict]) -> dict:
    pool = [m for m in modules if (m.get("questions") or 0) >= MIN_SAMPLE and m.get("accuracy") is not None]
    if not pool:
        return {"text": "题量还太少，我先不下结论。再多给我几张截图。",
                "facts": {"modules": len(modules or [])}}
    worst = min(pool, key=lambda m: m["accuracy"])
    best = max(pool, key=lambda m: m["accuracy"])
    text = (f"「{worst['module']}」是最毛的一块，{_pct(worst['accuracy'])}，{worst['questions']} 题。"
            f"「{best['module']}」你自己都没发现吧，{_pct(best['accuracy'])}。")
    facts = {"worst": worst["module"], "worst_accuracy": worst["accuracy"],
             "best": best["module"], "best_accuracy": best["accuracy"],
             "sample": worst["questions"]}
    return {"text": text, "facts": facts}


def answer_promise(memories: list[dict]) -> dict:
    promises = [m for m in (memories or []) if m.get("type") == "promise"]
    if not promises:
        return {"text": "你还没跟我说过什么非做成不可的事。说一句，我记着。", "facts": {"promises": 0}}
    m = max(promises, key=lambda x: x.get("days_ago") or 0)
    then, week = m.get("then_accuracy"), m.get("week_accuracy")
    days = m.get("days_ago")
    quote = m.get("quote") or ""
    facts = {"id": m.get("id"), "days_ago": days, "then_accuracy": then,
             "week_accuracy": week, "module": m.get("module")}

    if not isinstance(then, (int, float)) or not isinstance(week, (int, float)):
        text = f"{days} 天前你说「{quote}」。这句话我一直记着。"
        return {"text": text, "facts": facts}

    if week >= then:
        text = f"{days} 天前你说「{quote}」，那时候 {_pct(then)}，这周 {_pct(week)}。你说到做到。"
    else:
        text = (f"{days} 天前你说「{quote}」，那时候 {_pct(then)}，这周 {_pct(week)}。"
                f"我不是要你解释，我只是记着。")
    if m.get("question"):
        facts["question"] = m["question"]
    return {"text": text, "facts": facts}


def reply(intent: str, *, today: dict, modules: list[dict], memories: list[dict]) -> dict:
    """把意图路由到对应回答。未知意图不硬答，反问回去。"""
    intent = (intent or "").strip().lower()
    if intent == "today":
        body = answer_today(today or {})
    elif intent == "weak":
        body = answer_weak(modules or [])
    elif intent == "promise":
        body = answer_promise(memories or [])
    else:
        return {"ok": False, "intent": intent, "text": "这个我答不上来。你问我今天学得怎么样？",
                "facts": {}, "topics": list(INTENTS), "source": "rules"}
    return {"ok": True, "intent": intent, "text": body["text"], "facts": body["facts"],
            "topics": list(INTENTS), "source": "rules"}
