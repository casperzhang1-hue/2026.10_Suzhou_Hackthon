"""D 的集成回归测试：锁住两个「演示会当场翻车」的坑。

这两条不是 B 的原始设计，是合并分支后实测发现的行为缺口，补丁写在 app/service.py：

1. gap 只数**真的学了**的天（时长 > 0）。seed 里 10-27 / 10-29 是「本周没学」，
   旧口径会把它们算成完成 → owed=0 → 演示里最有力的那句「本周欠 2 次」消失。
2. 今天还没记录时**不结算今天**（回放到昨天）。旧口径每天 0 点就把今天按
   completion=0 记账，等于早上打开 App 宠物永远是「蔫了」——正是反焦虑护栏禁止的。
"""
import json
from datetime import date

from fastapi.testclient import TestClient

from app import main


def _rec(date_str, minutes=58, correct=26, total=30):
    return {
        "record": {
            "source_app": "粉笔", "event_date": date_str, "event_time": "21:40",
            "duration_minutes": minutes,
            "modules": [{"name": "资料分析", "question_count": total, "correct_count": correct}],
            "total_questions": total, "accuracy": None,
        },
        "user_id": "demo_zhang",
    }


def _client(tmp_path, monkeypatch, today="2026-10-31"):
    monkeypatch.setattr(main, "_PINNED_TODAY", today)
    return TestClient(main.create_app(tmp_path))


def test_gap_ignores_zero_minute_days(tmp_path, monkeypatch):
    """「记录了但没学」不能抵掉缺口。"""
    c = _client(tmp_path, monkeypatch)
    for d in ("2026-10-26", "2026-10-28", "2026-10-30"):
        assert c.post("/api/records", json=_rec(d)).status_code == 200
    for d in ("2026-10-27", "2026-10-29"):
        # 时长 0 的「没学」记录：入库成功，但不该算完成
        assert c.post("/api/records", json=_rec(d, minutes=0)).status_code == 200

    gap = c.get("/api/today").json()["gap"]
    assert gap["week_done"] == 3, gap
    assert gap["owed"] == 2, gap          # ← 演示那句「本周欠 2 次」


def test_today_not_settled_before_any_record(tmp_path, monkeypatch):
    """今天还没学，显示的应是昨天结算出来的状态，不是按 0 分扣过的。"""
    c = _client(tmp_path, monkeypatch)
    for d in ("2026-10-28", "2026-10-30"):
        c.post("/api/records", json=_rec(d))

    body = c.get("/api/today").json()
    assert body["has_record"] is False
    assert body["pending_today"] is True
    assert body["pet_state"] != "sleep"
    assert body["vitality"] > 0

    # 今天补上记录后，状态立刻算进来
    c.post("/api/records", json=_rec("2026-10-31"))
    after = c.get("/api/today").json()
    assert after["has_record"] is True and after["pending_today"] is False
    assert after["vitality"] >= body["vitality"]


def test_seed_shape_converter_roundtrip(tmp_path, monkeypatch):
    """A 的 seed（days）经转换脚本后，B 能读出 44 条记录 + 3 条记忆。"""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "seed_to_backend", root / "D-module-materials" / "tools" / "seed_to_backend.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out = mod.convert(root / "A-module-frontend" / "seed" / "seed.json")
    assert len(out["records"]) == 44
    assert len(out["memories"]) == 3
    assert out["records"][0]["event_date"] == "2026-09-17"

    (tmp_path / "seed.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    c = _client(tmp_path, monkeypatch)
    body = c.get("/api/today").json()
    assert body["gap"]["owed"] == 2
    assert body["pet_state"] in {"vigour", "steady", "wilt", "tired"}
    assert len(c.get("/api/memories").json()["items"]) == 3


def test_replay_is_date_stable(tmp_path, monkeypatch):
    """同一个 seed + 同一个 today，反复请求结果一致（现场可复算）。"""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "seed_to_backend", root / "D-module-materials" / "tools" / "seed_to_backend.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.convert(root / "A-module-frontend" / "seed" / "seed.json")
    (tmp_path / "seed.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    c = _client(tmp_path, monkeypatch)
    first = c.get("/api/today").json()
    for _ in range(3):
        assert c.get("/api/today").json() == first
