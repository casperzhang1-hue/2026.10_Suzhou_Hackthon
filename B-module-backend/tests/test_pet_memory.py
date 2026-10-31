"""记忆与「你怎么知道」——这次被当面戳穿的那两个洞。

用户在截图上问「你怎么知道我做了这么长时间」，它回：
「我闻到你袖口有咖啡味，还摸到你手心冒汗。你上次说『学到凌晨两点』，我就记住了呀。」

这句话里有三处假，一处都不该说出口：

1. **闻到、手心** —— 它只有一块屏幕，没有鼻子也没有手
2. **你上次说** —— mock 里那句「那天你学到凌晨两点」是系统旁白，不是他说的
3. **你刚做的这件事它根本不知道** —— 图片传进识别模块就断了，压根没到它手里

所以这组测试盯的全是「它凭什么这么说」，而不是「它说得暖不暖」。
"""
import io
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, pet_llm, pet_memory as M, pet_persona as P, pet_vision

SEED = Path(__file__).resolve().parents[1] / "data" / "seed.json"
REAL_IMG = Path(__file__).resolve().parents[2] / "C-module-recognition" / "test" / "test12_粉笔_1031_判断推理.jpg"


@pytest.fixture
def client(tmp_path):
    shutil.copy(SEED, tmp_path / "seed.json")
    with TestClient(main.create_app(tmp_path)) as c:
        yield c


TODAY = {
    "has_record": True,
    "user_state": "疲惫",
    "gap": {"week_target": 5, "week_done": 4, "owed": 1},
    "detail": {"duration_minutes": 24, "accuracy": 0.6},
}
MODULES = [
    {"module": "资料分析", "questions": 955, "accuracy": 0.624},
    {"module": "判断推理", "questions": 300, "accuracy": 0.67},
]
KNOWN = ["资料分析", "判断推理"]
MEMORIES = [
    {"type": "promise", "days_ago": 41, "quote": "资料分析我一定能拿下", "module": "资料分析"},
    {"type": "event", "days_ago": 30, "quote": "那天你学到凌晨两点", "detail": "210 分钟，60 题对 33 题"},
]


# ---------- 抽记忆：存原话，不存摘要 ----------

def test_抽记忆_情绪和事件都记得住():
    assert M.classify("我今天真的学不动了") == "feeling"
    assert M.classify("我今天刷了两套判断推理") == "event"
    assert M.classify("我答应你明天早起") == "promise"
    assert M.classify("我最怕数量关系") == "prefer"


def test_抽记忆_提问不算记忆():
    """「我今天做得怎么样」不能变成一条事件记忆——记住的全是问句，它就会答非所问。"""
    assert M.classify("我今天做得怎么样？") is None
    assert M.classify("我该怎么办") is None


def test_抽记忆_没有我就不是他自己说的():
    assert M.classify("今天天气不错") is None


def test_抽记忆_问它的话不能被记成他说过的事():
    """「你怎么知道我做了这么长时间」里有个「我做了」，但它是在问它，
    记下来之后它就会拿这句话当出处，回一句「你刚才跟我说的呀」。"""
    assert M.classify("你怎么知道我做了这么长时间") is None
    assert M.classify("你凭什么觉得我今天学了") is None


def test_抽记忆_存的是原话不是摘要():
    item = M.extract("我今天模考只对了九题，有点想哭")
    assert item["quote"] == "我今天模考只对了九题，有点想哭"
    assert item["who"] == "他" and item["source"] == "user" and item["days_ago"] == 0


def test_抽记忆_带上他提到的科目():
    item = M.extract("我今天资料分析又只对了一半", known_modules=["资料分析", "判断推理"])
    assert item["module"] == "资料分析"


# ---------- 旁白 vs 原话 ----------

def test_旁白被认出来不是他的原话():
    """seed 里那句「那天你学到凌晨两点」是系统摘要，不是他说的。"""
    assert M.is_narration("那天你学到凌晨两点") is True
    assert M.is_narration("资料分析我一定能拿下") is False
    assert M.view({"quote": "那天你学到凌晨两点", "days_ago": 30})["who"] == "旁白"
    assert M.view({"quote": "资料分析我一定能拿下", "days_ago": 41})["who"] == "他"


def test_多久之前要说人话():
    assert M.view({"quote": "我在", "days_ago": 0, "source": "user"})["when"] == "刚才"
    assert M.view({"quote": "我在", "days_ago": 30})["when"] == "30 天前"


# ---------- 闸：编身体证据 ----------

def _facts(text="今天怎么样"):
    return P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text=text)


def test_闸_拦下截图里那句闻到摸到():
    """原话逐字复现。这句是这次翻车的现场。"""
    bad = "我闻到你袖口有咖啡味，还摸到你手心冒汗。"
    ok, why = P.check_reply(bad, facts=_facts(), user_text="你怎么知道我做了这么长时间")
    assert not ok and "身体" in why


def test_闸_拦下看见他眼皮咬着笔头():
    bad = "你今天做了24分钟，我看见你眼皮都快粘住了呀，你咬着笔头想了好久。"
    ok, why = P.check_reply(bad, facts=_facts(), user_text="今天怎么样")
    assert not ok and "身体" in why


def test_闸_放行看见你发的图():
    """「看到你发的截图」不算编身体证据——图是他自己给的。"""
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="我传了张图",
                          uploads=[{"seen": {"minutes": 23,
                                             "modules": [{"name": "判断推理", "questions": 15, "correct": 9}]}}])
    ok, why = P.check_reply("我看到你发的截图啦，判断推理呀。", facts=facts, user_text="我传了张图",
                            known_modules=KNOWN)
    assert ok, why


# ---------- 闸：科目编造 ----------

def test_闸_拦下库里没有的科目():
    ok, why = P.check_reply("那道数量关系的题你最后还是做对了。",
                            facts=_facts(), user_text="今天怎么样", known_modules=KNOWN)
    assert not ok and "科目" in why


def test_闸_放行库里有的科目():
    ok, _ = P.check_reply("判断推理你今天做得还行。", facts=_facts(), user_text="今天怎么样",
                          known_modules=KNOWN)
    assert ok


# ---------- 闸：被问出处必须说出处 ----------

def test_闸_被问怎么知道却没说出处就拦():
    ok, why = P.check_reply("我就是知道呀。", facts=_facts("你怎么知道我做了这么长时间"),
                            user_text="你怎么知道我做了这么长时间")
    assert not ok and "出处" in why


def test_闸_说出图就算过():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="你怎么知道我做了这么长时间",
                          uploads=[{"seen": {"minutes": 23, "modules": []}}])
    ok, why = P.check_reply("你刚传给我的那张图呀，上面写着呢。",
                            facts=facts, user_text="你怎么知道我做了这么长时间")
    assert ok, why


def test_事实包_被问出处时进provenance模式并带来源():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="你怎么知道我做了这么长时间",
                          uploads=[{"said": "看了", "seen": {"summary": "粉笔，判断推理 15 题对 9 题"}}])
    assert facts["mode"] == "provenance"
    assert any("图" in s["from"] for s in facts["sources"])


def test_闸_图里读到的数可以被念出来():
    """图上是 15 题 23 分钟，它说出来不算编——这些是他给过我的。"""
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="你怎么知道我做了这么长时间",
                          uploads=[{"seen": {"minutes": 23,
                                             "modules": [{"name": "判断推理", "questions": 15, "correct": 9}],
                                             "summary": "10-31，判断推理 15 题对 9 题，23 分钟"}}])
    ok, why = P.check_reply("你刚传给我的那张图里，判断推理 23 分钟做了 15 题，对了 9 题。",
                            facts=facts, user_text="你怎么知道我做了这么长时间",
                            known_modules=["判断推理"])
    assert ok, why


# ---------- 闸：旁白不许当原话 ----------

def test_闸_没有他说过的话时不许说你说过():
    facts = _facts()
    ok, why = P.check_reply("你说过要学到凌晨两点。", facts=facts, user_text="还记得吗")
    assert not ok and "旁白" in why


def test_闸_引图必须引得出():
    """「我拱你一下，你那天学到凌晨两点，小灯还亮着呢」——图里没有小灯，是它想的。"""
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="我传了张截图",
                          uploads=[{"seen": {"minutes": 23,
                                             "modules": [{"name": "判断推理", "questions": 15, "correct": 9}]}}])
    ok, why = P.check_reply("我拱你一下，你刚传给我的那张图里，小灯还亮着呢。",
                            facts=facts, user_text="我传了张截图", known_modules=KNOWN)
    assert not ok and "图里没有" in why


def test_闸_引图说得出数就放行():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="我传了张截图",
                          uploads=[{"seen": {"minutes": 23,
                                             "modules": [{"name": "判断推理", "questions": 15, "correct": 9}]}}])
    ok, _ = P.check_reply("你传的那张图上是判断推理，15 题。", facts=facts,
                          user_text="我传了张截图", known_modules=KNOWN)
    assert ok


def test_闸_没给过图却提图():
    # 问的不是账（问账时另有更狠的一条闸：别拿截图当答案）
    ok, why = P.check_reply("你那张图里写着呀。", facts=_facts("你在干嘛呀"), user_text="你在干嘛呀",
                            known_modules=KNOWN)
    assert not ok and "没给过" in why


def test_安慰模式不给图当证据():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="我今天学不动了",
                          uploads=[{"seen": {"minutes": 23, "modules": []}}])
    assert "sources" not in facts
    ok, why = P.check_reply("我看你那张图里，小灯还亮着呢。", facts=facts,
                            user_text="我今天学不动了")
    assert not ok


# ---------- 接口：记忆真的写进去了 ----------

def test_接口_他说的话会落库并抽成记忆(client):
    d = client.post("/api/pet/say", json={"text": "我今天模考又把判断推理做崩了"}).json()
    assert d["remembered"] and d["remembered"]["who"] == "他"
    items = client.get("/api/memories").json()["items"]
    assert any(m.get("quote") == "我今天模考又把判断推理做崩了" for m in items)


def test_接口_记忆能被显式写入(client):
    d = client.post("/api/memories", json={"text": "我最怕数量关系"}).json()
    assert d["saved"] is True and d["memory"]["who"] == "他"


def test_接口_没什么可记的就别硬记(client):
    d = client.post("/api/memories", json={"text": "今天天气不错"}).json()
    assert d["saved"] is False


def test_接口_对话落库刷新不丢(client):
    client.post("/api/pet/say", json={"text": "我今天有点累"})
    d = client.post("/api/pet/say", json={"text": "你还记得我刚才说啥吗"}).json()
    # 第二句请求里没带 history，事实包里也要能看见第一句留下的记忆
    assert any("我今天有点累" in str(m) for m in d["facts"]["memories"])


# ---------- 接口：真的看一眼图 ----------

def _fake_seen(monkeypatch):
    monkeypatch.setattr(pet_vision, "see", lambda raw, **k: {
        "ok": True, "model": "fake-vl", "raw": "",
        "seen": {"app": "粉笔", "date": "10-31", "minutes": 24,
                 "modules": [{"name": "判断推理", "questions": 15, "correct": 9}],
                 "evidence": "判断推理 15/9"},
    })
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "唔，判断推理 15 题对 9 题呀，24 分钟。")


def test_接口_传图后它说得出图上有什么(client, monkeypatch):
    _fake_seen(monkeypatch)
    d = client.post("/api/pet/seen", json={"image": "x" * 64, "image_name": "a.jpg"}).json()
    assert d["ok"] is True
    assert d["seen"]["modules"][0]["name"] == "判断推理"
    assert "15" in d["text"] or "判断推理" in d["text"]


def test_接口_同一张图不会看两遍(client, monkeypatch):
    _fake_seen(monkeypatch)
    first = client.post("/api/pet/seen", json={"image": "x" * 64}).json()
    second = client.post("/api/pet/seen", json={"image": "x" * 64}).json()
    assert first.get("cached") is False
    assert second["cached"] is True and second["text"] == first["text"]


def test_接口_看不清就承认看不清不猜(client, monkeypatch):
    monkeypatch.setattr(pet_vision, "see", lambda raw, **k: {
        "ok": False, "seen": None, "model": "fake-vl", "raw": "", "reason": "图上看不出有效信息",
    })
    d = client.post("/api/pet/seen", json={"image": "y" * 64}).json()
    assert d["ok"] is False and "看不清" in d["text"]


def test_接口_看图说话也必须过闸(client, monkeypatch):
    """模型看到图还是可能编一句「我闻到你身上有咖啡味」，一样拦掉，退到由抽取结果拼的那句。"""
    _fake_seen(monkeypatch)
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "我闻到你身上有咖啡味，判断推理 15 题。")
    d = client.post("/api/pet/seen", json={"image": "z" * 64}).json()
    assert "咖啡" not in d["text"]
    assert "判断推理" in d["text"]


# ---------- 视觉层：解析必须宁缺毋滥 ----------

def test_视觉解析_看不清的字段就是None():
    seen = pet_vision.parse('{"app":null,"minutes":null,"modules":[],"evidence":null}')
    assert seen is None                       # 一个能用的字段都没有 = 没看清


def test_视觉解析_从解释文字里抠JSON():
    seen = pet_vision.parse('好的，这是结果：\n```json\n{"app":"粉笔","minutes":24,'
                            '"modules":[{"name":"判断推理","questions":15,"correct":9}]}\n```')
    assert seen["minutes"] == 24 and seen["modules"][0]["correct"] == 9


def test_视觉解析_坏JSON不猜():
    assert pet_vision.parse("粉笔，判断推理，大概 24 分钟") is None


def test_视觉解析_照抄提示词的字段当没填():
    """实测 gpt-4o-mini 会把 app 填成「应用名（图上写了的才填）或 null」。"""
    seen = pet_vision.parse('{"lines":["总用时 23 分 51 秒"],'
                            '"app":"应用名（图上写了的才填）或 null",'
                            '"minutes":23,"modules":[]}')
    assert seen["app"] is None
    assert seen["minutes"] == 23


def test_视觉解析_图上没写又不在词表里的科目丢掉():
    seen = pet_vision.parse('{"lines":["总用时 23 分 51 秒"],"minutes":23,'
                            '"modules":[{"name":"判断推理","questions":15,"correct":9},'
                            '{"name":"机器学习","questions":5,"correct":3}]}')
    names = [m["name"] for m in seen["modules"]]
    assert "判断推理" in names and "机器学习" not in names


def test_视觉解析_转写行留作证据():
    seen = pet_vision.parse('{"lines":["总用时 23 分 51 秒","判断推理"],"minutes":23,'
                            '"evidence":"总用时 23 分 51 秒","modules":[]}')
    assert seen["lines"][0] == "总用时 23 分 51 秒"
    assert seen["evidence"] == "总用时 23 分 51 秒"


def test_视觉解析_练习类型不许当应用名():
    """实测它把「专项智能练习」填进 app，于是开口就是「这张我看了，专页智能练习…」。"""
    seen = pet_vision.parse('{"lines":["练习类型：专项智能练习（判断推理）","总用时 23 分 51 秒"],'
                            '"app":"专项智能练习","minutes":23,'
                            '"modules":[{"name":"判断推理","questions":15,"correct":9}]}')
    assert seen["app"] is None


def test_视觉解析_认识的应用名照留():
    seen = pet_vision.parse('{"lines":["粉笔","总用时 23 分 51 秒"],"app":"粉笔","minutes":23,'
                            '"modules":[]}')
    assert seen["app"] == "粉笔"
