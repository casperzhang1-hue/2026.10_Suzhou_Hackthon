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
    # 「我今天做了什么」问的是账，不是要主意（早先它被判成 advice，模型自己编了个时长）。
    # 现在走 data：第一句该说什么由 answer 算好，模块和正确率照旧带口径。
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="我今天做了什么")
    nums = []
    _all_numbers(facts, nums)
    assert facts["mode"] == "data"
    assert facts["answer"] == {"kind": "today", "minutes": 130, "accuracy_pct": 60}
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
    ok, why = P.check_reply("你今天 130 分钟，对了六成呢", facts=_facts(), user_text="今天怎么样")
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
    ok, _ = P.check_reply("你记得吃点东西再学呀。", facts=_facts("我在学"), user_text="我在学")
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
    ok, _ = P.check_reply("唔，我在呢。", facts=_facts("在吗"), user_text="在吗")
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
        return old if calls["n"] == 1 else "数量关系最毛，52%，我再帮你翻翻。"

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
def test_闸_问账时不许把账安到他嘴上():
    """「82 分钟，你自己跟我说的」——他没说过，那数是记录算出来的。
    这种错位比报错数更伤：他第一反应是「我什么时候说过」。"""
    facts = _facts("今天怎么样")
    for bad in ("130分钟，60%对。你自己跟我说的。", "130分钟，你亲口说的。"):
        ok, why = P.check_reply(bad, facts=facts, user_text="今天怎么样")
        assert not ok and "安到了他嘴上" in why
    # 「记录里写着」是真的，不能一起拦——拦真话等于把它逼回兜底
    ok, why = P.check_reply("130分钟，记录里就这么写的。", facts=facts, user_text="今天怎么样")
    assert ok, why

# ---------- 名字：谁是谁 ----------
# 用户截图：「团团我叫什么」→「你叫我团团时，我耳朵尖尖的」；
# 「你应该叫我什么」→「你叫我团团就行啦」。两问问的都是**他的**名字，
# 答的都是它自己的名字。流利，但答的是另一件事。
def test_名字_问我叫什么走称呼模式():
    for q in ("团团我叫什么", "你应该叫我什么", "你还记得我叫什么吗", "我是谁"):
        facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text=q)
        assert facts["mode"] == "address", q
def test_名字_问你叫什么走身份模式():
    for q in ("你叫什么", "你是谁", "团团你叫什么名字"):
        facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text=q)
        assert facts["mode"] == "identity", q
def test_名字_忘了就是忘了_不许编():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="你应该叫我什么")
    assert facts["known_name"] is None
    ok, why = P.check_reply("团团是你喊我的名字呀，别的都不行。", facts=facts,
                            user_text="你应该叫我什么")
    assert not ok and "我自己的名字" in why
    ok, why = P.check_reply("唔，你还没告诉我你叫什么呢，说给我听听呀。", facts=facts,
                            user_text="你应该叫我什么")
    assert ok, why
def test_名字_记住了就要叫出来():
    with_name = [{"quote": "你叫林一", "type": "name", "name": "林一", "days_ago": 1}]
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=with_name, text="你应该叫我什么")
    assert facts["known_name"] == "林一"
    ok, why = P.check_reply("当然叫林一呀，我记着呢。", facts=facts, user_text="你应该叫我什么")
    assert ok, why
    ok, deny = P.check_reply("你还没告诉我你叫什么呢。", facts=facts, user_text="你应该叫我什么")
    assert not ok and "却没叫出来" in deny
def test_名字_问你是谁_得报自己的名字():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="你是谁")
    ok, why = P.check_reply("唔，我听着呢。", facts=facts, user_text="你是谁")
    assert not ok and "自己的名字" in why
    ok, why = P.check_reply("我叫团团，一只爱藏瓜子的仓鼠。", facts=facts, user_text="你是谁")
    assert ok, why
def test_名字_接口_他报了名字_下次就能叫出来(client, monkeypatch):
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "唔，好呀。")
    client.post("/api/pet/say", json={"text": "我叫林一", "history": []})
    d = client.post("/api/pet/say", json={"text": "你应该叫我什么", "history": []}).json()
    assert d["facts"]["mode"] == "address"
    assert d["facts"]["known_name"] == "林一"

# ---------- 闲聊里的两类实问：能干什么、要不要好 ----------
# 用户截图之外的同类病：问「你能干什么」，答「我帮你把瓜子藏进腮帮子啦」；
# 问「你喜欢我吗」，答「我把你瓜子藏了三天」。都答得挺可爱，但一个字没答他。
def test_能做什么_得说得出能做什么():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="你能干什么")
    assert facts["mode"] == "capability" and len(facts["skills"]) >= 2
    ok, why = P.check_reply("我帮你把瓜子藏进腮帮子啦，想吃就来摸摸我。", facts=facts,
                            user_text="你能干什么")
    assert not ok and "小动作" in why
    ok, why = P.check_reply("你给我看截图，我就知道你做了多少；你说过的事我也记着。",
                            facts=facts, user_text="你能干什么")
    assert ok, why
def test_关系_得正面答():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="你喜欢我吗")
    assert facts["mode"] == "relation"
    ok, why = P.check_reply("我把爪子藏了三天啦。", facts=facts, user_text="你喜欢我吗")
    assert not ok and "没正面答" in why
    ok, why = P.check_reply("喜欢呀，我天天在这儿等你。", facts=facts, user_text="你喜欢我吗")
    assert ok, why
def test_名字_忘了能删_删了就不叫了(client, monkeypatch):
    """他改名了、或者当初手滑，库里得能删。留着一条过期的名字，它会一直叫错。"""
    monkeypatch.setattr(pet_llm, "chat", lambda *a, **k: "唔。")
    client.post("/api/pet/say", json={"text": "我叫林一", "history": []})
    items = client.get("/api/memories").json()["items"]
    name_item = [m for m in items if m.get("type") == "name"][-1]
    assert client.delete(f"/api/memories/{name_item['id']}").json()["deleted"] is True
    d = client.post("/api/pet/say", json={"text": "你应该叫我什么", "history": []}).json()
    assert d["facts"]["known_name"] is None

# ---------- 复读的「同一件事」按意思判，不按字面 ----------
# 实测（2026-11-01 真机）：先问「再学一会儿吗」，再问「今天还用学吗」，
# 它答的还是那句「今天够了，82分钟过了80的线」。两句问的是一件事，答案像是对的，
# 但按字面分堆把它判成了「答非所问」，打回两次，最后掉兜底——他听到一句模板。
# 所以「同一件事」要按意图判：同一个意思换个问法，答案相似是正常的。
def test_复读_换个问法问同一件事不算答非所问():
    hist = [{"role": "user", "content": "再学一会儿吗"},
            {"role": "assistant", "content": "今天够了，82分钟过了80的线。"}]
    other, same = P.split_recent_replies(hist, "今天还用学吗")
    assert other == [] and same == ["今天够了，82分钟过了80的线。"]
def test_复读_换了件事仍然算答非所问():
    hist = [{"role": "user", "content": "今天怎么样"},
            {"role": "assistant", "content": "今天 130 分钟，正确率 60%。"}]
    other, same = P.split_recent_replies(hist, "你喜欢我吗")
    assert other == ["今天 130 分钟，正确率 60%。"] and same == []
def test_复读_换成问另一科就是另一本账():
    hist = [{"role": "user", "content": "资料分析怎么样"},
            {"role": "assistant", "content": "资料分析 62%，做了 240 题。"}]
    other, same = P.split_recent_replies(hist, "数量关系怎么样")
    assert other and not same
def test_名字类可以说你自己跟我说的():
    """名字确实是他说的，这句话是真话。以前一并拦下，问「你叫什么」两次被打回，
    最后掉进模板——真话被自己的闸挡住，是最冤的一种「笨」。"""
    with_name = [{"quote": "我叫林一", "type": "name", "name": "林一", "days_since": 1}]
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=with_name, text="你应该叫我什么")
    ok, why = P.check_reply("你叫林一呀，你自己跟我说的，我记着呢。", facts=facts,
                            user_text="你应该叫我什么")
    assert ok, why
def test_账类仍然不许安到他嘴上():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text="今天怎么样")
    ok, why = P.check_reply("今天 130 分钟，你自己跟我说的。", facts=facts, user_text="今天怎么样")
    assert not ok and "安到了他嘴上" in why
def test_问第二遍给结构_第三遍换侧重点():
    """光说「换个说法」它换不动——账就几个数，能换的词就那么几个。
    所以第二遍给一个相反的语序（先说为什么再说结论），第三遍起直接换侧重点
    （先说小动作，再把结论带出来）。"""
    facts = _facts("今天还用学吗")
    one = [{"role": "user", "content": "今天还用学吗"},
           {"role": "assistant", "content": "今天够了，82分钟过了80的线。"}]
    two = one + [{"role": "user", "content": "今天还用学吗"},
                 {"role": "assistant", "content": "今天够啦，都82分钟了。"}]
    a = P.build_messages("今天还用学吗", facts=facts, history=one)[-1]["content"]
    b = P.build_messages("今天还用学吗", facts=facts, history=two)[-1]["content"]
    assert "先说为什么" in a and "第 3 遍" in b

def test_瓜子是它自己的_方向不许说反():
    """真机连着说反两次：「我把你瓜子推过去啦」「我把你给的瓜子藏在腮帮里」。
    瓜子是它攒的、它分给他的；说成他的，整只宠物的立足点就塌了。"""
    facts = _facts("你在干嘛")
    for bad in ("我把你瓜子推过去啦。", "我把你给的瓜子藏在腮帮里了。", "你的瓜子我收起来了。"):
        ok, why = P.check_reply(bad, facts=facts, user_text="你在干嘛")
        assert not ok and "瓜子说成了他的" in why, bad
    # 正确方向不能误杀
    ok, why = P.check_reply("我把瓜子推给你啦。", facts=facts, user_text="你在干嘛")
    assert ok, why


def test_瓜子是它自己的_方向不许说反():
    """真机连着说反两次：「我把你瓜子推过去啦」「我把你给的瓜子藏在腮帮里」。
    瓜子是它攒的、它分给他的；说成他的，整只宠物的立足点就塌了。"""
    facts = _facts("你在干嘛")
    for bad in ("我把你瓜子推过去啦。", "我把你给的瓜子藏在腮帮里了。", "你的瓜子我收起来了。"):
        ok, why = P.check_reply(bad, facts=facts, user_text="你在干嘛")
        assert not ok and "瓜子说成了他的" in why, bad
    # 正确方向不能误杀
    ok, why = P.check_reply("我把瓜子推给你啦。", facts=facts, user_text="你在干嘛")
    assert ok, why


def test_问账重问要给数据模式里成立的换法():
    """问账的提示是「第一句说分钟数」，和「换个说法」直接打架——它照第一条办，
    出来的句子必然一模一样。所以换法得在数据模式里也成立：换语序，不换数字。"""
    facts = _facts("今天怎么样")
    hist = [{"role": "user", "content": "今天怎么样"},
            {"role": "assistant", "content": "今天 130 分钟，正确率 60%。"}]
    last = P.build_messages("今天怎么样", facts=facts, history=hist)[-1]["content"]
    assert "换个语序" in last and "优先于上面" in last and "数字一个都不许改" in last


def test_问账重问要给数据模式里成立的换法():
    """问账的提示是「第一句说分钟数」，和「换个说法」直接打架——它照第一条办，
    出来的句子必然一模一样。所以换法得在数据模式里也成立：换语序，不换数字。"""
    facts = _facts("今天怎么样")
    hist = [{"role": "user", "content": "今天怎么样"},
            {"role": "assistant", "content": "今天 130 分钟，正确率 60%。"}]
    last = P.build_messages("今天怎么样", facts=facts, history=hist)[-1]["content"]
    assert "换个语序" in last and "优先于上面" in last and "数字一个都不许改" in last


def test_问账重问_三本账各有各的换法():
    """「这周还差几天」里没有正确率，笼统说「先说正确率」会把这一支带沟里。
    实测它懵了，两次照抄，掉兜底。"""
    week = _facts("这周还差几天")
    hist = [{"role": "user", "content": "这周还差几天"},
            {"role": "assistant", "content": "这周 4 天了，还差 1 天。"}]
    last = P.build_messages("这周还差几天", facts=week, history=hist)[-1]["content"]
    assert "先说还差几天" in last and "正确率" not in last.split("这是他刚问过的")[-1]


def test_问账重问_三本账各有各的换法():
    """「这周还差几天」里没有正确率，笼统说「先说正确率」会把这一支带沟里。
    实测它懵了，两次照抄，掉兜底。"""
    week = _facts("这周还差几天")
    hist = [{"role": "user", "content": "这周还差几天"},
            {"role": "assistant", "content": "这周 4 天了，还差 1 天。"}]
    last = P.build_messages("这周还差几天", facts=week, history=hist)[-1]["content"]
    assert "先说还差几天" in last and "正确率" not in last.split("这是他刚问过的")[-1]
