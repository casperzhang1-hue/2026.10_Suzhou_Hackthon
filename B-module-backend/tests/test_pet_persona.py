"""团团的性格、记性和嘴上的闸 —— 以及「接模型」那条链路的降级行为。

模型本身不可测（非确定性、还依赖网络），所以这里测的全是**能确定的部分**：

- 说出来的话格式对不对（markdown / 表情 / 换行 / 括号旁白都会被气泡撑破）
- 该想起的事有没有想起来（他说「资料分析」，就该想起那条约定的承诺）
- 该拦的话有没有拦住（报假数字、把数字改成中文、说教、角色混淆、编「昨天」）
- 模型挂了 / 说错话时，是不是退到一句笨但真的话，而不是把假话显示出去
"""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, pet_llm, pet_persona as P

SEED = Path(__file__).resolve().parents[1] / "data" / "seed.json"


@pytest.fixture
def client(tmp_path):
    shutil.copy(SEED, tmp_path / "seed.json")
    with TestClient(main.create_app(tmp_path)) as c:
        yield c


TODAY = {
    "has_record": True,
    "user_state": "疲惫",
    "gap": {"week_target": 5, "week_done": 4, "owed": 1},
    "detail": {"duration_minutes": 130, "accuracy": 0.6},
}
MODULES = [
    {"module": "资料分析", "questions": 955, "accuracy": 0.624},
    {"module": "数量关系", "questions": 100, "accuracy": 0.52},
    {"module": "判断推理", "questions": 300, "accuracy": 0.67},
]
MEMORIES = [
    {"type": "promise", "days_ago": 41, "quote": "资料分析我一定能拿下",
     "module": "资料分析", "then_accuracy": 0.73, "week_accuracy": 0.48},
    {"type": "event", "days_ago": 30, "quote": "那天你学到凌晨两点",
     "detail": "210 分钟，60 题对 33 题"},
]


# ---------- 洗格式 ----------

def test_洗格式_去掉markdown和表情和换行():
    raw = "**唔**，我在呢 😊\n\n- 瓜子给你\n- 别怕"
    assert P.sanitize(raw) == "唔，我在呢 瓜子给你 别怕"


def test_洗格式_括号旁白去掉括号保留内容():
    # 气泡里出现「（拱你一下）」像剧本，读起来不像小动物在说话
    assert P.sanitize("（拱你一下）我在呢") == "拱你一下我在呢"


def test_洗格式_三个点是中文省略号():
    assert "..." not in P.sanitize("唔...我在")


def test_洗格式_超长在标点处断句():
    text = "我在这儿" * 30 + "。"
    out = P.sanitize(text)
    assert len(out) <= 61
    # 要么停在句号上，要么补一个省略号——不能停在一个没说完整的字上
    assert out.endswith(("。", "…"))


# ---------- 记性 ----------

def test_想起_提到模块就想起那条承诺():
    picked = P.recall("资料分析到底怎么样", MEMORIES, MODULES)
    assert picked[0]["quote"] == "资料分析我一定能拿下"


def test_想起_难受时想起那件事实而不是承诺():
    picked = P.recall("我今天学不动了", MEMORIES, MODULES)
    assert picked[0]["type"] == "event"


def test_想起_什么都没命中时也给一件最不瞎编的():
    picked = P.recall("今天天气不错", MEMORIES, MODULES)
    assert len(picked) == 1  # 手上不能空着，空着模型就会编


# ---------- 事实包：安慰模式里一个数字都不许有 ----------

def _all_numbers(node, out):
    if isinstance(node, dict):
        for v in node.values():
            _all_numbers(v, out)
    elif isinstance(node, list):
        for v in node:
            _all_numbers(v, out)
    elif isinstance(node, bool):
        pass
    elif isinstance(node, (int, float)):
        out.append(node)
    elif isinstance(node, str):
        out.extend(int(n) for n in __import__("re").findall(r"\d+", node))


def test_安慰模式_事实包里没有任何数字():
    """他难受的时候，输入端就不给数字——不给，模型就没得念。
    比在输出端追着拦可靠：实测 qwen-flash 被拦一次后照样念。"""
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="我今天学不动了")
    nums = []
    _all_numbers(facts, nums)
    assert facts["mode"] == "comfort"
    assert nums == []


def test_数据模式_数字照旧带口径():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="我今天做了什么")
    nums = []
    _all_numbers(facts, nums)
    assert facts["mode"] == "normal"
    assert 130 in nums and 60 in nums
    assert facts["weakest_module"] == "数量关系"


def test_难受但明确问成绩_仍然给数据():
    # 一边说累一边问「怎么样」，他是真想知道，不能一律进安慰模式
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="累死了，我今天做得怎么样")
    assert facts["mode"] == "normal"


# ---------- 嘴上的闸 ----------

def _facts(text="今天怎么样"):
    return P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text=text)


def test_闸_拦下说教话():
    ok, why = P.check_reply("你应该早点睡，别想太多", facts=_facts(), user_text="我累了")
    assert not ok and "堵情绪" in why


def test_闸_拦下编造的数字():
    ok, why = P.check_reply("你今天学了250分钟", facts=_facts(), user_text="今天怎么样")
    assert not ok and "没有的数字" in why


def test_闸_拦下中文写法的数字():
    """「十三分钟」「六成」绕得过 \\d+ 白名单，是最隐蔽的一个洞。"""
    for bad in ("你今天学了十三分钟", "对了六成呢", "啃了两小时"):
        ok, why = P.check_reply(bad, facts=_facts(), user_text="今天怎么样")
        assert not ok, bad


def test_闸_拦下第三人称():
    ok, why = P.check_reply("他说今天很累", facts=_facts(), user_text="今天怎么样")
    assert not ok and "第三人称" in why


def test_闸_拦下编造的昨天():
    ok, why = P.check_reply("你昨天学到很晚呀", facts=_facts(), user_text="今天怎么样")
    assert not ok and "比较基线" in why


def test_闸_难受时不许报数字():
    facts = _facts("我今天学不动了")
    ok, why = P.check_reply("你今天学了130分钟呀", facts=facts, user_text="我今天学不动了")
    assert not ok


def test_闸_放行一句正常的安慰():
    facts = _facts("我今天学不动了")
    ok, why = P.check_reply("唔…那你歇会儿，我趴这儿陪你。", facts=facts, user_text="我今天学不动了")
    assert ok, why


def test_闸_他说的数字可以被引用():
    # 他说「60分」，模型回「60分」不该被判成编造
    ok, _ = P.check_reply("60 分也不算白做呀", facts=_facts(), user_text="我今天模考60分")
    assert ok


# ---------- 兜底与重试 ----------

def test_兜底话里一个数字都没有():
    import re
    for q in ("我今天学不动了", "你还记得我的承诺吗", "今天天气不错"):
        assert not re.search(r"\d", P.fallback(q)), q


def test_重试是把否定理由喂回去():
    msgs = P.retry_messages([{"role": "system", "content": "x"}], "说了个数字", "他正难受")
    assert msgs[-2] == {"role": "assistant", "content": "说了个数字"}
    assert "他正难受" in msgs[-1]["content"]


# ---------- 接口层：模型好 / 模型坏 / 模型说错话 ----------

def test_接口_模型正常时走模型(client, monkeypatch):
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "唔，你摸摸我，我在呢。")
    d = client.post("/api/pet/say", json={"text": "陪我待一会儿"}).json()
    assert d["source"] == "model" and d["guard"]["ok"] is True
    assert d["text"] == "唔，你摸摸我，我在呢。"


def test_接口_模型第一次说错话会重试(client, monkeypatch):
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        return "你今天学了130分钟" if calls["n"] == 1 else "唔，先歇会儿，我在。"

    monkeypatch.setattr(pet_llm, "chat", fake)
    d = client.post("/api/pet/say", json={"text": "我今天学不动了"}).json()
    assert calls["n"] == 2
    assert d["source"] == "model" and d["text"] == "唔，先歇会儿，我在。"


def test_接口_两次都说错话就退回兜底(client, monkeypatch):
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "你应该加油，别想太多")
    d = client.post("/api/pet/say", json={"text": "我累了"}).json()
    assert d["source"] == "fallback" and d["guard"]["ok"] is False
    assert "加油" not in d["text"] and "你应该" not in d["text"]


def test_接口_模型挂了也照样回一句话(client, monkeypatch):
    def boom(*a, **k):
        raise pet_llm.LLMError("连不上")

    monkeypatch.setattr(pet_llm, "chat", boom)
    d = client.post("/api/pet/say", json={"text": "在吗"}).json()
    assert d["ok"] is True and d["source"] == "fallback" and d["text"]


def test_接口_空话被挡在门口(client):
    assert client.post("/api/pet/say", json={"text": ""}).status_code == 422


def test_接口_返回里带事实包方便自证(client, monkeypatch):
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "唔，我在呢。")
    d = client.post("/api/pet/say", json={"text": "资料分析怎么样"}).json()
    assert d["facts"]["mode"] in ("normal", "comfort")
    assert isinstance(d["facts"]["memories"], list)
    assert d["ms"] >= 0


def test_探活接口_不把401个模型名倒给前端(client):
    d = client.get("/api/pet/llm").json()
    assert set(d) >= {"available", "model", "persona"}
    assert len(d["models"]) <= 1
