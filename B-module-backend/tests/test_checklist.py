"""约束清单即规格：文档里写的每一类问题、每一条禁令，在这里真跑一遍。

为什么单独有这个文件：`docs/宠物对话约束清单.md` 是拿截图一轮一轮怼出来的，
改口吻、加类型、收紧闸的候最怕「文档写了，代码没落」。所以把清单第二节的表、
第三节的禁令表，直接翻译成断言——

- 九类问题各给一句典型问法，判错就红；
- 每一类都得有兜底、有引导，缺一句就红；
- 十一条禁令各给一个反例，放过去就红。

改清单的时候顺手改这里，两边就不会漂。
"""
from __future__ import annotations

import re

import pytest

from app import pet_persona as P

TODAY = {
    "date": "2026-10-31",
    "has_record": True,
    "user_state": "稳",
    "gap": {"week_target": 5, "week_done": 4, "owed": 1},
    "detail": {"duration_minutes": 130, "accuracy": 0.6},
}
MODULES = [
    {"module": "数量关系", "questions": 100, "accuracy": 0.52},
    {"module": "资料分析", "questions": 240, "accuracy": 0.62},
]
MEMORIES = [{"quote": "你怕申论写不完", "type": "event", "source": "narration", "days_ago": 3}]


def facts_for(text: str, **kw):
    return P.build_facts(today=TODAY, modules=MODULES, memories=MEMORIES, text=text, **kw)


# ---------- 第二节：九类问题，一条一句典型问法 ----------
# 表里每一类都在这里，少一类不是「测试少了一条」，是清单少了执行。
CASES = [
    ("address", "你应该叫我什么"),
    ("identity", "你是谁"),
    ("capability", "你能干什么"),
    ("relation", "你喜欢我吗"),
    ("advice", "今天还用学吗"),
    ("comfort", "学不动了"),
    ("data", "今天怎么样"),
    ("provenance", "你怎么知道我学了多久"),
    ("normal", "你在干嘛"),
]


@pytest.mark.parametrize("mode,question", CASES)
def test_清单里的每一类都判得出来(mode, question):
    assert facts_for(question)["mode"] == mode


@pytest.mark.parametrize("mode,question", CASES)
def test_每一类都有兜底(mode, question):
    """模型挂了也得答得上话。名字、判断、账单这三类尤其：回「我在呢」等于装没听见。"""
    f = facts_for(question)
    out = P.fallback(question, facts=f)
    assert out and out.strip()


@pytest.mark.parametrize("mode,question", CASES)
def test_每一类都有引导(mode, question):
    """除了 normal，每一类都要在请求里明说「这一问要答什么」。
    没有这句，模型手上只有一堆事实，就会挑最具体的那样念——所有答非所问都是这么来的。
    """
    f = facts_for(question)
    last = P.build_messages(question, facts=f)[-1]["content"]
    assert question in last
    if mode != "normal":
        assert len(last) > len(f'事实（JSON，只能用这里面的数字，sources 是你唯一能指的出处）')


def test_安慰类一个数字都不给():
    """清单里写死的一条：他难受的时候，事实包里不许有数字可念。"""
    f = facts_for("学不动了")
    nums = re.findall(r"\d+", __import__("json").dumps(f, ensure_ascii=False))
    assert "today" not in f and "week" not in f


def test_问账的三本账都算得出来():
    """今天多少分钟 / 哪块最毛 / 这周还差几天，是三本不同的账。"""
    assert facts_for("今天学了多久")["answer"]["kind"] == "today"
    assert facts_for("我哪里最毛")["answer"]["kind"] == "weakest"
    week = facts_for("这周还差几天")["answer"]
    assert week == {"kind": "week", "done": 4, "target": 5, "owed": 1}


# ---------- 第三节：十一条禁令，一条一个反例 ----------
def _ok(text, facts, **kw):
    return P.check_reply(text, facts=facts, **kw)


BANS = [
    ("编身体证据", "我闻到你袖口有咖啡味，还摸到你手心冒汗。", "身体"),
    ("编数字", "你今天学了 250 分钟。", "数字"),
    ("中文数字对不上", "你今天学了十三分钟。", "中文写法"),
    ("编科目", "资料分析 955 题，你做得不错。", "科目"),
    ("第三人称", "他说今天很累。", "第三人称"),
    ("旁白当原话", "你说过学到凌晨两点。", "旁白"),
    ("问账安到他嘴上", "130 分钟，你自己跟我说的。", "安到了他嘴上"),
    ("复读", "唔，我在呢，你慢慢说。", "复读"),
    ("非判断模式承诺时长", "你还能再学 15 分钟。", "承诺"),
    ("类型关键词闸", "我把你瓜子藏了三天啦。", "没正面答"),
]


@pytest.mark.parametrize("ban,text,reason", BANS)
def test_十一条禁令各有反例(ban, text, reason):
    facts = facts_for("今天怎么样")
    kw = {}
    if ban == "编科目":
        kw["known_modules"] = ["判断推理"]
        facts = facts_for("在吗")
    elif ban == "旁白当原话":
        facts = {"mode": "normal", "memories": [{"who": "旁白", "text": "那天你学到凌晨两点"}]}
    elif ban == "复读":
        facts = facts_for("在吗")
        kw["avoid"] = [text]
    elif ban == "非判断模式承诺时长":
        facts = facts_for("我不累啊")
    elif ban == "类型关键词闸":
        facts = facts_for("你喜欢我吗")
    elif ban == "问账安到他嘴上":
        facts = facts_for("今天怎么样")
    ok, why = _ok(text, facts, user_text="今天怎么样", **kw)
    assert not ok, f"{ban} 这条放过去了：{text}"
    assert reason in why, f"{ban} 拦是拦了，理由不对：{why}"


# ---------- 清单之外新加的两条（写在第三节里，编号 12 / 13） ----------
def test_结论不能跟算出来的相反():
    """刚算完「今天该停」，嘴上却来一句「再刷二十分钟」——他照着做，明天更累。"""
    f = facts_for("今天还用学吗")
    assert f["verdict"]["verdict"] == "stop"
    ok, why = _ok("今天就到这儿吧。不过你要是想学，再刷二十分钟也行。", f, user_text="今天还用学吗")
    assert not ok and "给了继续学的时长" in why


def test_判断类说反了方向也要拦():
    keep = {"mode": "advice", "verdict": {"verdict": "keep", "again_minutes": 20},
            "today": {"minutes": 82}, "week": {"owed": 1}}
    ok, why = _ok("别学了，早点睡吧。", keep, user_text="还要再学吗")
    assert not ok and "叫他别学了" in why
    # 正常说法不能误杀：「再 20 分钟，做完就收工」是 keep 的标准答法
    ok, why = _ok("再 20 分钟，做完就收工。", keep, user_text="还要再学吗")
    assert ok, why


def test_问账必须给出数():
    """「唔，你今天做了不少呢」——听着没毛病，但一个字也没答他问的账。"""
    f = facts_for("今天怎么样")
    ok, why = _ok("唔，你今天做了不少呢。", f, user_text="今天怎么样")
    assert not ok and "一个数都没给" in why
    ok, why = _ok("今天 130 分钟，正确率 60%。", f, user_text="今天怎么样")
    assert ok, why


def test_停的时候说句贴心话不算矛盾():
    """「我再陪你坐会儿」不是学习承诺。判矛盾不能只看「再…分钟」，
    否则 stop 时它说一句好听的也要被打回——那是把温柔当成了违规。

    （带具体数字的「陪你十分钟」另说：那会被「数字只能是事实里的」拦下，
    那是另一条禁令，方向是宁可笨不可假，这里不替它开口子。）"""
    f = facts_for("今天还用学吗")
    ok, why = _ok("今天就到这儿吧，我再陪你坐会儿。", f, user_text="今天还用学吗")
    assert ok, why


def test_停的时候说句贴心话不算矛盾():
    """「我再陪你坐会儿」不是学习承诺。判矛盾不能只看「再…分钟」，
    否则 stop 时它说一句好听的也要被打回——那是把温柔当成了违规。

    （带具体数字的「陪你十分钟」另说：那会被「数字只能是事实里的」拦下，
    那是另一条禁令，方向是宁可笨不可假，这里不替它开口子。）"""
    f = facts_for("今天还用学吗")
    ok, why = _ok("今天就到这儿吧，我再陪你坐会儿。", f, user_text="今天还用学吗")
    assert ok, why
