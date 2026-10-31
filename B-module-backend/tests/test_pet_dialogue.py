"""两类新问题的规格：他问「刚才说了什么」，他说「有什么办法」。

这两个模式是补出来的，补的理由都写在 pet_persona 的注释里，这里只钉行为：

- ``recap``   他问「我们刚才聊到哪了」。以前这一问一个判定都不命中，
              掉进 normal 之后被答成报账（「你刚传的图里，23 分钟做了 15 题对 9 题」）。
- ``solution`` 他难受 **而且** 在问「那我该怎么办」。以前和 comfort 混在一起，
              而 comfort 的指令明写着「不要给办法」，于是他要办法、它给陪伴。

两条都需要一样东西：判对了不算完，出口还得验它真答了那件事。
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from app import pet_memory as M
from app import pet_persona as P

TODAY = {
    # 距今 9 天：既避开「今天」的口径，也留出余量，改天再跑这批用例也不会飘
    "date": (date.today() + timedelta(days=9)).isoformat(),
    "has_record": True,
    "user_state": "稳",
    "gap": {"week_target": 5, "week_done": 4, "owed": 1},
    "detail": {"duration_minutes": 82, "accuracy": 0.6},
}
MODULES = [{"module": "数量关系", "questions": 120, "accuracy": 0.52}]
# 一条真原话（有「我」）和一条系统旁白（以「你」开头）——安慰时只能用前者
MEMORIES = [
    {"quote": "我怕考不上", "type": "feeling", "source": "user", "days_ago": 0},
    {"quote": "断了一天，第二天就回来了", "type": "event", "source": "narration", "days_ago": 3},
]
HISTORY = [
    {"role": "user", "content": "我今天模考又崩了"},
    {"role": "assistant", "content": "那先别急着算题，我趴你手边。"},
    {"role": "user", "content": "那我今天还会不会太赶"},
    {"role": "assistant", "content": "不会，今天够了，去歇着。"},
]


def facts_for(text: str, **kw):
    return P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                         text=text, history=HISTORY, **kw)


# ---------- recap：他问「刚才说了什么」 ----------

@pytest.mark.parametrize("text", [
    "那我们刚刚说了什么",
    "我刚才说什么了",
    "我们聊到哪了",
    "你刚才说啥来着",
    "上一句是什么",
    "帮我回顾一下刚才",
    # 「你再讲一遍刚才那事」说的是同一件事，只是换了个动词
    "你再讲一遍刚才那事",
    "刚才那事你再说一遍",
    "复读一遍上句",
])
def test_问刚才说了什么都走_recap(text):
    assert facts_for(text)["mode"] == "recap"


@pytest.mark.parametrize("text", [
    "我刚才学了多久",      # 问的是账，不是话
    "我今天做了什么",      # 同上
    "我今天正确率多少",    # 同上
])
def test_问账不会被_recap_抢走(text):
    """「刚才」这个词同时出现在问话和问账里，词表必须分得开。"""
    assert facts_for(text)["mode"] != "recap"


def test_recap_把它的回答也给他():
    """这是 recap 存在的理由：他要复述的包括它自己说过什么，
    而其它模式刻意不给它的原话（给了就照抄）。"""
    facts = facts_for("我们刚才说了什么")
    recent = facts["recent"]
    assert any(r["who"] == "他" for r in recent)
    assert any(r["who"] == "我" for r in recent)
    assert any("模考又崩了" in r["text"] for r in recent)


def test_recap_不带账本():
    """他问的是话，事实包里就不该有账——给了它就会挑最具体的念。"""
    facts = facts_for("我们刚才说了什么")
    assert "answer" not in facts
    assert "memories" not in facts


def test_没有历史时不编():
    facts = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                          text="我们刚才说了什么", history=None)
    assert facts["mode"] == "recap" and facts["recent"] == []
    # 兜底也得认账，不能顺手报一串数
    text = P.fallback("我们刚才说了什么", facts=facts)
    assert "刚才没聊几句" in text and not re.search(r"\d", text)


# ---------- recap 的出口 ----------

def _ok(text: str, facts: dict, user_text: str, **kw):
    return P.check_reply(text, facts=facts, user_text=user_text, **kw)


def test_recap_复述自己的旧话不算复读():
    """复读闸对所有其它模式都有效，唯独 recap 要放行：
    它答的就是「我刚才说了什么」，复述必然和 avoid 里的句子重合。
    不放行的话，正确答案会被自己的闸打死，然后掉兜底。"""
    facts = facts_for("我们刚才说了什么")
    old = "不会，今天够了，去歇着。"
    ok, why = _ok("你刚才说模考又崩了，我回你不会太赶。", facts, "我们刚才说了什么",
                  avoid=[old], avoid_same=[old])
    assert ok, why


def test_recap_报账要被拦():
    """原实现的错答长这样：每个数都是真的，但一个字没回答他的问题。
    这里刻意不用带「图」的句子——那样会被引图闸先拦下，
    就分不清到底是哪道闸起了作用。"""
    facts = facts_for("我们刚才说了什么")
    ok, why = _ok("你今天做了 82 分钟，正确率 60%。", facts, "我们刚才说了什么")
    assert not ok and "复述" in why, why


def test_recap_逐字重播要被拦():
    """换个问法问同一件事，它把上一遍的复述原样又播了一遍——
    界面上就是两条一样的泡泡，正是最开始被截图骂的那个毛病。
    复述的内容本来就该相似，所以这道闸只认逐字重复，松一点会误杀真的复述。"""
    facts = facts_for("我们刚才说了什么")
    same = "你刚才在说模考崩了那件事，我把你刚说的那句藏进腮帮子了。"
    ok, why = _ok(same, facts, "刚才聊到哪了", avoid_same=[same])
    assert not ok and "换个说法" in why, why


def test_recap_复述内容相似但换了入口就放行():
    facts = facts_for("我们刚才说了什么")
    old = "你刚才在说模考崩了那件事，我把你刚说的那句藏进腮帮子了。"
    ok, why = _ok("你在说模考崩了那件事。我跟你说先别急着算题，我趴你手边。",
                  facts, "刚才聊到哪了", avoid_same=[old])
    assert ok, why


# ---------- solution：他难受，而且他要办法 ----------

@pytest.mark.parametrize("text", [
    "有什么办法让我不累呢",
    "我现在该怎么办",
    "怎么才能不那么慌",
    "给我点建议吧",
])
def test_要办法的走_solution(text):
    assert facts_for(text)["mode"] == "solution"


def test_只是示弱仍然走_comfort():
    """拆开的目的是各答各的，不是把安慰全变成建议。"""
    assert facts_for("我好累")["mode"] == "comfort"
    assert facts_for("我怕考不上")["mode"] == "comfort"


def test_solution_的做法里一个数字都没有():
    """这些是通用的小事，不碰他的账本，所以永远不算编造。"""
    for tip in facts_for("有什么办法让我不累呢")["tips"]:
        assert not re.search(r"\d", tip), tip


def test_solution_只给陪伴要被拦():
    facts = facts_for("有什么办法让我不累呢")
    ok, why = _ok("你累啦？我趴你手边歇会儿。", facts, "有什么办法让我不累呢")
    assert not ok and "办法" in why


def test_solution_复述处境也要被拦():
    """他知道自己有多惨，不用再听一遍。
    历史里写着「他更早说过：模考又崩了」，模型很容易拿这句当开场，
    于是问「怎么办」得到的是一段处境回放——和只给陪伴是同一种没答。"""
    facts = facts_for("有什么办法让我不累呢")
    ok, why = _ok("你刚说模考又崩了。把手机放远点，回来做最熟的那几道。",
                  facts, "有什么办法让我不累呢")
    assert not ok and "复述" in why, why


def test_solution_不给他翻旧账的料():
    """只给下一步该做什么。给了旧事它就当主体念（实测问「怎么提神」答「你刚说模考崩了」）。"""
    assert "memories" not in facts_for("有什么办法让我不累呢")


def test_solution_建议里的时长不算编造():
    """「你先闭眼三分钟」是动作，不是从库里抄的数。
    按报账的标准拦，会把一条正确的建议打回兜底——实测真的掉过一次。
    但「再学 30 分钟」那种承诺另有闸管着，不能一起放。"""
    facts = facts_for("有什么办法让我不累呢")
    ok, why = _ok("先闭眼三分钟，回来只做最熟的那几道。", facts, "有什么办法让我不累呢")
    assert ok, why
    ok, why = _ok("先歇会儿，等下再学 30 分钟。", facts, "有什么办法让我不累呢")
    assert not ok


def test_solution_给了具体做法就放行():
    facts = facts_for("有什么办法让我不累呢")
    ok, why = _ok("确实累了。把手机放到看不见的地方，回来只做最熟的那几道。",
                  facts, "有什么办法让我不累呢")
    assert ok, why


def test_solution_的兜底也给办法():
    facts = facts_for("有什么办法让我不累呢")
    text = P.fallback("有什么办法让我不累呢", facts=facts)
    assert text and "我在呢" not in text


# ---------- comfort：旁白不能冒充他的话 ----------

def test_安慰时只给他亲口说的():
    """seed 里那句「断了一天，第二天就回来了」是我们记的账，不是他的原话。
    实测放进去，模型就读成他做过的事，张口「你刚断了一天」——当场能被拆穿。"""
    facts = facts_for("我好累")
    assert facts["mode"] == "comfort"
    for m in facts["memories"]:
        assert m["who"] == "他"
        assert m["text"] == "我怕考不上"


def test_recap_跳过历史里的回看问答():
    """他连着问「刚才说了什么」时，历史最近的几轮全是前几遍的问句和前几遍的复述。
    照着那些复述，等于用答案答答案——实测第三遍的输出里，一大半是从第二遍搬来的。
    所以要从末尾往前摘，摘到真正的对话为止。"""
    hist = HISTORY + [
        {"role": "user", "content": "那我们刚刚说了什么"},
        {"role": "assistant", "content": "你在说模考崩了那件事。"},
        {"role": "user", "content": "刚才聊到哪了"},
        {"role": "assistant", "content": "你刚才说得太赶那件事。"},
    ]
    recent = P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES,
                           text="我们刚才说了什么呀", history=hist)["recent"]
    joined = " ".join(r["text"] for r in recent)
    assert "刚才聊到哪了" not in joined, joined
    assert "数量关系" in joined or "模考" in joined      # 摘完剩下的是真聊过的事


def test_recap_整段照搬_prev_回答要被拦():
    """字符重合率判不出这种：在旧话前后各加半句，比例掉到 0.7，
    可中间那二十个字一个字没改，界面上看着还是同一句。所以按连续子串判。"""
    facts = facts_for("我们刚才说了什么")
    old = "我趴你手边，把瓜子推过去，唔，先离开桌子走一圈，让眼睛歇一会儿啦。"
    cheated = "你在说模考崩了那件事，" + old
    ok, why = _ok(cheated, facts, "我们刚才说了什么", avoid_same=[old])
    assert not ok and "整段搬过来" in why, why


def test_recap_换了说法就放行():
    facts = facts_for("我们刚才说了什么")
    old = "我趴你手边，把瓜子推过去，唔，先离开桌子走一圈，让眼睛歇一会儿啦。"
    ok, why = _ok("你在说模考崩了那件事。我让你离开桌子走一走，眼睛先歇会儿。",
                  facts, "我们刚才说了什么", avoid_same=[old])
    assert ok, why


# ---------- 记忆抽取：疑问句不是事件 ----------

@pytest.mark.parametrize("text", [
    "那我今天还会不会太赶",
    "我该不该继续学",
    "我来得及吗",
    "我要不要现在开始",
])
def test_问句不进记忆(text):
    """库里真的出过这条脏数据：一句提问被当成「今天发生的事」存了下来，
    它下次说「你说过……」引出来的却是他自己的一句问话。"""
    assert M.classify(text) is None


@pytest.mark.parametrize("text,kind", [
    ("我今天模考又崩了", "feeling"),
    ("我决定明天开始背单词", "promise"),
    ("我讨厌数量关系", "prefer"),
])
def test_真交代的事照样记得住(text, kind):
    """收紧疑问句不能把真话一起收了——这是同一道闸的反向断言。"""
    assert M.classify(text) == kind


# ---------- 对话的连贯性 ----------
# 这几条钉的是「它手上有没有上一轮」。没有这三样，它就只能每次重新挑一样素材念，
# 界面上看着就是写死的程序：不接话、不认前一句、换个问法又从头介绍一遍。

def _hist(*pairs: tuple[str, str]) -> list[dict]:
    out: list[dict] = []
    for q, a in pairs:
        out.append({"role": "user", "content": q})
        out.append({"role": "assistant", "content": a})
    return out


def _ctx(text: str, history: list[dict], facts: dict | None = None) -> str:
    msgs = P.build_messages(text, facts=facts or {"mode": "normal"}, history=history)
    return "\n".join(m.get("content") or "" for m in msgs)


def test_它看得见自己上一轮答的话题():
    """以前它完全不知道自己上一句说了什么，只能重新挑素材念。
    现在给话题词——但不给整句，给了整句它会照抄。"""
    h = _hist(("我叫林一", "林一，我记着呢"))
    ctx = _ctx("我妈又催我报班了", h)
    assert "你上一轮答的是关于「林一」" in ctx
    assert "林一，我记着呢" not in ctx            # 原句不许出现，只给词


def test_短追问能认出是顺着上一句问的():
    """「判断推理呢」这种短句单看判不出在问什么——没有情绪词也没有问法词。
    不点出锚点，它就会当成全新话题，把素材从头再念一遍。"""
    h = _hist(("模考又崩了，判断推理错了一堆", "今天够了，先歇会儿吧"))
    ctx = _ctx("判断推理呢", h)
    assert "顺着「判断推理」往下问的" in ctx


def test_换了话题就不该有锚点():
    """反向断言：上一句没提过的东西，不能硬认成追问。"""
    h = _hist(("模考又崩了，判断推理错了一堆", "今天够了，先歇会儿吧"))
    ctx = _ctx("我妈又催我报班了", h)
    assert "往下问的" not in ctx


def test_这一句自己不会被当成历史():
    """这一句如果也在历史里，会被写成「他刚说的上一句：这一句」——
    它于是对着自己的话答一遍。"""
    h = _hist(("模考又崩了", "今天够了，先歇会儿吧"))
    h.append({"role": "user", "content": "那资料分析呢"})
    ctx = _ctx("那资料分析呢", h)
    assert "（他刚说的上一句：那资料分析呢）" not in ctx


def test_最近提过的事这轮别再提():
    h = _hist(("我今天累了", "歇会儿吧，别硬撑"),
              ("嗯", "嗯，我趴你手边陪你"))
    facts = {"mode": "normal", "memories": [{"who": "他", "text": "他嫌培训课烦"}]}
    ctx = _ctx("好无聊啊", h, facts)
    if "最近刚提过" in ctx:
        assert "培训课" in ctx


def test_不相关的话不算同一件事():
    """两句都落在同一个笼统档位时，光比 intent_key 会把它们判成同一件事——
    于是它拿答上一件事的那句当反面样本，去答一句全新的话。"""
    assert not P._same_topic("我明天想去看电影", "我们公司下周搬家")
    assert P._same_topic("我想去看电影", "电影几点开始")                   # 同一个话题
    assert P._same_topic("今天还用学吗", "再学一会儿吗")                   # 同义换问法
    # 单字重合不算：「又」「了」这种字几乎每句都有，撞上两个字不代表同一件事
    assert not P._same_topic("模考又崩了", "课又取消了")


def test_连着要主意_第二遍要从做法说起():
    """三遍都要主意，它每一遍都从「你累啦」开头，看着像同一句套了三个尾巴。
    第二遍起得直接给做法，而且不许抓着同一条建议不放。"""
    h = _hist(("我今天真的学不动了", "你累啦，我趴你手边"),
              ("有什么办法能让我不那么累", "你累啦，那就先离开桌子走一圈"))
    facts = {"mode": "solution", "tips": ["走一圈", "把手机放远", "洗把脸"]}
    ctx = _ctx("再给我出个主意", h, facts)
    assert "不许再认累" in ctx
    assert "挑一条和上一遍不同" in ctx


def test_要主意的说法要认得出来():
    """「出个主意」这类说法原先一个都没收，掉回 normal 就又答成陪伴——
    他要的还是办法。"""
    assert P._asks_solution("再给我出个主意")
    assert P._asks_solution("还有别的办法吗")
    assert P._asks_solution("支个招呗")


@pytest.mark.parametrize("text,which", [
    ("我到底叫什么来着", "mine"),
    ("我叫啥来着", "mine"),
    ("你还记得我叫什么吗", "mine"),
    ("你到底叫什么", "yours"),
    ("你叫啥来着", "yours"),
    ("你叫什么", "yours"),
])
def test_问名字_中间插字也要认出来(text, which):
    """「我到底叫什么来着」这种说法词表堆不完——他能插的字有几十种。
    判不出来就掉进 normal，问名字被答成递瓜子。方向也不能反：
    「我叫什么」是他的名字，「你叫什么」是它的名字。"""
    assert P._which_name(text) == which


@pytest.mark.parametrize("text,which", [
    ("我到底叫什么来着", "mine"),
    ("我叫啥来着", "mine"),
    ("你还记得我叫什么吗", "mine"),
    ("你到底叫什么", "yours"),
    ("你叫啥来着", "yours"),
    ("你叫什么", "yours"),
])
def test_问名字_中间插字也要认出来(text, which):
    """「我到底叫什么来着」这种说法词表堆不完——他能插的字有几十种。
    判不出来就掉进 normal，问名字被答成递瓜子。方向也不能反：
    「我叫什么」是他的名字，「你叫什么」是它的名字。"""
    assert P._which_name(text) == which
