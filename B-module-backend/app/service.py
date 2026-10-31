"""由记录推导每日信号，并回放出今日状态。全部是纯函数，today 参数由调用方传入。

信号推导（signals_of）是 A 原型 finalizePayload 的移植，保持同一口径：
  completion = 正确率；缺失时按时长/60 兜底，夹在 [0, 1.2]
  energy     = 过载 32；否则有正确率 55+acc*30；否则 58
  progress   = 60（原型常量）
"""
from datetime import date, timedelta

from .engine import compute_daily_state

WEEK_TARGET = 5          # 每周目标天数（原型未定义，此处为后端暂定值，待与 D/A 确认）
INITIAL_VITALITY = 50    # 新用户
SLEEP_AFTER_DAYS = 7     # 与引擎 petStateOf 的休眠阈值一致

PHRASE_LEVEL = {"vigour": "excellent", "steady": "good", "tired": "low", "wilt": "low", "sleep": "low"}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _accuracy(rec: dict):
    acc = rec.get("accuracy")
    if isinstance(acc, (int, float)):
        return acc
    mods = rec.get("modules") or []
    asked = sum(m["question_count"] for m in mods if m.get("correct_count") is not None)
    right = sum(m["correct_count"] for m in mods if m.get("correct_count") is not None)
    return right / asked if asked else None


def signals_of(rec: dict) -> dict:
    minutes = rec.get("duration_minutes") or 0
    total = rec.get("total_questions") or 0
    acc = _accuracy(rec)
    overloaded = minutes > 200 or (total > 80 and acc is not None and acc < 0.55)
    completion = _clamp(acc if acc is not None else minutes / 60, 0, 1.2)
    energy = 32 if overloaded else (55 + acc * 30 if acc is not None else 58)
    return {"completion": completion, "energy": energy, "progress": 60, "minutes": minutes}


def _by_day(records: list[dict]) -> dict[date, list[dict]]:
    days: dict[date, list[dict]] = {}
    for r in records:
        d = r.get("event_date")
        if d:
            days.setdefault(date.fromisoformat(str(d)), []).append(r)
    return days


def _merge_day(recs: list[dict]) -> dict:
    """同一天多条记录：时长相加，其余信号取各自推导后的时长加权。"""
    sigs = [signals_of(r) for r in recs]
    minutes = sum(s["minutes"] for s in sigs)
    w = [(s["minutes"] or 1) if minutes else 1 for s in sigs]
    return {
        "completion": sum(s["completion"] * wi for s, wi in zip(sigs, w)) / sum(w),
        "energy": min(s["energy"] for s in sigs),     # 任何一次过载都算当天过载
        "progress": 60,
        "minutes": minutes,
    }


def replay(records: list[dict], today: date) -> dict:
    """从第一条记录起逐日回放，返回"现在该显示的状态"。

    ⚠️ 今天没记录时不结算今天（settle_to = 昨天）。
    一天还没过完就按 completion=0 结算，等于每天早上打开 App 宠物都是「蔫了」——
    这正是产品明令禁止的惩罚式反馈（PRD 05 反焦虑护栏）。今天一有记录入库，
    下一次调用就会把今天算进来。
    """
    days = _by_day(records)
    if not days:
        return {"state": None, "last_study": None, "missed_days": None, "settled_to": None}
    pending_today = today not in days
    settle_to = today - timedelta(days=1) if pending_today else today
    vitality = INITIAL_VITALITY
    missed = 0
    state = None
    d = min(days)
    while d <= settle_to:
        if d in days:
            sig = _merge_day(days[d])
            missed = 0
        else:
            # 没记录的日子：完成度 0，精力沿用中性值，时长 0（原型 'none' 预设：0.08/55/60）
            sig = {"completion": 0.0, "energy": 55, "progress": 60, "minutes": 0}
            missed += 1
        state = compute_daily_state(
            prev_vitality=vitality, completion=sig["completion"], energy=sig["energy"],
            progress=sig["progress"], minutes=sig["minutes"], missed_days=missed,
        )
        vitality = state["vitality"]
        d += timedelta(days=1)
    # 对外汇报的「连续没学天数」把今天算进去（今天确实还没学），但状态本身按已结算的日子算
    reported_missed = missed + (1 if pending_today else 0)
    return {"state": state, "last_study": max(k for k in days if k <= today),
            "missed_days": reported_missed, "settled_to": settle_to}


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def gap_of(records: list[dict], today: date) -> dict:
    """本周缺口 = 目标天数 - 本周**真的学了**的天数。

    ⚠️ 只数有时长的日子。seed 里 10-27 / 10-29 是「本周没学」（时长 0），
    按"有记录就算完成"会算成全勤、owed=0，演示里那句「本周欠 2 次」就没了。
    """
    start = _week_start(today)
    studied = {
        d for d, recs in _by_day(records).items()
        if start <= d <= today and _merge_day(recs)["minutes"] > 0
    }
    done = len(studied)
    return {"week_target": WEEK_TARGET, "week_done": done, "owed": max(0, WEEK_TARGET - done)}


def today_view(records: list[dict], today: date) -> dict:
    r = replay(records, today)
    days = _by_day(records)
    st = r["state"]
    if st is None:
        # 新用户：没有任何记录
        return {"date": today.isoformat(), "has_record": False, "pet_state": "sleep", "vitality": INITIAL_VITALITY,
                "user_state": None, "phrase_level": "normal", "gap": gap_of(records, today),
                "pending_today": True, "missed_days": 0}
    return {
        "date": today.isoformat(),
        "has_record": today in days,
        "pending_today": today not in days,
        "pet_state": st["pet_state"],
        "vitality": st["vitality"],
        "user_state": st["user_state"],
        "phrase_level": PHRASE_LEVEL[st["pet_state"]],
        "gap": gap_of(records, today),
        "missed_days": r["missed_days"],
    }
