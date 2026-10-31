import json

import pytest
from fastapi.testclient import TestClient

from app import main


def _payload(date_str, minutes=58, correct=26, total=30, edited=None, user_id="demo_zhang"):
    return {
        "record": {
            "source_app": "粉笔", "event_date": date_str, "event_time": "21:40",
            "duration_minutes": minutes,
            "modules": [{"name": "资料分析", "question_count": total, "correct_count": correct}],
            "total_questions": total, "accuracy": round(correct / total, 2),
        },
        "recognition_ref": {"schema_version": "1.1", "confidence": 0.88},
        "edited_fields": edited or [],
        "confirmed_at": "2026-10-31T12:20:31.000Z",
        "user_id": user_id,
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_PINNED_TODAY", "2026-10-31")   # 周六
    return TestClient(main.create_app(tmp_path))


def test_post_records_ok_and_persisted(client, tmp_path):
    r = client.post("/api/records", json=_payload("2026-10-31", edited=["duration_minutes"]))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["record_id"].startswith("rec_")
    saved = json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))
    assert saved["records"][0]["edited_fields"] == ["duration_minutes"]   # 必修项


def test_post_records_rejects_correct_over_total(client):
    p = _payload("2026-10-31", correct=40, total=30)
    assert client.post("/api/records", json=p).status_code == 422


def test_today_new_user_has_gap_row(client):
    r = client.get("/api/today").json()
    assert r["has_record"] is False
    assert r["gap"] == {"week_target": 5, "week_done": 0, "owed": 5}      # gap 不能省（RK-08）


def test_today_after_record(client):
    client.post("/api/records", json=_payload("2026-10-31"))
    r = client.get("/api/today").json()
    assert r["has_record"] is True
    # 新用户 50，完成度 26/30≈0.87：0.6*50 + 0.4*87 = 64.8 -> 64
    assert r["pet_state"] == "steady" and r["vitality"] == 64
    assert r["gap"]["week_done"] == 1 and r["gap"]["owed"] == 4
    assert set(r) >= {"date", "has_record", "pet_state", "vitality", "user_state", "phrase_level", "gap"}


def test_today_is_deterministic(client):
    client.post("/api/records", json=_payload("2026-10-31"))
    assert client.get("/api/today").json() == client.get("/api/today").json()


def test_missed_days_cool_down_then_sleep(client):
    client.post("/api/records", json=_payload("2026-10-20"))     # 11 天前
    r = client.get("/api/today").json()
    assert r["has_record"] is False and r["pet_state"] == "sleep"
    assert r["missed_days"] == 11


def test_week_gap_counts_distinct_days_this_week_only(client):
    # 2026-10-31 为周六，本周从 10-26 开始
    for d in ("2026-10-25", "2026-10-27", "2026-10-27", "2026-10-30"):
        client.post("/api/records", json=_payload(d))
    gap = client.get("/api/today").json()["gap"]
    assert gap["week_done"] == 2          # 10-27 去重，10-25 属于上周


def test_memories_empty_without_seed(client):
    assert client.get("/api/memories").json() == {"items": []}


def test_memories_from_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_PINNED_TODAY", "2026-10-31")
    item = {"days_ago": 41, "quote": "资料分析我一定能拿下",
            "reality": {"module": "资料分析", "week_accuracy": 0.48}, "question": "你当时少算了什么？"}
    (tmp_path / "seed.json").write_text(json.dumps({"records": [], "memories": [item]}, ensure_ascii=False), encoding="utf-8")
    c = TestClient(main.create_app(tmp_path))
    assert c.get("/api/memories").json() == {"items": [item]}
