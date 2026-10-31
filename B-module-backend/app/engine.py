"""状态引擎：A 原型 computeDailyState 的逐行移植。

纯函数：同样输入永远同样输出，不读时间、不读随机数、不改入参。
对拍依据 tests/golden.json（由 tools/gen_golden.mjs 从原型 JS 生成）。
"""
import math


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _js_round(x):
    # JS Math.round 的 .5 向正无穷取整；Python 内置 round 是银行家舍入，结果会不一致
    return math.floor(x + 0.5)


def _r1(v):
    return _js_round(v * 10) / 10


def compute_vitality(prev, completion):
    """非对称：表现差(<0.5)只掉一点，表现好(>=0.5)立刻涨。"""
    c = _clamp(completion, 0, 1.2)
    if c < 0.5:
        nxt = 0.75 * prev + 0.25 * (c * 100)
    else:
        nxt = 0.60 * prev + 0.40 * (c * 100)
    return math.floor(_clamp(nxt, 0, 100))


def pet_state_of(v, energy, minutes, missed_days):
    if missed_days >= 7:
        return "sleep"
    if minutes >= 200 and energy < 45 and v >= 52:  # 学太猛，反而是劝停
        return "tired"
    if v >= 78:
        return "vigour"
    if v >= 55:
        return "steady"
    if v >= 30:
        return "wilt"
    return "sleep"


def user_state_of(energy, progress):
    if energy < 40 and progress < 45:
        return "崩溃前兆"
    if energy < 40 and progress >= 45:
        return "过载"
    if energy >= 40 and progress < 45:
        return "平台期"
    return "稳"


def compute_daily_state(prev_vitality, completion, energy, progress, minutes=0, missed_days=0):
    minutes = max(0, minutes or 0)
    v = compute_vitality(prev_vitality, completion)
    return {
        "completion": _r1(completion),
        "net_minutes": _js_round(minutes),
        "energy": _js_round(energy),
        "progress": _js_round(progress),
        "prev_vitality": _js_round(prev_vitality),
        "vitality": v,
        "user_state": user_state_of(energy, progress),
        "pet_state": pet_state_of(v, energy, minutes, missed_days or 0),
    }
