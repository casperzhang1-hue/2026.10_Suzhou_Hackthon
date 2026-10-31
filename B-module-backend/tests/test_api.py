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
    # 口径与 A 的 mock-server 一致：完成度 = 58/80 = 0.725（不是正确率）
    # 新用户 30：0.6*30 + 0.4*72.5 = 47 -> wilt
    assert r["pet_state"] == "wilt" and r["vitality"] == 47
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


def test_post_records_dedupes_same_screenshot_resubmit(client, tmp_path):
    p = _payload("2026-10-31")
    first = client.post("/api/records", json=p).json()
    p2 = {**p, "confirmed_at": "2026-10-31T12:21:10.000Z"}      # 同一张图，39 秒后重复提交
    second = client.post("/api/records", json=p2).json()
    assert second["record_id"] == first["record_id"]
    saved = json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))
    assert len(saved["records"]) == 1


def test_post_records_keeps_same_content_when_far_apart(client):
    p = _payload("2026-10-31")
    a = client.post("/api/records", json=p).json()
    b = client.post("/api/records", json={**p, "confirmed_at": "2026-10-31T12:25:00.000Z"}).json()
    assert a["record_id"] != b["record_id"]


def test_post_records_keeps_different_content(client):
    a = client.post("/api/records", json=_payload("2026-10-31", correct=26)).json()
    b = client.post("/api/records", json=_payload("2026-10-31", correct=20, total=40)).json()
    assert a["record_id"] != b["record_id"]


def test_cors_allows_any_local_port(client):
    r = client.options("/api/today", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    r = client.options("/api/today", headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
