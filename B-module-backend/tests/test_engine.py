import copy
import json
from pathlib import Path

import pytest

from app.engine import compute_daily_state

GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text(encoding="utf-8"))

KEY_MAP = {"prevVitality": "prev_vitality", "missedDays": "missed_days"}
OUT_MAP = {"netMinutes": "net_minutes", "prevVitality": "prev_vitality",
           "userState": "user_state", "petState": "pet_state"}


def _snake(d, mapping):
    return {mapping.get(k, k): v for k, v in d.items()}


@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_matches_prototype_js(case):
    """与 A 原型 JS 输出逐字段一致（含越界、临界等怪异边界）。"""
    got = compute_daily_state(**_snake(case["input"], KEY_MAP))
    assert got == _snake(case["expected"], OUT_MAP)


# ---- 任务卡要求的 6 个场景：语义断言，不依赖 golden ----

def test_normal():
    r = compute_daily_state(prev_vitality=70, completion=0.8, energy=70, progress=68, minutes=58)
    assert (r["pet_state"], r["user_state"]) == ("steady", "稳")


def test_missed_one_day_only_drops_a_little():
    r = compute_daily_state(prev_vitality=70, completion=0, energy=62, progress=60, minutes=0, missed_days=1)
    assert r["vitality"] == 52          # 70 -> 52，不是归零
    assert r["pet_state"] == "wilt"


def test_missed_seven_days_sleeps():
    r = compute_daily_state(prev_vitality=40, completion=0, energy=50, progress=50, minutes=0, missed_days=7)
    assert r["pet_state"] == "sleep"


def test_overload_says_stop():
    r = compute_daily_state(prev_vitality=75, completion=1.2, energy=31, progress=58, minutes=372)
    assert (r["pet_state"], r["user_state"]) == ("tired", "过载")


def test_comeback_gains_more_than_miss_loses():
    miss = compute_daily_state(prev_vitality=70, completion=0, energy=62, progress=60)
    back = compute_daily_state(prev_vitality=25, completion=0.93, energy=70, progress=68, minutes=58)
    assert 70 - miss["vitality"] < back["vitality"] - 25   # 掉 18，涨 27


def test_new_user_default_vitality_50():
    r = compute_daily_state(prev_vitality=50, completion=0.6, energy=60, progress=50, minutes=30)
    assert r["vitality"] == 54


def test_pure_same_input_same_output_and_input_untouched():
    kwargs = dict(prev_vitality=63.0, completion=0.77, energy=51.5, progress=47, minutes=33, missed_days=2)
    snapshot = copy.deepcopy(kwargs)
    assert compute_daily_state(**kwargs) == compute_daily_state(**kwargs)
    assert kwargs == snapshot
