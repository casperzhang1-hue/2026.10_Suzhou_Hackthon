"""由记录推导每日信号，并回放出今日状态。全部是纯函数，today 参数由调用方传入。

⚠️ 口径与 A 的 `A-module-frontend/mock-server` **完全一致**——那是演示数值的唯一事实源。
如果这里另算一套，前端说「踏实 64」、后台说「蔫了 40」，路演现场没法解释。
对拍命令见 tests/test_parity_a.py。

  completion = min(1.2, 当日时长 / 80)          # 80 分钟算达标
  energy     = 100 - 时长/6，熬夜 -30，夹 [0,100]  # 学越多越累，熬夜重罚
  progress   = round(正确率 × 100)
  vitality   = 新用户起点 30，逐日非对称累积

今天还没记录时**不结算今天**：把最近一次真学的那天原样再算一遍（A 的 display 口径），
否则每天 0 点就把今天按 0 分记账，等于早上打开 App 宠物永远「蔫了」。
"""
from datetime import date, timedelta

from .engine import compute_daily_state

WEEK_TARGET = 5          # 每周目标天数（与 A 的 seed.gap.week_target 一致）
INITIAL_VITALITY = 30    # 新用户起点，与 A 原型 rollPrevVitality 一致
SLEEP_AFTER_DAYS = 7     # 与引擎 pet_state_of 的休眠阈值一致

PHRASE_LEVEL = {"vigour": "excellent", "steady": "good", "tired": "low", "wilt": "low", "sleep": "low"}

# 没有记录的一天：完成度 0、精力满格（没学就不累）、正确率记 0
_IDLE_SIGNALS = {"minutes": 0, "completion": 0.0, "energy": 100, "progress": 0}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _js_round(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def accuracy_of(rec: dict):
    """优先取识别出的 accuracy；没有就用 modules 的正确数/题量算。"""
    acc = rec.get("accuracy")
    if isinstance(acc, (int, float)):
        return acc
    mods = rec.get("modules") or []
    asked = sum(m.get("question_count") or 0 for m in mods if m.get("correct_count") is not None)
    right = sum(m.get("correct_count") or 0 for m in mods if m.get("correct_count") is not None)
    return right / asked if asked else None


def is_late_night(start_time, end_time, minutes: int) -> bool:
    """熬夜：结束时间落在 0–6 点，或 22 点后开刷且超过 90 分钟。与 A 的 isLateNight 同逻辑。"""
    def hour(t):
        if not t:
            return None
        try:
            return int(str(t).split(":")[0])
        except ValueError:
            return None

    eh = hour(end_time)
    if eh is not None and 0 <= eh < 6:
        return True
    sh = hour(start_time) if start_time else 21
    return sh is not None and sh >= 22 and minutes > 90


def signals_of(rec: dict) -> dict:
    """单条记录 → 当日信号（A 的 finalizePayload 口径）。"""
    minutes = rec.get("duration_minutes") or 0
    acc = accuracy_of(rec)
    late = is_late_night(rec.get("event_time"), rec.get("end_time"), minutes)
    return {
        "minutes": minutes,
        "completion": min(1.2, minutes / 80),
        "energy": _js_round(_clamp(100 - minutes / 6 - (30 if late else 0), 0, 100)),
        "progress": _js_round((acc or 0) * 100),
        "accuracy": acc,
        "late_night": late,
    }


def _by_day(records: list[dict]) -> dict[date, list[dict]]:
    days: dict[date, list[dict]] = {}
    for r in records:
        d = r.get("event_date")
        if d:
            days.setdefault(date.fromisoformat(str(d)), []).append(r)
    return days


def _day_signals(recs: list[dict]) -> dict:
    """同一天多条记录：时长相加、正确率按题量加权（A 只取最后一条，这里更准但不改口径形态）。"""
    sigs = [signals_of(r) for r in recs]
    minutes = sum(s["minutes"] for s in sigs)
    weights = [max(s["minutes"], 1) for s in sigs]
    acc_vals = [(s["accuracy"], w) for s, w in zip(sigs, weights) if s["accuracy"] is not None]
    acc = (sum(a * w for a, w in acc_vals) / sum(w for _, w in acc_vals)) if acc_vals else None
    return {
        "minutes": minutes,
        "completion": min(1.2, minutes / 80),
        "energy": _js_round(_clamp(100 - minutes / 6 - (30 if any(s["late_night"] for s in sigs) else 0), 0, 100)),
        "progress": _js_round((acc or 0) * 100),
        "accuracy": acc,
        "late_night": any(s["late_night"] for s in sigs),
    }


def replay(records: list[dict], today: date) -> dict:
    """逐日回放，返回"现在该显示的状态"。

    今天有记录 → 结算到今天；今天没记录 → 只结算到昨天，展示时把最近一次真学的那天
    原样再算一遍（与 A 的 /api/today 一致，保证两边数字同一个）。
    """
    days = _by_day(records)
    if not days:
        return {"state": None, "last_study": None, "missed_days": 0, "settled_to": None, "signals": None}

    pending_today = today not in days
    vitality = INITIAL_VITALITY
    missed = 0
    state = None
    last_study_sig = None
    d = min(days)
    # 最后一天要结算到哪里：今天有记录就含今天，否则停在昨天
    settle_to = today if not pending_today else today - timedelta(days=1)
    while d <= settle_to:
        sig = _day_signals(days[d]) if d in days else _IDLE_SIGNALS
        if sig["minutes"] > 0:
            last_study_sig = sig
            missed = 0
        else:
            missed += 1
        state = compute_daily_state(
            prev_vitality=vitality, completion=sig["completion"], energy=sig["energy"],
            progress=sig["progress"], minutes=sig["minutes"], missed_days=missed,
        )
        vitality = state["vitality"]
        d += timedelta(days=1)

    if pending_today:
        # 今天还没学：用最近一次真学的那天作为展示态（A 的 display 口径）
        if last_study_sig is None:
            return {"state": state, "last_study": None, "missed_days": missed,
                    "settled_to": settle_to, "signals": None}
        today_missed = missed + 1         # 今天确实还没学
        state = compute_daily_state(
            prev_vitality=vitality, completion=last_study_sig["completion"],
            energy=last_study_sig["energy"], progress=last_study_sig["progress"],
            minutes=last_study_sig["minutes"], missed_days=today_missed,
        )
        return {"state": state, "last_study": max(k for k in days if k <= today),
                "missed_days": today_missed, "settled_to": settle_to, "signals": last_study_sig}

    return {"state": state, "last_study": max(k for k in days if k <= today),
            "missed_days": missed, "settled_to": settle_to,
            "signals": _day_signals(days[today])}


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def gap_of(records: list[dict], today: date) -> dict:
    """本周缺口 = 目标天数 - 本周**真的学了**的天数（时长 > 0）。

    ⚠️ 只数有时长的日子。seed 里 10-27 / 10-29 是「本周没学」（时长 0），
    按"有记录就算完成"会算成全勤、owed=0，演示里那句「本周欠 2 次」就没了。
    """
    start = _week_start(today)
    studied = {
        d for d, recs in _by_day(records).items()
        if start <= d <= today and _day_signals(recs)["minutes"] > 0
    }
    done = len(studied)
    return {"week_target": WEEK_TARGET, "week_done": done, "owed": max(0, WEEK_TARGET - done)}


def today_view(records: list[dict], today: date) -> dict:
    r = replay(records, today)
    days = _by_day(records)
    st = r["state"]
    if st is None:
        return {"date": today.isoformat(), "has_record": False, "pending_today": True,
                "pet_state": "sleep", "vitality": INITIAL_VITALITY, "user_state": None,
                "phrase_level": "normal", "gap": gap_of(records, today),
                "missed_days": 0, "detail": None}
    sig = r["signals"] or {}
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
        "detail": {
            "duration_minutes": sig.get("minutes", 0),
            "accuracy": sig.get("accuracy"),
            "energy": st["energy"],
            "progress": st["progress"],
            "completion": st["completion"],
            "late_night": sig.get("late_night", False),
        },
    }
