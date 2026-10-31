"""宠物「模型嘴」（/api/pet/context + /api/pet/verify）的验收测试。

模型本身不可测（非确定性），所以测的是**拦住它的那两道闸**：

- 事实包口径：同一个「资料分析」有历史累计 / 承诺当时 / 承诺本周三个数，
  必须分别贴上不同标签，否则模型必然张冠李戴（实测 glm-5.3-flash 就上过当）。
- 数字白名单：模型编一个库里没有的数，必须被抓。
- 分句归属：数字是真的但安错了模块，也必须被抓。
- 复核接口：不通过时 ok=false 且给出原因，前端据此回退模板。
"""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, pet_brain

SEED = Path(__file__).resolve().parents[1] / "data" / "seed.json"


@pytest.fixture
def client(tmp_path):
    shutil.copy(SEED, tmp_path / "seed.json")
    with TestClient(main.create_app(tmp_path)) as c:
        yield c


TODAY = {
    "has_record": True,
    "user_state": "稳",
    "gap": {"week_target": 5, "week_done": 4, "owed": 1},
    "detail": {"duration_minutes": 130, "accuracy": 0.6},
}
MODULES = [
    {"module": "资料分析", "questions": 955, "accuracy": 0.624},
    {"module": "数量关系", "questions": 100, "accuracy": 0.52},
]
MEMORIES = [
    {"id": "m1", "type": "promise", "days_ago": 41, "quote": "资料分析我一定能拿下",
     "module": "资料分析", "then_accuracy": 0.73, "week_accuracy": 0.48},
]


def _facts(intent="weak"):
    return pet_brain.build_facts(intent, today=TODAY, modules=MODULES, memories=MEMORIES)


# ---------- 事实包口径 ----------

def test_三个口径分开贴标签():
    """资料分析：历史累计 62、承诺当时 73、承诺本周 48，三者不能糊成一个。"""
    facts = _facts()
    module = next(m for m in facts["modules"] if m["name"] == "资料分析")
    assert module["accuracy_pct"] == 62

    mem = facts["memories"][0]
    assert mem["accuracy_when_promised_pct"] == 73
    assert mem["accuracy_this_week_pct"] == 48
    # 同一个词不能在模块视图里再出现一次，否则模型不知道挑哪个
    assert mem.get("accuracy_pct") is None


def test_百分比全部转成整数():
    """0.624 → 62。模型不用做小数换算，就少一类算错的机会。"""
    facts = _facts()
    assert all(isinstance(m["accuracy_pct"], int) for m in facts["modules"])
    assert facts["today"]["accuracy_pct"] == 60


def test_弱项最强项由模块表推出():
    facts = _facts()
    assert facts["weakest_module"] == "数量关系"
    assert facts["strongest_module"] == "资料分析"


def test_题量不足的模块不进事实包():
    """少于 MIN_SAMPLE 的模块不给模型看，避免拿三题的正确率下结论。"""
    facts = pet_brain.build_facts(
        "weak", today=TODAY,
        modules=[{"module": "申论", "questions": 5, "accuracy": 0.9}],
        memories=[],
    )
    assert facts["modules"] == []
    assert "weakest_module" not in facts


def test_记忆按意图筛选():
    """问承诺就只给承诺，不要把两条 event 也塞进去干扰它。"""
    mems = MEMORIES + [{"id": "m2", "type": "event", "days_ago": 30, "quote": "那天你学到凌晨两点",
                        "detail": "210 分钟，60 题对 33 题。"}]
    assert [m["kind"] for m in pet_brain.build_facts("promise", today=TODAY, modules=MODULES, memories=mems)["memories"]] == ["promise"]
    assert len(pet_brain.build_facts("today", today=TODAY, modules=MODULES, memories=mems)["memories"]) == 2


# ---------- 第一道闸：数字白名单 ----------

def test_白名单覆盖事实包里每个数字():
    allowed = pet_brain.allowed_numbers(_facts())
    for n in (130, 60, 1, 4, 5, 62, 52, 955, 100, 41, 73, 48):
        assert n in allowed, f"{n} 应该允许出现"


def test_编造的数字被抓():
    facts = _facts()
    ok, reason = pet_brain.check("数量关系最弱，正确率才 38%。", facts)
    assert not ok and "38" in reason


def test_真实回答放行():
    facts = _facts()
    ok, reason = pet_brain.check("数量关系最弱，历史累计 52%。资料分析这周只有 48%。", facts)
    assert ok, reason


# ---------- 第二道闸：分句归属 ----------

def test_数字是真的但安错模块也被抓():
    """48 确实是事实包里的数（资料分析的承诺本周），但绝不是数量关系的。"""
    facts = _facts()
    ok, reason = pet_brain.check("数量关系这周只有 48%。", facts)
    assert not ok and "数量关系" in reason


def test_同一句点两个模块时不做归属判定():
    """比较句里两个模块并列是正常的，硬判会误杀好回答。"""
    facts = _facts()
    ok, reason = pet_brain.check("数量关系 52%，资料分析 62%，两个都得补。", facts)
    assert ok, reason


def test_不提模块名的句子不做归属判定():
    facts = _facts()
    ok, reason = pet_brain.check("这周还欠 1 次，今天 130 分钟。", facts)
    assert ok, reason


def test_空回答被拒():
    ok, reason = pet_brain.check("   ", _facts())
    assert not ok and reason == "空回答"


# ---------- 接口 ----------

def test_context_接口返回可直接喂模型的形状(client):
    d = client.get("/api/pet/context?intent=weak").json()
    assert d["ok"] is True and d["intent"] == "weak"
    assert d["facts"]["weakest_module"]
    assert d["system_prompt"].startswith("你是")
    assert d["question"]
    assert isinstance(d["allowed_numbers"], list) and d["allowed_numbers"]


def test_context_未知意图回落今天(client):
    d = client.get("/api/pet/context?intent=胡说八道").json()
    assert d["intent"] == "today"


def test_verify_放行真实回答(client):
    """拿库里真有的数字去问，必须放行——否则闸门太紧，正常回答全被误杀。"""
    minutes = client.get("/api/today").json()["detail"]["duration_minutes"]
    d = client.post("/api/pet/verify", json={
        "intent": "today", "text": f"今天 {minutes} 分钟。"}).json()
    assert d["ok"] is True, d.get("reason")


def test_verify_拦下编造的数字(client):
    d = client.post("/api/pet/verify", json={
        "intent": "today", "text": "今天练了 999 分钟。"}).json()
    assert d["ok"] is False and "999" in d["reason"]


def test_verify_用库里的真实事实而不是客户端说了算(client):
    """客户端只能报 intent 与文本，事实由服务端现查——否则可以伪造一份白名单骗过校验。"""
    d = client.post("/api/pet/verify", json={
        "intent": "weak", "text": "数量关系这周只有 48%。"}).json()
    assert d["ok"] is False
