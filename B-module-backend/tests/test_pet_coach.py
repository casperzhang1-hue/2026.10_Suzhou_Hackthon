"""团团的判断：该不该继续学。

这组用例盯的是一件事：**它得给一个明确结论，而且结论有依据**。

用户的原话是「这个回答一点都不智能」——问「所以我今天就不用学习了吗」，
它答「我帮你剥了颗瓜子搁在题本上」。温柔，但一个字都没回答。

所以这里断言的全是「结论对不对」和「凭什么」，
而不是措辞好不好听。措辞交给模型，结论不许模型碰。
"""
from app import pet_coach as C
from app import pet_persona as P

MODULES = [
    {"module": "判断推理", "accuracy": 0.42, "questions": 120},
    {"module": "资料分析", "accuracy": 0.68, "questions": 955},
]


def _today(*, minutes=0, acc=None, energy=80, late=False, owed=1, done=4):
    return {
        "has_record": minutes > 0,
        "detail": {"duration_minutes": minutes, "accuracy": acc, "energy": energy,
                   "late_night": late, "completion": min(1.2, minutes / 80)},
        "gap": {"week_done": done, "week_target": 5, "owed": owed},
        "pet_state": "steady",
        "user_state": "稳",
    }


# ---- 今天还没开始 ----

def test_没记录_白天给一个很小的起手量():
    v = C.judge(today=_today(), hour=15, modules=MODULES)
    assert v["verdict"] == "start"
    assert v["again_minutes"] == 15      # 不能一上来就「补满 80」，那样谁来都不动


def test_没记录_晚上起手量更小():
    v = C.judge(today=_today(), hour=22, modules=MODULES)
    assert v["verdict"] == "start"
    assert v["again_minutes"] == 10


def test_没记录_过了23点就别开新账():
    assert C.judge(today=_today(), hour=23, modules=MODULES)["verdict"] == "stop"


# ---- 已经达标 ----

def test_达标就停_不加时长():
    """够了就是够了。再加时长不加分，只加疲劳。"""
    v = C.judge(today=_today(minutes=90, acc=0.62), hour=20, modules=MODULES)
    assert v["verdict"] == "stop"
    assert "90" in v["why"]              # 理由里必须有真数，否则像敷衍


def test_达标但本周还欠_说明天补():
    v = C.judge(today=_today(minutes=90, acc=0.62, owed=1), hour=20, modules=MODULES)
    assert v["verdict"] == "stop"
    assert "1" in v["why"]               # 「本周还差 1 天」也要说出来


def test_达标但正确率不到一半_别堆时长去复盘():
    v = C.judge(today=_today(minutes=90, acc=0.38), hour=20, modules=MODULES)
    assert v["verdict"] == "switch"
    assert v["module"] == "判断推理"      # 弱科，且题量够样本


# ---- 没达标 ----

def test_没达标_白天给一段但不用补满():
    v = C.judge(today=_today(minutes=30, acc=0.62), hour=15, modules=MODULES)
    assert v["verdict"] == "keep"
    assert v["again_minutes"] == 40       # 还差 50，但一次只给 40
    assert v["short_by"] == 50


def test_没达标_晚上只给20分钟():
    v = C.judge(today=_today(minutes=30, acc=0.62), hour=22, modules=MODULES)
    assert v["verdict"] == "keep"
    assert v["again_minutes"] == 20


def test_没达标_熬过夜就别再加():
    v = C.judge(today=_today(minutes=30, acc=0.62, late=True), hour=20, modules=MODULES)
    assert v["verdict"] == "stop"


def test_没达标_正确率低就换活_不加时长():
    v = C.judge(today=_today(minutes=40, acc=0.35), hour=20, modules=MODULES)
    assert v["verdict"] == "switch"
    assert v["module"] == "判断推理"


def test_没达标_精力见底就去睡():
    v = C.judge(today=_today(minutes=30, acc=0.62, energy=18), hour=20, modules=MODULES)
    assert v["verdict"] == "stop"


def test_没达标_过了23点就明天补():
    v = C.judge(today=_today(minutes=30, acc=0.62), hour=23, modules=MODULES)
    assert v["verdict"] == "stop"
    assert v["short_by"] == 50


# ---- 难受压过一切 ----

def test_难受的时候一律停_不看数据():
    v = C.judge(today=_today(minutes=10, acc=0.3), hour=20, modules=MODULES, sad=True)
    assert v["verdict"] == "stop"
    assert v["tone"] == "gentle"


def test_难受时不报计划_事实包里一个数字都不给():
    facts = P.build_facts(today=_today(minutes=30, acc=0.62), modules=MODULES,
                          memories=[], text="我好累，今天还用学吗")
    assert facts["mode"] == "advice"
    assert facts["verdict"]["verdict"] == "stop"
    assert "today_minutes" not in facts["verdict"]   # 难受时不许说「你今天 30 分钟」
    assert "again_minutes" not in facts["verdict"]


# ---- 意图：什么才算在要主意 ----

def test_意图_所以今天不用学了吗算要主意():
    """用户截图里那句原话。它必须被当成提问，而不是一句感慨。"""
    assert P._asks_advice("所以我今天就不用学习了吗")


def test_意图_还要再学一会儿吗算要主意():
    """这句不长得像「该不该」，但就是在问，实测漏判过一次。"""
    assert P._asks_advice("那我今天还要再学一会儿吗")


def test_意图_我今天做了什么是在问账本():
    """「做了什么」结尾的「么」不是疑问语气，这一问要走数据模式报数。"""
    assert not P._asks_advice("我今天做了什么")


def test_意图_你睡了吗是在问它():
    assert not P._asks_advice("你睡了吗")


def test_意图_我不累啊不算难受():
    """「不」是反驳，不是示弱。判错就会掉进安慰模式，一个数都不给。"""
    assert not P.looks_sad("我不累啊")
    assert not P.looks_sad("我不困，还能再来一会儿")


def test_意图_我是不是特别笨算难受():
    """「是不是」里的「不」不是否认，别把该安慰的一句判成闲聊。"""
    assert P.looks_sad("我是不是特别笨")


def test_意图_真难受照旧认出来():
    assert P.looks_sad("我今天真的好累，感觉学不动了")


# ---- 闸：答了才算答 ----

def _advice_facts(**verdict):
    base = {"verdict": "stop", "action": "今天够了", "tone": "firm"}
    base.update(verdict)
    return {"mode": "advice", "verdict": base, "today": {"minutes": 82}, "week": {"owed": 1}}


def test_闸_只安慰不给结论要拦():
    ok, why = P.check_reply("你真的很努力了。", facts=_advice_facts(),
                            user_text="所以我今天就不用学习了吗")
    assert not ok and "没给结论" in why


def test_闸_给了结论就放行():
    ok, why = P.check_reply("今天够了，明天再补。", facts=_advice_facts(),
                            user_text="所以我今天就不用学习了吗")
    assert ok, why


def test_闸_建议时长必须是算出来的那个数():
    facts = _advice_facts(**{"verdict": "keep", "again_minutes": 20})
    ok, why = P.check_reply("再 25 分钟就好。", facts=facts, user_text="还要再学吗")
    assert not ok and "算出来的" in why


def test_闸_算好的时长能说():
    facts = _advice_facts(**{"verdict": "keep", "again_minutes": 20})
    ok, why = P.check_reply("再 20 分钟，做完就收工。", facts=facts, user_text="还要再学吗")
    assert ok, why


def test_闸_不在判断模式不许承诺时长():
    """实测「我不累啊」这种闲聊，它自己接了一句「还能再学 15 分钟」——
    15 是图上题数，数是真的，但那句话没有任何依据。"""
    facts = {"mode": "normal", "today": {"minutes": 82}, "week": {"owed": 1}}
    ok, why = P.check_reply("你还能再学 15 分钟。", facts=facts, user_text="我不累啊")
    assert not ok and "时长" in why


def test_闸_闲聊里报今天的时长不算承诺():
    facts = {"mode": "normal", "today": {"minutes": 82}, "week": {"owed": 1}}
    ok, why = P.check_reply("你今天已经 82 分钟了。", facts=facts, user_text="我今天怎么样")
    assert ok, why


# ---- 模型挂了也得有答复 ----

def test_兜底_判断能说出口():
    assert "20" in C.fallback(verdict="keep", again_minutes=20, seed="")
    # 判了停就得说停，不能给一句「我在呢」糊过去
    assert "明天" in C.fallback(verdict="stop", seed="")


def test_兜底_没有时长就不硬编():
    assert "分钟" not in C.fallback(verdict="keep", again_minutes=None, seed="")


# ---- 洗稿：该死的空话删掉，别把整句连坐 ----

def test_洗稿_听见了删掉而不是拦整句():
    """踩过的坑：一开始把「我听到了」放进黑名单拦整句，结果模型重试两次都带它，
    一句「你刚说太赶，我听到了。我趴你手边」硬是变成了「模型没接上，它凭记忆说」。
    空话该删，但后面那个动作得留下。"""
    out = P.sanitize("你刚说太赶，我听到了。我趴你手边，唔。")
    assert "我听到了" not in out
    assert "我趴你手边" in out
    assert "，。" not in out and "。，" not in out


def test_洗稿_听了的几种说法都删():
    for raw in ("我听见了。那你先歇会儿。", "我懂了，也听懂了。歇着吧。"):
        out = P.sanitize(raw)
        assert "听见了" not in out and "听懂了" not in out
        assert out.strip()


def test_不在判断模式_时长承诺整句删掉而不是拦():
    """实测拦整句的代价是掉兜底。删掉那个子句，后半句反而是好话。"""
    out = P.strip_commit("那我再学 15 分钟，你刚传的图里还有 9 题对得挺稳。")
    assert "15" not in out
    assert "9 题" in out
    assert out.startswith("你刚传")


def test_时长承诺是整句时候变成空():
    """删空就交给兜底，但不许留半句残话。"""
    assert P.strip_commit("那我再学 15 分钟。") == ""


def test_洗稿_你刚说这种复读开头要剥掉():
    """实测它会连着三轮说「你刚说太赶，现在又说不累呀」——
    前半句复读他的话，后半句像数落。两句都不是安慰。"""
    out = P.sanitize("你刚说太赶，现在又说不累呀。我推个瓜子给你，歇会儿再战。")
    assert not out.startswith("你刚说")
    assert "现在又说" not in out
    assert "我推个瓜子给你" in out        # 后面那句才是真话，得留着
