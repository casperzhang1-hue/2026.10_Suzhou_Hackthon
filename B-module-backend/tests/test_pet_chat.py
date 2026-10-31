"""宠物开口（/api/pet/chat）的验收测试。

重点不是「有没有话」，而是**话里的数字能不能溯源**：
- 有记录 → 必须报真实时长与正确率
- 没记录 → 必须报真实缺口，且不得出现编造的时长
- 承诺 → 必须与 memories 里的 73% / 48% 一致
- 未知意图 → 必须反问，不得硬答
- 样本量不足 → 必须拒绝下结论
"""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, pet_chat

SEED = Path(__file__).resolve().parents[1] / "data" / "seed.json"


@pytest.fixture
def client(tmp_path):
    """带 seed 的库：记忆与模块聚合才有真实数据可引用。"""
    shutil.copy(SEED, tmp_path / "seed.json")
    app = main.create_app(tmp_path)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def empty_client(tmp_path):
    """空库：验证「无数据时不下结论」这一侧。"""
    with TestClient(main.create_app(tmp_path)) as c:
        yield c


def _post(client, date_str, minutes, correct, total):
    return client.post("/api/records", json={
        "record": {
            "source_app": "粉笔", "event_date": date_str, "event_time": "21:40",
            "duration_minutes": minutes,
            "modules": [{"name": "资料分析", "question_count": total, "correct_count": correct}],
            "total_questions": total, "accuracy": round(correct / total, 2),
        },
        "confirmed_at": "2026-10-31T12:20:31.000Z",
        "user_id": "demo_zhang",
    })


def test_chat_today_without_record_speaks_gap_not_fake_minutes(client):
    body = client.get("/api/pet/chat", params={"intent": "today"}).json()
    assert body["ok"] is True
    assert body["facts"]["has_record"] is False
    assert "分钟" not in body["text"]          # 没记录就不能报时长
    assert "欠" in body["text"] or "打卡" in body["text"]


def test_chat_today_with_record_quotes_real_minutes(client):
    assert _post(client, "2026-10-31", 58, 26, 30).status_code == 200

    body = client.get("/api/pet/chat", params={"intent": "today"}).json()
    assert body["facts"]["has_record"] is True
    assert body["facts"]["minutes"] == 58
    assert "58 分钟" in body["text"]
    assert "87%" in body["text"]               # 26/30 = 0.867 → 87%


def test_chat_weak_names_lowest_module_from_real_aggregate(client):
    body = client.get("/api/pet/chat", params={"intent": "weak"}).json()
    assert body["ok"] is True
    worst, best = body["facts"]["worst"], body["facts"]["best"]
    # 与 /api/stats 的聚合口径一致：最低的就是数量关系，最高的是言语理解
    assert worst == "数量关系"
    assert best == "言语理解"
    assert "52%" in body["text"]
    assert worst in body["text"] and best in body["text"]


def test_chat_promise_matches_memory_numbers(client):
    body = client.get("/api/pet/chat", params={"intent": "promise"}).json()
    facts = body["facts"]
    assert facts["id"] == "m1"
    assert facts["then_accuracy"] == 0.73
    assert facts["week_accuracy"] == 0.48
    assert "73%" in body["text"] and "48%" in body["text"]
    assert "资料分析我一定能拿下" in body["text"]


def test_chat_unknown_intent_asks_back_instead_of_answering(client):
    body = client.get("/api/pet/chat", params={"intent": "讲个笑话"}).json()
    assert body["ok"] is False
    assert "答不上来" in body["text"]
    assert set(body["topics"]) == {"today", "weak", "promise"}


def test_weak_refuses_when_sample_too_small():
    """题量不足时不许下结论——否则「只做了 3 题」会被说成弱项。"""
    tiny = [{"module": "数量关系", "questions": 8, "accuracy": 0.25, "sessions": 1}]
    out = pet_chat.answer_weak(tiny)
    assert out["facts"] == {"modules": 1}
    assert "太少" in out["text"]


def test_promise_honest_when_no_memory(empty_client):
    body = empty_client.get("/api/pet/chat", params={"intent": "promise"}).json()
    assert body["ok"] is True
    assert body["facts"]["promises"] == 0
    assert "还没跟我说过" in body["text"]
