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

def test_洗格式_去掉markdown和表情():
    raw = "**唔**，我在呢 😊\n\n- 瓜子给你\n- 别怕"
    assert P.sanitize(raw) == "唔，我在呢，瓜子给你，别怕。"


def test_洗格式_换行处补逗号而不是压成空格():
    """压成空格会得到「我在呢 你慢慢说」，气泡里看着像两个残句。"""
    assert P.sanitize("我在呢\n你慢慢说") == "我在呢，你慢慢说。"


def test_洗格式_上一行有标点就不再补逗号():
    assert P.sanitize("唔，我在呢。\n你慢慢说") == "唔，我在呢。你慢慢说。"


def test_洗格式_结尾没标点就补一个():
    assert P.sanitize("你撑住了") == "你撑住了。"


def test_洗格式_括号旁白去掉括号保留内容():
    # 气泡里出现「（拱你一下）」像剧本，读起来不像小动物在说话
    assert P.sanitize("（拱你一下）我在呢") == "拱你一下我在呢。"


def test_洗格式_破折号后面不留逗号():
    """模型爱写「唔——」再换行，补逗号会变成「唔——，」，念起来很别扭。"""
    assert P.sanitize("唔——\n我在这儿") == "唔——我在这儿。"


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
    assert facts["mode"] == "data"
    assert facts["answer"]["kind"] == "today" and facts["answer"]["minutes"] == 130
    # 他开口问的账，报数才是答他——闸不能把数拦掉
    ok, why = P.check_reply("今天 130 分钟了，正确率 60%。", facts=facts,
                            user_text="累死了，我今天做得怎么样")
    assert ok, why


# ---------- 问账：先答他问的那一句 ----------

def test_问今天怎么样_第一句就是今天的分钟数():
    """以前这一句落在 normal 模式：事实包里有今天的数、有刚传的图、还有旧事，
    模型没有主次，就挑最具体的念——于是问今天学得怎么样，它答图里那道题。"""
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="今天怎么样")
    assert facts["mode"] == "data"
    assert facts["answer"] == {"kind": "today", "minutes": 130, "accuracy_pct": 60}
    # 问账的时候不给旧事、不给截图：给了就是让它跑题
    assert "memories" not in facts and "sources" not in facts and "last_upload" not in facts


def test_问哪块最毛_直接算出最弱的那个模块():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="我哪里最毛")
    assert facts["mode"] == "data"
    assert facts["answer"]["kind"] == "weakest"
    assert facts["answer"]["module"] == "数量关系" and facts["answer"]["accuracy_pct"] == 52


def test_问某一科_答那一科而不是今天():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="资料分析怎么样")
    assert facts["answer"]["kind"] == "module" and facts["answer"]["module"] == "资料分析"


def test_问账时不许拿截图当答案():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="今天怎么样",
                          uploads=[{"seen": {"minutes": 23,
                                             "modules": [{"name": "判断推理", "questions": 15, "correct": 9}]}}])
    ok, why = P.check_reply("你刚传的图上是判断推理，15 题。", facts=facts, user_text="今天怎么样")
    assert not ok and "问账" in why


def test_问账的兜底照实数报_不说我在呢():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="今天怎么样")
    assert "130" in P.fallback("今天怎么样", facts=facts)
    weak = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="我哪里最毛")
    text = P.fallback("我哪里最毛", facts=weak)
    assert "数量关系" in text and "52" in text


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
    """「十三分钟」「两小时」绕得过 \\d+ 白名单，是最隐蔽的一个洞。"""
    for bad in ("你今天学了十三分钟", "啃了两小时", "做了八十五道题"):
        ok, why = P.check_reply(bad, facts=_facts(), user_text="今天怎么样")
        assert not ok, bad


def test_闸_中文写法和库里对得上就放行():
    """「六成」就是 60%，事实里正是这个数——它是真话，拦下来只会掉兜底。"""
    ok, why = P.check_reply("你今天对了六成呢", facts=_facts(), user_text="今天怎么样")
    assert ok, why


def test_闸_中文数字换算():
    """换算错了会两头出错：拦不住假话，或者把真话拦成假话。"""
    assert P.cn_amounts("十三分钟") == [("十三分钟", 13)]
    assert P.cn_amounts("两小时") == [("两小时", 120)]
    assert P.cn_amounts("六成") == [("六成", 60)]
    assert P.cn_amounts("二十三道题") == [("二十三道题", 23)]
    assert P.cn_amounts("一道题") == []      # 口语里的「一道题」，不该当数量拦


def test_闸_拦下第三人称():
    ok, why = P.check_reply("他说今天很累", facts=_facts(), user_text="今天怎么样")
    assert not ok and "第三人称" in why


def test_闸_拦下把记忆安到用户头上():
    """「你记得那句『我一定拿下』」——记得的人该是仓鼠，不是他。"""
    ok, why = P.check_reply("你记得那句“资料分析我一定能拿下”呀", facts=_facts(), user_text="那个承诺")
    assert not ok and "记忆安到了他头上" in why


def test_闸_不误杀正常叮嘱():
    ok, _ = P.check_reply("你记得吃点东西再学呀。", facts=_facts(), user_text="我在学")
    assert ok


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


# ---------- 嘴里的话不许抄自己上一句 ----------
# 实测（16:05-16:06 的真实会话）：连点三次「今天怎么样」，三次回的是同一句；
# 再问「我哪里最毛」，回的还是一模一样的一句。抄出来的那句又落库、又进下一轮历史，
# 于是越问越像唱片跳针。

def test_复读_一模一样要拦():
    ok, why = P.check_reply("数量关系那道题你算对了，我看见的。", facts=_facts(),
                            user_text="今天怎么样",
                            avoid=["数量关系那道题你算对了，我看见的。"])
    assert not ok and "复读" in why


def test_复读_前半截照抄后面补一句也要拦():
    """这是 qwen-flash 最典型的复读方式：先把上一句整句抄下来，再补一个小动作。"""
    ok, why = P.check_reply("数量关系那道题你算对了，我看见的。我把瓜子推过去啦。",
                            facts=_facts(), user_text="我哪里最毛",
                            avoid=["数量关系那道题你算对了，我看见的。"])
    assert not ok and "复读" in why


def test_复读_只换几个字也算():
    ok, _ = P.check_reply("数量关系那道题你算对了，我看见了呀。", facts=_facts(),
                          user_text="今天怎么样",
                          avoid=["数量关系那道题你算对了，我看见的。"])
    assert not ok


def test_复读_同一个模块的另一句话不误杀():
    ok, why = P.check_reply("数量关系最毛，52%，100 题。", facts=_facts(),
                            user_text="我哪里最毛",
                            avoid=["数量关系那道题你算对了，我看见的。"])
    assert ok, why


def test_复读_同一个问题重问_同样的回答不算复读():
    """事实就那些，人被问三遍也会说差不多的话——那不是毛病（不能误杀）。
    换了问题还回同一句，才是要拦的。"""
    history = [{"role": "user", "content": "今天怎么样"},
               {"role": "assistant", "content": "今天 82 分钟了，正确率 60%。"}]
    other, same = P.split_recent_replies(history, "今天怎么样")
    assert other == [] and same == ["今天 82 分钟了，正确率 60%。"]
    other2, same2 = P.split_recent_replies(history, "我哪里最毛")
    assert other2 == ["今天 82 分钟了，正确率 60%。"] and same2 == []


def test_复读_同一问题重问_换了说法就放行():
    """同一件事问两遍，事实就那些，重说一遍数没错；只要不是逐字照抄就该放行。"""
    facts = _facts("今天怎么样")
    ok, why = P.check_reply("你今天学了130分钟，正确率60%。我把瓜子推过去啦。", facts=facts,
                            user_text="今天怎么样",
                            avoid_same=["今天 130 分钟了，正确率 60%。"])
    assert ok, why


def test_复读_同一问题重问_逐字照抄还是要拦():
    """两口气一个字都不差，界面上看着像卡死了——哪怕答案是事实，也得换一句。"""
    old = "今天 130 分钟了，正确率 60%。"
    ok, why = P.check_reply(old, facts=_facts("今天怎么样"), user_text="今天怎么样",
                            avoid_same=[old])
    assert not ok and "原样说了一遍" in why


def test_重试时_同一件事重问要给的是换说法_不是别说话():
    """「复读」和「同一句原样说了一遍」是两种病，改法相反：
    前者要它闭嘴换话题，后者要它留着那笔账只换句式。喂错药它就更不会说。"""
    msgs = P.retry_messages([{"role": "user", "content": "x"}], "那句",
                            "又把刚才那句原样说了一遍「今天 130 分钟」")
    tail = msgs[-1]["content"]
    assert "数一个都不许改" in tail and "开头必须换掉" in tail


def test_复读_没有历史时一律放行():
    ok, _ = P.check_reply("唔，我在呢。", facts=_facts(), user_text="在吗")
    assert ok


def test_重试时把复读的原因说具体():
    msgs = P.retry_messages([{"role": "system", "content": "x"}], "复读了刚才那句", "复读了刚才那句「数量关系」")
    assert "全新的" in msgs[-1]["content"]


# ---------- 历史里不该有它自己的原句 ----------

def test_送模型的历史只留他说的话():
    """它自己的上一句一旦被喂回去，qwen-flash 会整句照抄。
    它需要知道的是「他刚说过什么」，不是「我上一句说了什么」。"""
    history = [
        {"role": "user", "content": "今天怎么样"},
        {"role": "assistant", "content": "数量关系那道题你算对了，我看见的。"},
        {"role": "user", "content": "我哪里最毛"},
    ]
    msgs = P.build_messages("我哪里最毛", facts=_facts("我哪里最毛"), history=history)
    roles = [m["role"] for m in msgs]
    assert "assistant" not in roles
    joined = " ".join(m["content"] for m in msgs)
    assert "数量关系那道题你算对了" not in joined      # 没有可抄的锚点
    assert "今天怎么样" in joined                      # 但记得他刚说过什么


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
    assert d["facts"]["mode"] in ("normal", "comfort", "data")
    assert d["facts"]["mode"] != "data" or "answer" in d["facts"]
    assert d["ms"] >= 0


def test_接口_复读上一句会被打回重说(client, monkeypatch):
    """离线复现线上那次：它把上一轮的回答原样搬过来。第一次照抄要被打回。"""
    calls = {"n": 0}
    old = "数量关系那道题你算对了，我看见的。"

    def fake(*a, **k):
        calls["n"] += 1
        return old if calls["n"] == 1 else "你上次问的那块，我再翻翻记录。"

    monkeypatch.setattr(pet_llm, "chat", fake)
    d = client.post("/api/pet/say", json={
        "text": "我哪里最毛",
        "history": [{"role": "user", "content": "今天怎么样"},
                    {"role": "assistant", "content": old}],
    }).json()
    assert calls["n"] == 2
    assert d["source"] == "model" and d["text"] != old


def test_接口_同一个问题重问_逐字照抄会被打回重说(client, monkeypatch):
    """同一个问题问两遍，它两次吐出一模一样的字——第一次就该打回，
    换一句说法再上屏（数还是那对数，但话不能一个标点都不差）。"""
    old = "我趴这儿陪你一会儿。"
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        return old if calls["n"] == 1 else "今天攒下的那些，我一条条记着呢。"

    monkeypatch.setattr(pet_llm, "chat", fake)
    d = client.post("/api/pet/say", json={
        "text": "今天怎么样",
        "history": [{"role": "user", "content": "今天怎么样"},
                    {"role": "assistant", "content": old}],
    }).json()
    assert calls["n"] == 2
    assert d["source"] == "model" and d["text"] != old


def test_接口_两次都复读就照实数报账(client, monkeypatch):
    """两次都抄自己，也不能回一句「我在呢」——他问的是哪块最毛，得给模块和正确率。"""
    old = "数量关系那道题你算对了，我看见的。"
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: old)
    d = client.post("/api/pet/say", json={
        "text": "我哪里最毛",
        "history": [{"role": "assistant", "content": old}],
    }).json()
    assert d["source"] == "fallback"
    assert d["text"] != old and "最毛" in d["text"]


def test_探活接口_不把401个模型名倒给前端(client):
    d = client.get("/api/pet/llm").json()
    assert set(d) >= {"available", "model", "persona"}
    assert len(d["models"]) <= 1


def test_同一问题重问_输入端就提醒换说法():
    """复读最好别等到出口才发现：输入端把上一句当反面样本摆出来，
    说清「别用这个开头」。出口那道闸只留作保险。"""
    facts = _facts("今天怎么样")
    history = [{"role": "user", "content": "今天怎么样"},
               {"role": "assistant", "content": "你今天学了130分钟，正确率60%。"}]
    same = P.build_messages("今天怎么样", facts=facts, history=history)[-1]["content"]
    fresh = P.build_messages("今天怎么样", facts=facts, history=[])[-1]["content"]
    assert "你上一遍的原话是" in same
    assert "你上一遍的原话是" not in fresh


def test_兜底_同一件事重问要认一句刚说过():
    """两次都被拦的时候，兜底不能还是那一条：界面上两条一样的泡泡，
    看着就是卡住了。认一句「刚说过啦」，数照旧，话不一样。"""
    facts = _facts("今天怎么样")
    first = P.fallback("今天怎么样", facts=facts)
    again = P.fallback("今天怎么样", facts=facts, repeat=True)
    assert first != again
    assert again.startswith("刚说过啦，") and "130" in again


def test_兜底_同一件事重问要认一句刚说过():
    """两次都被拦的时候，兜底不能还是那一条：界面上两条一样的泡泡，
    看着就是卡住了。认一句「刚说过啦」，数照旧，话不一样。"""
    facts = _facts("今天怎么样")
    first = P.fallback("今天怎么样", facts=facts)
    again = P.fallback("今天怎么样", facts=facts, repeat=True)
    assert first != again
    assert again.startswith("刚说过啦，") and "130" in again


def test_闸_问账时不许把账安到他嘴上():
    """「82 分钟，你自己跟我说的」——他没说过，那数是记录算出来的。
    这种错位比报错数更伤：他第一反应是「我什么时候说过」。"""
    facts = _facts("今天怎么样")
    for bad in ("130分钟，60%对。你自己跟我说的。", "130分钟，你亲口说的。"):
        ok, why = P.check_reply(bad, facts=facts, user_text="今天怎么样")
        assert not ok and "说成是他跟你说的" in why
    ok, why = P.check_reply("130分钟，记录里就这么写的。", facts=facts, user_text="今天怎么样")
    assert ok, why


def test_闸_问账时不许把账安到他嘴上():
    """「82 分钟，你自己跟我说的」——他没说过，那数是记录算出来的。
    这种错位比报错数更伤：他第一反应是「我什么时候说过」。"""
    facts = _facts("今天怎么样")
    for bad in ("130分钟，60%对。你自己跟我说的。", "130分钟，你亲口说的。"):
        ok, why = P.check_reply(bad, facts=facts, user_text="今天怎么样")
        assert not ok and "说成是他跟你说的" in why
    ok, why = P.check_reply("130分钟，记录里就这么写的。", facts=facts, user_text="今天怎么样")
    assert ok, why
