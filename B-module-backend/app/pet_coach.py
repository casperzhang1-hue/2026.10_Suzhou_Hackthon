"""团团的判断：他今晚该不该再学。

为什么要单独一个模块——之前它只会安慰，因为事实包里只有数字、没有结论。
「再学 20 分钟」和「够了去睡」是两件相反的事。让模型自己从 82 分钟里推，
它必然挑那句听着最贴心的；那不是判断，是顺着他说。而一个只会顺着说的宠物，
问他「今天还用学吗」得到的永远是「你辛苦了」——这就是用户说的「呆」。

所以结论先在这里算好，模型只负责把它说成一只仓鼠的话。
**这里不许出现「差不多」「看情况」**：拿主意是这只宠物的活儿，
不是把选择权再推回给他。

口径全部沿用 ``service``，一个数都不发明：
- 日达标线 80 分钟（``service`` 里 ``completion = 时长 / 80``）
- 周目标 5 天（``WEEK_TARGET``），``owed`` 只数真的学过的日子
- 熬夜、精力、弱项样本量（``MIN_SAMPLE``）同样照抄
"""
from __future__ import annotations

import os
from datetime import datetime

from .pet_brain import MIN_SAMPLE

# 与 service 的达标线一致。改这里必须同步改 service，否则「今天够了」会和首页打架
DAILY_MINUTES = 80

# 正确率低于这个数，再加时长只是把错的做法练得更熟
ROUGH_ACCURACY = 50

# 精力低于这个数就别谈计划了，人已经没油了
LOW_ENERGY = 25

# 晚于这个点，给的是「就做 20 分钟」，不再是「补满 80」
LATE_HOUR = 21

# 过了这个点还没达标，就别开新账
CUTOFF_HOUR = 23

VERDICTS = ("keep", "stop", "start", "switch")


def now_hour() -> int:
    """当前几点。演示时可用 ``HAMSTER_HOUR=22`` 钉死，避免现场时间漂移改结论。"""
    pinned = (os.environ.get("HAMSTER_HOUR") or "").strip()
    if pinned.isdigit() and 0 <= int(pinned) <= 23:
        return int(pinned)
    return datetime.now().hour


def _weakest(modules: list[dict] | None) -> str | None:
    """题量够的模块里，正确率最低的那个。样本不足不下结论——这是全项目的口径。"""
    pool = [
        (m.get("accuracy"), m.get("module"))
        for m in (modules or [])
        if (m.get("questions") or 0) >= MIN_SAMPLE and m.get("accuracy") is not None
    ]
    if not pool:
        return None
    return min(pool)[1]


def _grade(acc_pct: int | None) -> str:
    """今天的手感。没有正确率就是「不知道」——不猜，也不拿历史累计冒充今天。"""
    if acc_pct is None:
        return "unknown"
    if acc_pct >= 60:
        return "good"
    if acc_pct >= ROUGH_ACCURACY:
        return "ok"
    return "rough"


def judge(*, today: dict, hour: int | None = None, modules: list[dict] | None = None,
          sad: bool = False) -> dict:
    """给他一个明确的判断。返回的东西会进 facts，模型只能照着它说。

    字段里所有数字都是 int，会被 ``pet_brain.allowed_numbers`` 收进白名单，
    所以模型念得出「20 分钟」，但念不出「25 分钟」——那个数是它自己编的。
    """
    h = now_hour() if hour is None else hour
    detail = (today or {}).get("detail") or {}
    gap = (today or {}).get("gap") or {}
    minutes = int(detail.get("duration_minutes") or 0)
    raw_acc = detail.get("accuracy")
    acc_pct = round(raw_acc * 100) if isinstance(raw_acc, (int, float)) else None
    energy = detail.get("energy")
    late = bool(detail.get("late_night"))
    owed = int(gap.get("owed") or 0)
    weak = _weakest(modules)
    has_record = bool((today or {}).get("has_record")) and minutes > 0

    base = {
        "hour": h,
        "today_minutes": minutes,
        "line": DAILY_MINUTES,
        "owed": owed,
        "accuracy_pct": acc_pct,
        "grade": _grade(acc_pct),
        "weakest": weak,
    }

    def out(verdict: str, *, action: str, why: str, tone: str = "firm",
            minutes_=None, module=None, **extra) -> dict:
        assert verdict in VERDICTS
        item = {**base, **extra}
        item.update({
            "verdict": verdict,
            "action": action,
            "why": why,
            "tone": tone,
        })
        if minutes_ is not None:
            item["again_minutes"] = int(minutes_)
        if module:
            item["module"] = module
        return item

    # ① 他难受。这是唯一能压过所有数据的一条：这时候谈计划，是把安慰说成了任务
    if sad:
        return out("stop", action="别学了，先去歇着", tone="gentle",
                   why="他今天难受，这时候劝学是错的")

    # ② 今天还没开始
    if not has_record:
        if h >= CUTOFF_HOUR or h < 5:
            return out("stop", action="今天就这样吧，去睡", tone="gentle",
                       why="这个点再开新账，明天只会更累")
        # 起手目标要小。让他「做 15 分钟」永远比「补满 80」启动得了
        first = 10 if h >= LATE_HOUR else 15
        return out("start", action=f"先做 {first} 分钟", minutes_=first, tone="gentle",
                   why="今天还没有记录，开个头就行")

    left = max(0, DAILY_MINUTES - minutes)

    # ③ 已经够了。够了就是够了，再加时长不加分，只加疲劳
    if minutes >= DAILY_MINUTES:
        if base["grade"] == "rough" and weak:
            return out("switch", action=f"别再堆时长了，回去看 {weak} 的错题",
                       module=weak,
                       why=f"今天 {minutes} 分钟够了，但正确率只有 {acc_pct}%，再加题量只是把错的做法练熟")
        if owed > 0:
            # 理由里必须带真数。只说「今天够了」，他没法判断你是不是在敷衍他
            return out("stop", action="今天够了，剩下的明天补", tone="gentle",
                       why=f"今天 {minutes} 分钟，过了 {DAILY_MINUTES} 的线；本周还差 {owed} 天，明天补得上")
        return out("stop", action="今天够了，去歇着", tone="gentle",
                   why=f"今天 {minutes} 分钟，过了 {DAILY_MINUTES} 的线，这周也清了")

    # ④ 没达标。这时候才轮到「再来一点」——但要看时间和今天的手感
    if h >= CUTOFF_HOUR or h < 5:
        return out("stop", action="太晚了，剩下的明天补", tone="gentle",
                   why=f"今天 {minutes} 分钟，离 {DAILY_MINUTES} 还差 {left}，但这个点学进去留不住",
                   short_by=left)

    if late:
        return out("stop", action="别再加了，今天已经熬过一回", tone="gentle",
                   why="今天有过熬夜，再堆时长是在透支明天", short_by=left)

    if base["grade"] == "rough" and weak and minutes >= 30:
        return out("switch", action=f"别刷新题了，回去看 {weak} 的错题",
                   module=weak,
                   why=f"今天 {minutes} 分钟，正确率只有 {acc_pct}%，再加题量只是重复错的做法",
                   short_by=left)

    if isinstance(energy, (int, float)) and energy < LOW_ENERGY:
        return out("stop", action="你今天耗得差不多了，去睡", tone="gentle",
                   why="精力已经见底，这时候学是硬撑", short_by=left)

    # 剩下的时间按点给：21 点后只给 20，避免一句「再学 80 分钟」把人劝退
    cap = 20 if h >= LATE_HOUR else 40
    again = min(cap, left)
    return out("keep", action=f"再 {again} 分钟", minutes_=again,
               why=f"今天 {minutes} 分钟，离 {DAILY_MINUTES} 还差 {left}，先补 {again} 分钟就行",
               short_by=left)


_OPENERS = {
    "keep": [
        "那就再来 {n} 分钟，我陪你数着。",
        "{n} 分钟，做完咱就收工。",
        "我把瓜子收起来了，先做 {n} 分钟。",
    ],
    "start": [
        "先做 {n} 分钟，开了头就不难了。",
        "就 {n} 分钟，我趴这儿等你。",
    ],
    "stop": [
        "今天到这儿吧，明天再接着来。",
        "收工吧，剩下的明天补。",
    ],
    "switch": [
        "别刷新题了，回去看看错的那几道。",
        "换个轻的，回去翻翻错题。",
    ],
}


def fallback(*, verdict: str, again_minutes: int | None = None, seed: str = "") -> str:
    """模型不在时的判断话术。

    和其它兜底一样：只说算出来的结论，不评价他这个人，不带任何编造的细节。
    这是「宠物不智能」的最后一道保险——哪怕模型挂了，他问「今天还用学吗」
    也得有个明确答复，而不是一句「我在呢」。
    """
    pool = _OPENERS.get(verdict) or _OPENERS["stop"]
    line = pool[len(seed or "") % len(pool)]
    if "{n}" in line:
        if not again_minutes:
            return "今天就到这儿吧，明天再接着来。"
        line = line.replace("{n}", str(int(again_minutes)))
    return line
