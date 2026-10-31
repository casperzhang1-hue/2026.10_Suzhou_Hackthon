"""与 A 的 mock-server 对拍（演示数值的唯一事实源）。

期望值不是手算的，是 14:55 同时跑两边、逐字段比对得到的实测值：
    A: cd A-module-frontend/mock-server && node server.js     → :8787
    B: HAMSTER_TODAY=2026-10-31 uvicorn app.main:app --port 8015
    seed: D-module-materials/tools/seed_to_backend.py 转换后的 45 天数据

只要有人改了 service.py 的任何一个系数，这里就会红——这正是它存在的意义：
前端说「踏实 64」、后台说「蔫了 40」，路演现场没法解释。
"""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TODAY = {
    "pet_state": "steady",
    "vitality": 64,
    "user_state": "稳",
    "phrase_level": "good",
    "gap": {"week_target": 5, "week_done": 3, "owed": 2},
    "detail": {
        "duration_minutes": 62,
        "accuracy": 0.57,
        "energy": 90,
        "progress": 57,
        "completion": 0.8,
        "late_night": False,
    },
}


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "seed_to_backend", ROOT / "D-module-materials" / "tools" / "seed_to_backend.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.convert(ROOT / "A-module-frontend" / "seed" / "seed.json")
    (tmp_path / "seed.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(main, "_PINNED_TODAY", "2026-10-31")
    return TestClient(main.create_app(tmp_path))


def test_today_matches_a_mock_server(seeded):
    got = seeded.get("/api/today").json()
    for key, want in EXPECTED_TODAY.items():
        if key == "detail":
            for k, v in want.items():
                assert got["detail"][k] == v, f"detail.{k}: 期望 {v}，实得 {got['detail'][k]}"
        else:
            assert got[key] == want, f"{key}: 期望 {want}，实得 {got[key]}"


def test_memories_match_seed(seeded):
    items = seeded.get("/api/memories").json()["items"]
    assert len(items) == 3
    assert items[0]["days_ago"] == 41
    assert items[0]["quote"] == "资料分析我一定能拿下"
    assert items[0]["then_accuracy"] == 0.73
    assert items[0]["week_accuracy"] == 0.48


def test_upload_today_changes_state_same_as_demo(seeded):
    """上传今日截图（58 分钟 / 30 对 26）后，两边都应变成 steady / 62 / 欠 1。

    ⚠️ 唯一允许的差异：progress。A 的 mock 直接读 record.accuracy，确认卡传 null 时它记 0
    （这是 A 侧待修的 bug）；B 会从 modules 反算 87 并据此判「稳」，比 A 更对。
    """
    before = seeded.get("/api/today").json()
    seeded.post("/api/records", json={
        "record": {"source_app": "粉笔", "event_date": "2026-10-31", "event_time": "21:40",
                   "duration_minutes": 58,
                   "modules": [{"name": "资料分析", "question_count": 30, "correct_count": 26}],
                   "total_questions": 30, "accuracy": None},
        "user_id": "demo_zhang"})
    after = seeded.get("/api/today").json()
    assert after["pet_state"] == "steady" and after["vitality"] == 62
    assert after["gap"]["owed"] == 1
    assert after["detail"]["completion"] == 0.7
    assert after["detail"]["progress"] == 87          # 从 modules 反算，不是 0
    assert after["vitality"] < before["vitality"]     # 学得越多越累，这是设计
