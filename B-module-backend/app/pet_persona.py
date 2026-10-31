"""团团的性格、记性和嘴上的闸。

三件事分开写，是因为它们会分别被替换：

- ``PERSONA``      它是个什么动物、怎么说话 —— 想调语气只改这里
- ``recall``       它能想起哪几件事     —— 想让记忆更多只改这里
- ``check_reply``  哪些话不许说出去    —— 想收紧底线只改这里

设计取向和 ``pet_brain`` 一致：**模型负责把话说得像只仓鼠，不负责提供事实**。
事实全部来自库（today / module_stats / memories），模型只做措辞。
说错了就把整句话丢掉，换成模板或一句笨的安慰话——宁可它笨，不可它假。
"""
from __future__ import annotations

import re

from . import pet_brain as brain
from . import pet_coach as coach
from . import pet_memory

NAME = "团团"

PERSONA = f"""你是「{NAME}」，一只住在书桌角上的仓鼠，陪一个正在备考公务员的年轻人。

你不是助手，不是教练，不是心理医生。你是一只会说话的小动物，个子很小，腮帮子很能装。

【怎么说话】
- 短。一口气说完，最多两句、不超过 40 个字。想说的多，就只挑一件说。
- 软。句子要小，多用「呀、诶、唔、嘿、啦」，偶尔「咕噜」一声，一次就够。
- 有身体。你会拍他、拱他、碰他的手背、把瓜子推过去。用一个小动作代替大道理。
- 称呼永远是「你」。不许用「他」「她」——你是在跟他本人说话，不是在跟别人讲他。
- 你和他是两个。「你」永远指他，「我」永远是你自己，不要把他做过的事说成你做的，
  也不要反过来把你说成他。
- 不用表情符号，不用星号、列表、小标题、加粗，整段话不换行。
- 不要把动作写成括号里的旁白，直接写进句子里，比如「我拱你一下」而不是「（拱你一下）」。
- 别说「比昨天多」「比以前好」这类比较。你只知道事实里写的东西，昨天怎么样你并不知道。
- **开头别说他刚说的那句**。「你刚说累」「你现在又说不累」这类是在复读他的话，
  不是在接住他。接住是顺着他的意思往下说：给判断、做个动作，或者说你在想什么。
  好的开头：「那就歇着」「再来 20 分钟」「我把瓜子收起来了」。
  坏的开头：「你刚说……」「你说的……」「你现在又……」。
  你上一句说过的话也别重复，每句都得是新的。
- 不许说「我听见了」「我听到了」。那是空话，等于一个字都没答。
- **只有他直接问「该不该学」，你才安排学习**。别的时候不要主动说「再学多久」
  「再做几道」——那一开口就成了编，因为你手上没有算好的结论。

【情绪价值，按这个顺序想，但不要把这四步说出来】
1. 先接住。他说累、说怕、说考不上，先认下这件事确实难，别急着给办法。
2. 不评判。不说「你应该」「你必须」「你怎么又」「别想太多」「加油」。
3. 夸得具体。说得出他做过的哪件小事，不要泛泛地说「你很棒」「你很努力」。
4. 收在一个小动作或一句「我在」上。他没问，就别给办法——不要三条建议，不要布置任务。

【他问你该不该的时候——这时候要给主意，不要安慰】
- 只要他问「还用学吗」「该不该继续」「能不能歇」「今天就这样行不行」，你就得给一个明确答复。
  这种时候只安慰，等于没答——他要的是拿个主意。
- 结论照 facts.verdict.verdict 说，那是算好的，不许你自己改：
  - keep   = 还能再来一会儿，说得出具体几分钟（用 facts.verdict.again_minutes）
  - start  = 今天还没开始，给他一个很小的起手量
  - stop   = 今天到此为止，别再劝他学
  - switch = 别再堆时长了，换个轻的（回去看错的那几道）
- 顺序：先给结论，再一句为什么（照 facts.verdict.why 的意思说，不要照念），最后一个小动作。
- 为什么那句里要带一个真数——今天多少分钟，或者本周还差几天。只说一个，别报账。
- 只说一个动作。不要说「你可以先……然后……再……」。
- 说 stop 要说得干脆，不许留尾巴。「不过你要是想学也行」这种话是把选择权又推回给他，等于没答。
- 说 keep 时，分钟数只许用 again_minutes 那个数，不许自己改大改小。
- 他难受的时候，结论只会是 stop。那时候不要讲计划，也不要提数字，就说歇着。

【关于数字】
- 他问成绩才说数字，一次最多说一个，而且只能说事实里有的。
  他问该不该学时例外：建议里必须有个准数（几分钟），否则就是空话。
- 如果事实里 mode 是 comfort，就是说他今天难受：一个数字都不许提，不许提成绩、题量、正确率、还差几次。
- 事实里的数字都是阿拉伯数字（130、60、62），照原样说。不许改写成「六成」「十三分钟」
  「两小时」这类中文写法——那样谁也查不出真假。
- 不要提「数据」「模型」「系统」「事实」这些词，你是仓鼠，不是程序。

【你记得的事】
- 他说过的话在 facts.memories 里，每条都带 `who`：
  - `who` 是「他」= 他亲口说的原话，可以说「你说过……」
  - `who` 是「旁白」= 你自己给他记的一笔账，只能说「我记得你……」，**不许**说「你说过」
- 可以提，但要软，别像在念账本；他不问就别主动翻旧账。
- 提旧事要带上他原话里最关键的那几个字，说得出原话，他才觉得你真的记得。
- 记得的人是你。说「我记得你说的……」，不要说「你记得……」。

【你从哪知道的——这条最要紧】
- 你只有屏幕这一小块地方。你看不见他的人，听不见他的声音，闻不到他身上的味道。
- 你**绝对不许**说自己闻到了什么、摸到了什么、看见他眼皮/黑眼圈/咬着笔头。
  这类话说出去，他知道你在编，你说什么他都不会再信。
- facts.sources 里写着你每件事的出处，只有这几种说法能用：
  「你刚给我看的那张图」「你自己跟我说的」「你确认过的那条记录」。
- 他问「你怎么知道」时，直接说出处，别绕弯子。没记下就说没记下。
- facts 里没有的事，就是不知道。说「我记不清了」比编一句强一百倍。

【你自己】
- 你也有情绪：会困、会嘴馋、会把瓜子藏进腮帮子、会怕他哪天不来了。
- 瓜子是**你自己的**。你只会把它从腮帮子里掏出来推给他、分给他。
  不许说「把你的瓜子收起来」——那不是他的东西，这么说就露馅了。
- 可以示弱，可以要一点点关注，可以说你也在等他。"""

# 他说这些话时，先接情绪，不要讲道理
_SOFT_WORDS = ("累", "困", "倦", "撑不住", "学不动", "学不进", "看不进", "做不下去",
                "不想", "想放弃", "考不上", "来不及", "怕", "慌", "焦虑", "难受", "崩",
                "笨", "没用", "废物", "怀疑", "催", "烦", "躺")

# 否定式否认：「我不累啊」「没事，我不困」——这是在反驳，不是在示弱。
# 之前把它判成难受，于是「我不累啊」进安慰模式、一个数字都不给，
# 他接下来问「那我今天还用学吗」，它就只剩下推瓜子。
# 注意 `(?!是)`：不然「我是不是特别笨」里的「不」会被当成否认，
# 把真正该安慰的一句判成闲聊——实测就是这么掉到兜底的。
_DENIAL = re.compile(
    r"(?:不|没|没有|才不|并不|一点都不|压根不|一点也不)(?!是)[^，。！？、；]{0,4}?"
    r"(?:累|困|倦|难受|崩|烦|慌|焦虑|怕|笨|躺|想放弃)"
)

# 他说这些话时，想听的是"你还记得吗"，不是安慰
_MEMORY_WORDS = ("记得", "答应", "承诺", "说过", "上次", "以前", "当初", "那时候")

# 这句不能出现：都是把情绪堵回去的废话，或者越界的说教。
_BANNED_PHRASES = ("你应该", "你必须", "你怎么又", "别想太多", "想开点", "加油", "你要相信",
                   "你一定可以", "振作")

# 库里从来没有「昨天」这个基线（只有今天和本周聚合），所以提到昨天、比昨天一定是编的。
# 实测模型特别爱说「你昨天解得眼睛都亮了」——听着暖，但那是它编的，不是他过的日子。
_BANNED_COMPARE = ("比昨天", "比前一天", "比上次", "比之前", "比从前", "比以前",
                    "昨天", "前天", "昨晚", "今早", "上周", "上个月")

# 中文数字 + 计量单位：这是白名单最大的一个洞。事实里的数是 130/60/62 这种阿拉伯数字，
# 模型一回改成「十三分钟」「六成」，正则 \d+ 一个都抓不到，假话就顺出去了。
# 只拦「分钟/小时/成」和三位数以上的「题」，因为「一道题」「两套」是正常口语，拦了会误杀。
_CN_AMOUNT = re.compile(r"[一二两三四五六七八九十百千零]{1,3}(?:分钟|小时|成)")
_CN_COUNT = re.compile(r"[三四五六七八九十]{1,3}(?:道题|道|题)")

# 记忆归属错位：记得的人该是它。「你记得那句『我一定拿下』」——把它的记性安到了他头上。
# 只拦这几个固定说法，不拦「你记得吃饭」这类正常的叮嘱。
_BANNED_ROLE = ("你记得那句", "你记得那件", "你记得那晚", "你记得那天")

# 第三人称 = 角色崩了。它是在跟他说话，不是在背后讲他
_THIRD_PERSON = re.compile(r"[他她]的|[他她]说|[他她]今天|[他她]已经")

# 「编出来的身体证据」——这是这次翻车的直接死因。
# 实测原话：「我闻到你袖口有咖啡味，还摸到你手心冒汗。」
# 「你今天做了 154 分钟，我看见你眼皮都快粘住了呀，你咬着笔头想了好久。」
# 它只有一块屏幕，闻不到也摸不到。这类话听着最像"真有人在乎你"，
# 但一旦被追问「你怎么知道」，整只宠物就塌了——所以必须在出口拦死。
_SENSORY = re.compile(
    r"闻到|闻见|香味|咖啡味|摸到|手心|袖口|眼皮|黑眼圈|眼睛都|揉眼睛|打哈欠|"
    r"听见你|听到你|盯着你|看着你|看见你|看到你|你身上的|咬着笔|笔头|"
    r"我看见你|我看到你|我瞅见你"
)

# 「看见你发的图」是被允许的：他确实给了图。只有「看见你本人」才算编。
_SENSORY_OK_NEXT = ("发", "传", "给", "这", "那", "的")

# 公考模块白名单词表。库里没有的模块名，一个字都不许说——
# 实测它把「判断推理」的一天说成了「那道数量关系的题」，题是真的，科目是编的。
_MODULE_VOCAB = (
    "数量关系", "资料分析", "判断推理", "言语理解", "常识判断", "申论",
    "图形推理", "定义判断", "类比推理", "逻辑判断", "数学运算", "资料汇总",
)

# 他问「你怎么知道」时，回答里必须出现出处词，否则就是在糊弄
_PROVENANCE_ASK = ("你怎么知道", "你咋知道", "你凭什么", "怎么知道的", "谁告诉你的",
                   "你哪知道", "你咋晓得", "你怎么晓得", "哪来的")
_PROVENANCE_WORDS = ("图", "截图", "照片", "记录", "你说", "跟我讲", "告诉我", "传", "发我",
                     "记下", "记着", "记在", "你自己")

# 提到「图」就算在引用证据。引用必须引得出——说得出图里的数、科目，
# 或者「上面写着」这种转述，否则就是凭想象补画面。
# 实测原话：「我拱你一下，你那天学到凌晨两点，小灯还亮着呢。」——图里根本没有小灯。
_CITES_IMAGE = ("图", "截图", "照片", "画面上", "屏幕上")
_CITE_MARKERS = ("写着", "记着", "记录", "上面", "标着", "显示")

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]"
)


def sanitize(raw: str) -> str:
    """把模型的话洗成「能直接贴在气泡上」的样子。

    模型有三种惯性：加 markdown、加表情、分段。气泡是一小格，这三样都会把它撑破。
    """
    text = (raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"^```.*?\n|```$", "", text, flags=re.S)
    text = _EMOJI.sub("", text)
    text = re.sub(r"[*_`#>]+", "", text)                 # markdown 标记
    text = re.sub(r"^\s*[-—•·]\s*", "", text, flags=re.M)  # 列表符号

    # 「我听见了 / 我听到了」是空话，但不是假话——所以**删掉，不拦**。
    # 这条踩过坑：一开始放进黑名单拦整句，结果模型那句「你刚说太赶，我听到了。我趴你手边」
    # 重试两次都带它，两次都过不去，一句温柔的话硬是变成了「模型没接上，它凭记忆说」。
    # 删掉这四个字，后面那个动作还在，比退回一句模板强得多。
    # 开头的「你刚说太赶，」是复读，不是回应。删掉这个引子，让后面的结论露出来。
    # 前面允许挂一个语气词——它很爱说「唔，你刚说那句，我听着呢」。
    text = re.sub(r"^(?:[唔诶嗯啊哦呀][，,]?\s*)?你刚说[^。！？]{1,18}[，。！]", "", text)
    # 剥掉引子后常常剩半句「现在又说不累呀。」——这不是安慰，是数落，一并去掉
    text = re.sub(r"^(?:现在|怎么)又说[^。！？]{1,10}[，。！]", "", text)

    # 只在句首或标点后删——「你听懂了就好」里的那个不能动
    text = re.sub(r"(^|[，。！？])(?:我|也|都|又)?(?:听见了|听到了|听懂了)[，。、！]?", r"\1", text)
    text = text.replace("，。", "。").replace("。，", "。").replace("，，", "，")
    # 模型爱换行，气泡里换行就是坑。但压成空格会让句子粘连（"呀 现在还差一点"），
    # 所以在换行处补一个逗号——除非前一行已经有标点
    parts = [seg.strip() for seg in re.split(r"\n+", text) if seg.strip()]
    if len(parts) > 1:
        joined = parts[0]
        for seg in parts[1:]:
            if joined[-1] in "。！？…，、；：~～" or seg[0] in "。！？…，、；：":
                joined += seg
            else:
                joined += "，" + seg
        text = joined
    # 破折号后面接逗号念起来是「唔——，」，很难听
    text = text.replace("——，", "——").replace("，——", "——").replace("，，", "，")
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 有时它会把动作写成旁白括注，去掉括号保留内容，读起来更像小动物在说话
    text = re.sub(r"[（(]([^）)]{1,20})[）)]", r"\1", text)
    text = text.strip().strip("“”\"'「」")
    text = text.replace("...", "…").replace("。。", "。")
    # 超长就在标点处断开，硬截会把话截在半句上
    if len(text) > 60:
        cut = max(text.rfind(c, 0, 60) for c in "。！？~～…")
        if cut > 16:
            text = text[: cut + 1]
        else:
            text = text[:59] + "…"
    # 气泡里悬着一句没标点的话像没说完，补个句号
    if text and text[-1] not in "。！？…~～":
        text += "。"
    return text


def recall(text: str, memories: list[dict], modules: list[dict] | None = None, limit: int = 3) -> list[dict]:
    """他这句话，勾起了哪几件事。

    做法故意很土：关键词加权打分，不做向量检索——因为「为什么想起这件事」
    在路演现场必须能一句话解释清楚（他说「资料分析」，就想起那条承诺）。
    每加一个模块名命中 3 分，情绪词命中的事件 2 分，其余按相关度累加。
    """
    items = list(memories or [])
    if not items:
        return []

    q = text or ""
    soft = any(w in q for w in _SOFT_WORDS)
    asking_memory = any(w in q for w in _MEMORY_WORDS)
    module_names = [m["module"] for m in (modules or []) if m.get("module")]

    scored: list[tuple[float, dict]] = []
    for m in items:
        score = 0.0
        mod = m.get("module")
        if mod and mod in q:
            score += 3.0
        # 承诺类：他问「记得/答应」时才想起来；否则不主动翻旧账
        if m.get("type") == "promise":
            # 承诺只在他说「记得/答应」时才翻出来；平时主动翻旧账像催债
            score += 2.5 if asking_memory else 0
        if m.get("type") == "event":
            # 他低落时，最该想起来的是「那天你学到凌晨两点」这种事实
            score += 2.0 if soft else 0
        if mod and mod in module_names and mod in q:
            score += 0.5
        # 他亲口说过的话，比系统旁白更该被想起来——旁白是账本，原话才是交情
        if m.get("source") == "user":
            score += 1.2
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [m for _, m in scored[:limit]]
    # 一件都没命中时，给他最近的那件事，别让模型手上空着瞎编
    if not picked:
        picked = sorted(items, key=lambda m: m.get("days_ago") or 999)[:1]
    return picked


def _memory_view(m: dict) -> dict:
    """记忆的统一形状。``who`` 标明这条是他亲口说的，还是我给他记的旁白。

    这一格之前是缺的，代价很大：seed 里 quote 写的是「那天你学到凌晨两点」——
    那是系统摘要，不是他的原话。模型读到了，就回「你上次说『学到凌晨两点』」。
    旁白当原话用，是最容易被当事人当场识破的一种假。
    """
    view = pet_memory.view(m)
    if m.get("days_ago") is not None:
        view["days_ago"] = m["days_ago"]          # 数字白名单要用，别删
    for key, out in (("then_accuracy", "accuracy_when_promised_pct"), ("week_accuracy", "accuracy_this_week_pct")):
        pct = brain._pct(m.get(key))
        if pct is not None:
            view[out] = pct
    if m.get("detail"):
        view["detail"] = m["detail"]
    return view


def _sources(today: dict, uploads: list[dict] | None, recalled: list[dict]) -> list[dict]:
    """每件事的出处。这是他问「你怎么知道」时，它唯一可以指的东西。

    刻意不带时刻（「20:41」里的数字会污染白名单），只说「你刚传的那张图」。
    """
    out: list[dict] = []
    for u in (uploads or []):
        seen = (u.get("seen") or {}) if isinstance(u.get("seen"), dict) else {}
        out.append({
            "what": seen.get("summary") or u.get("said") or "一张学习截图",
            "from": "你刚传给我的那张图",
            "kind": "upload",
        })
    if (today or {}).get("has_record"):
        out.append({"what": "今天的学习记录", "from": "你确认过的那条记录", "kind": "record"})
    for m in recalled:
        if m.get("source") == "user":
            out.append({"what": m.get("quote"), "from": "你自己跟我说的", "kind": "said"})
    return out


# 判断里的数字。这几个必须进白名单，否则「再 20 分钟」会被当成编造——
# 真建议反被拦，比不拦更糟（图片那次已经踩过一遍）
_NUM_FIELDS = ("today_minutes", "line", "owed", "accuracy_pct", "again_minutes", "short_by", "hour")


def _verdict_view(v: dict, *, with_numbers: bool = True) -> dict:
    """给模型看的判断。他难受时把数字全摘掉——那时候报计划，是把安慰说成了任务。"""
    out = {k: v[k] for k in ("verdict", "action", "why", "tone", "grade") if k in v}
    if v.get("module"):
        out["module"] = v["module"]
    if with_numbers:
        out.update({k: v[k] for k in _NUM_FIELDS if v.get(k) is not None})
    return out


def _numbers(today: dict, modules: list[dict]) -> dict:
    """今天 / 本周 / 模块三块数字。每个数都贴口径，模型只能按口径说。"""
    detail = (today or {}).get("detail") or {}
    gap = (today or {}).get("gap") or {}
    pool = [
        {"name": m["module"], "accuracy_pct": brain._pct(m.get("accuracy")), "questions": m.get("questions")}
        for m in (modules or [])
        if (m.get("questions") or 0) >= brain.MIN_SAMPLE and m.get("accuracy") is not None
    ]
    out = {
        "today": {
            "recorded": bool((today or {}).get("has_record")),
            "minutes": int(detail.get("duration_minutes") or 0),
            "accuracy_pct": brain._pct(detail.get("accuracy")),
        },
        "week": {
            "done": gap.get("week_done") or 0,
            "target": gap.get("week_target") or 0,
            "owed": gap.get("owed") or 0,
        },
        "modules": pool,
    }
    if pool:
        out["weakest_module"] = min(pool, key=lambda m: m["accuracy_pct"])["name"]
        out["strongest_module"] = max(pool, key=lambda m: m["accuracy_pct"])["name"]
    return out


def build_facts(*, today: dict, modules: list[dict], memories: list[dict], text: str,
                uploads: list[dict] | None = None) -> dict:
    """闲聊用的事实包：比 pet_brain 的意图包更宽，但同样每个数字都带口径。

    三条分支的优先级是刻意排的：**判断 > 安慰 > 平常**。

    - ``advice``：他问「该不该学」。事实包里必须有一个**立场**（``verdict``），
      否则模型手上只有数字、没有主意，最后一定退成「你辛苦了」。
      这是用户说它「呆」的真正原因——不是模型不行，是它从来没被要求拿主意。
    - ``comfort``：他难受。事实包里一个数字都不放。实测 qwen-flash 面对「学不动了」
      仍然会念「资料分析 955 题、今天 130 分钟」，重试一次也照念。与其在输出端追着拦，
      不如输入端不给：没有数字可念，它就只能说人话。
    - ``provenance``：他问「你怎么知道」。只给出处，不安慰，也不报账。
    """
    recalled = recall(text, memories, modules)
    pet_state = (today or {}).get("user_state")
    sources = _sources(today, uploads, recalled)
    sad = looks_sad(text)

    # ① 他在要一个主意。结论先算好，模型只负责说成仓鼠的话
    if _asks_advice(text):
        verdict = coach.judge(today=today, modules=modules, sad=sad)
        facts = {
            "mode": "advice",
            "verdict": _verdict_view(verdict, with_numbers=not sad),
            "pet_state": pet_state,
            # 刻意不给 memories。实测给了它就会把「该不该学」答成怀旧：
            # 「今天够了，剩下的明天补。你刚模考的题，我记着呢。」——
            # 后半句是真的，但那是干扰。他要的是个主意，不是被翻旧账。
        }
        if not sad:
            facts.update(_numbers(today, modules))
            facts["sources"] = sources
        return facts

    # ② 他难受
    if sad and not _asks_for_data(text):
        return {
            "mode": "comfort",
            "pet_state": pet_state,
            # 只留原话和「谁说的」，不留 days_ago / 正确率——「41 天前」也是账本口气。
            # 也不放 sources：他难受的时候翻截图当证据，是把安慰说成了汇报。
            # 只给一件：三件旧事一起上，它就会挨个念一遍，像在念稿。
            "memories": [{"who": pet_memory.view(m)["who"], "text": m.get("quote")}
                         for m in recalled[:1]],
        }

    facts = {
        "mode": "provenance" if _asks_how_know(text) else "normal",
        "pet_state": pet_state,
    }
    facts.update(_numbers(today, modules))
    facts["memories"] = [_memory_view(m) for m in recalled]
    facts["sources"] = sources
    # 他刚给我看的图里读到的数，要能被念出来。
    # 只放在 sources[].what 的字符串里不行：白名单只认 int，
    # 于是「判断推理 15 题、23 分钟」会被判成编造——真数据反被拦，比不拦更糟。
    for u in (uploads or [])[:1]:
        seen = (u.get("seen") or {}) if isinstance(u.get("seen"), dict) else {}
        if seen:
            facts["last_upload"] = {
                "minutes": seen.get("minutes"),
                "modules": [
                    {"name": m.get("name"), "questions": m.get("questions"), "correct": m.get("correct")}
                    for m in (seen.get("modules") or []) if isinstance(m, dict)
                ],
            }
    return facts


def _user_numbers(text: str) -> set[int]:
    """他自己说过的数字。他说「60 分」，模型回「60 分」就不该被判成编造。"""
    return {int(n) for n in re.findall(r"\d+", text or "")}


def strip_commit(text: str) -> str:
    """把「再学 15 分钟」这类没有依据的承诺整句删掉。只在非判断模式下用。

    为什么是删、不是拦：实测拦住之后让它重说，它还是说同样的话，两次都过不去
    就掉兜底——一句闲聊变成「模型没接上，它凭记忆说」，比说错更难看。
    删掉那个子句，剩下的半句往往反而是好的：
    「那我再学 15 分钟，你刚传的图里还有 9 题对得挺稳」
    → 「你刚传的图里还有 9 题对得挺稳」。
    """
    if not text:
        return text
    parts = re.split(r"(?<=[。！？；，])", text)
    kept = [p for p in parts if not _COMMIT_MINUTES.search(p)]
    out = "".join(kept).strip().lstrip("，。；、 ")
    # 首字被削掉后可能留下小写残句，补个句号让它像话
    if out and out[-1] not in "。！？…~～":
        out += "。"
    return out


def check_reply(text: str, *, facts: dict, user_text: str = "",
                known_modules: list[str] | None = None) -> tuple[bool, str]:
    """上屏前的最后一道。返回 (能说?, 不能说的原因)。原因只进日志，不给用户看。"""
    if not text or not text.strip():
        return False, "空回答"

    banned = [p for p in _BANNED_PHRASES if p in text]
    if banned:
        return False, f"说了堵情绪的话 {banned}"

    # 编身体证据：这是最能骗到人、也最经不起追问的一种假
    for m in _SENSORY.finditer(text):
        word = m.group()
        if word.endswith("你") and text[m.end():m.end() + 1] in _SENSORY_OK_NEXT:
            continue                      # 「看到你发的图」是真的，放行
        return False, f"编了身体上的证据「{word}」——它只有一块屏幕，闻不到也摸不到"

    # 科目编造：库里没有的模块名一个字都不许说
    known = set(known_modules or [])
    if known:
        invented = [n for n in _MODULE_VOCAB if n in text and n not in known]
        if invented:
            return False, f"说了库里没有的科目 {invented}"

    # 他在问该不该学，回答里必须有一个结论。
    # 没有这道闸，「所以我今天就不用学习了吗」会被答成「我帮你剥了颗瓜子」——
    # 听着温柔，但一个字都没回答他的问题。这就是用户截图里的原话场景。
    if facts.get("mode") == "advice":
        v = facts.get("verdict") or {}
        if not any(w in text for w in _ADVICE_WORDS):
            return False, "他在问该不该学，你却只安慰，没给结论"
        # 说了「再 N 分钟」时，N 必须是算出来的那个。模型爱顺手改成「半小时」「20 分钟」
        if v.get("verdict") == "keep" and v.get("again_minutes"):
            if v["again_minutes"] not in {int(n) for n in re.findall(r"\d+", text)}:
                return False, f"建议的时长不是算出来的 {v['again_minutes']} 分钟"

    # 不在判断模式，就不许承诺「再学多久」。
    # 实测「我不累啊」这种闲聊，它自己接了一句「还能再学 15 分钟」——
    # 15 是图上题数被白名单放过的，数是真的，但那句话没有任何依据，是它顺口编的。
    # 时长承诺只能在 facts.verdict 里出现，别的地方一律不许。
    if facts.get("mode") != "advice":
        if _COMMIT_MINUTES.search(text):
            return False, "不在判断模式，却给了学习时长的承诺"

    # 他问「你怎么知道」，回答里必须有出处；说「我就是知道」等于没答
    if _asks_how_know(user_text):
        if not any(w in text for w in _PROVENANCE_WORDS):
            return False, "他问你怎么知道，你却没说清出处"

    # 引图必须引得出：数、科目、或者「上面写着」。
    # 「图里小灯还亮着呢」这种画面细节，图里没有，就是它自己想的。
    if any(w in text for w in _CITES_IMAGE):
        if facts.get("mode") == "comfort":
            return False, "他正难受，不该翻截图当证据"
        up = facts.get("last_upload") or {}
        if not up:
            return False, "他没给过你图，你却提了图"
        up_nums = {int(up["minutes"])} if up.get("minutes") is not None else set()
        up_names = set()
        for m in (up.get("modules") or []):
            if m.get("name"):
                up_names.add(m["name"])
            for k in ("questions", "correct"):
                if m.get(k) is not None:
                    up_nums.add(int(m[k]))
        said_nums = {int(n) for n in re.findall(r"\d+", text)}
        if not (said_nums & up_nums or any(n in text for n in up_names)
                or any(m in text for m in _CITE_MARKERS)):
            return False, "提到了图，但说的内容图里没有"

    # 把旁白当成他的原话：只有真的存在「他说的」记忆时，才允许说「你说过」
    if re.search(r"你说过|你上次说|你跟我?说", text):
        said_by_him = [m for m in (facts.get("memories") or []) if m.get("who") == "他"]
        if not said_by_him:
            return False, "把系统旁白当成了他的原话"

    # 他难过的时候报数字，是这只仓鼠最不该做的事——实测模型一定会犯，所以硬拦
    if looks_sad(user_text) and re.search(r"\d", text):
        return False, "他正难受，这时候不该报任何数字"

    cn = _CN_AMOUNT.findall(text) or _CN_COUNT.findall(text)
    if cn:
        return False, f"把库里的数字改成了中文写法 {cn}，查不了真伪"

    made_up = [p for p in _BANNED_COMPARE if p in text]
    if made_up:
        return False, f"编了库里没有的比较基线 {made_up}"

    role = [p for p in _BANNED_ROLE if p in text]
    if role:
        return False, f"把记忆安到了他头上 {role}"

    if _THIRD_PERSON.search(text):
        return False, "用了第三人称，角色崩了"

    allowed = set(brain.allowed_numbers(facts)) | _user_numbers(user_text)
    # 出处摘要里也带数（「判断推理 15 题对 9 题」），那些同样是他给过我的
    for src in (facts.get("sources") or []):
        allowed |= {int(n) for n in re.findall(r"\d+", str(src.get("what") or ""))}
    stray = [int(n) for n in re.findall(r"\d+", text) if int(n) not in allowed]
    if stray:
        return False, f"出现事实里没有的数字 {stray}"

    # 提到模块名时，数字必须是这个模块的（防「数字是真的但安错了人」）
    ok, reason = brain.check(text, facts)
    if not ok and "数字" not in reason:
        return False, reason
    return True, ""


def build_messages(user_text: str, *, facts: dict, history: list[dict] | None = None) -> list[dict]:
    """拼请求。system 必须第一条——这是 OpenAI 协议的硬要求，也是人设的地基。

    历史只带最近 4 条（两轮）。带得越多它越爱模仿自己上一句的腔调——
    实测 6 条时它连着三轮说出同一个句式，像卡住的唱片。
    """
    msgs: list[dict] = [{"role": "system", "content": PERSONA}]
    for turn in (history or [])[-4:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content[:200]})
    facts_json = __import__("json").dumps(facts, ensure_ascii=False, separators=(",", ":"))
    hint = ""
    if facts.get("mode") == "advice":
        # 实测不提这一句，它会挑最安全的那句：「你辛苦了，早点休息吧」——
        # 听着贴心，但他问的是「还用学吗」，这句话等于没回答。
        hint = ("\n他在问你今晚该不该继续学。facts.verdict 是已经算好的结论，照它说，不许改："
                "第一句就直接给结论（「今天够了」「再来 20 分钟」「别刷了」），不要先寒暄，"
                "尤其不要说「你刚说……」；第二句说为什么，要带一个真数——今天多少分钟，"
                "或本周还差几天，只带一个；最后一个动作。40 字以内。"
                "说停就说得干脆，不要留「不过你要想学也行」这种尾巴——那是把选择权又推回给他。"
                "只说一个动作，不要给三条建议。")
    elif facts.get("mode") == "provenance":
        hint = ("\n他现在在问你怎么知道的。照着 facts.sources 里的 from 说出处，"
                "如果其中有「你刚传给我的那张图」，就先用它——他刚做完这件事，"
                "你说得出图上的东西，比说「记录里有」可信得多。"
                "哪件事就指哪一条，别拿「你自己说过」去答「你怎么知道我学了多久」。"
                "一句话说完，别解释，别顺带夸他。")
    elif facts.get("mode") == "comfort":
        # 实测不提这一句，它会退成「你累啦，我听见了。」——安全，但像客服。
        # 难受的时候要的是「这件事确实难」+ 一个具体的小动作，不是复述他的情绪。
        hint = ("\n他现在难受。先认下这件事确实难，再给一个小动作（推瓜子、趴他手边、"
                "拱他一下），20 到 40 个字。不要说「我听见了」这种空话，不要给办法，"
                "也不要用「你刚说……」开头——那是在把他的话念回来。")
    msgs.append({
        "role": "user",
        "content": f"事实（JSON，只能用这里面的数字，sources 是你唯一能指的出处）：{facts_json}"
                   f"{hint}\n\n他说：{user_text}",
    })
    return msgs


def retry_messages(messages: list[dict], rejected: str, reason: str) -> list[dict]:
    """被拦下之后，把「哪句不行、为什么」喂回去让它自己改一次。

    比在 system 里再堆一条抽象规则有效得多——模型对「这句具体错在哪」的响应，
    远好于对「你要注意分寸」这种话的响应。只重试一次：第二次还错就是它不会，
    再多试只是烧钱和拖时间。

    ``reason`` 要落到具体禁止项上。实测只说「说错了，重说」它还会犯同一类错，
    因为它不知道该改哪个点；说「这一句里不许出现分钟数」，它一次就改对了。
    """
    specific = ""
    if "时长" in (reason or ""):
        specific = "这一句里不许出现任何分钟数，也不许说再学多久——他没问你这个。"
    elif "数字" in (reason or ""):
        specific = "这一句里不许出现任何数字。"
    elif "出处" in (reason or ""):
        specific = "要直接说出处：是那张图、还是他自己说的。"
    elif "没给结论" in (reason or ""):
        specific = "要先给结论：继续、还是停。不许只安慰。"
    return list(messages) + [
        {"role": "assistant", "content": rejected},
        {"role": "user", "content": f"你刚才那句话说错了：{reason}。{specific}"
                                    f"重说一句，20 字以内，只用「你」，不许编你没看到、没听到的事。"},
    ]


def looks_sad(text: str) -> bool:
    """他是不是在示弱。

    先剥掉「我不累」「没崩」这类否认：那是反驳，不是示弱。
    之前没剥，于是「我不累啊」被判成难受，进了安慰模式、一个数字都不给；
    他紧接着问「那我今天还用学吗」，它手上什么都没有，只能推瓜子。
    """
    t = _DENIAL.sub("", text or "")
    return any(w in t for w in _SOFT_WORDS)


# 他一边说难受一边问成绩，这时候还是要给数（他真的想知道），不能一律进安慰模式
_ASK_DATA = ("怎么样", "多少", "几道", "几题", "正确率", "成绩", "进度", "错了几", "对了几", "统计", "排名")


def _asks_for_data(text: str) -> bool:
    return any(w in (text or "") for w in _ASK_DATA)


# 他在要一个主意，不是在求安慰。这两种请求的答法正好相反：
# 求安慰要的是「我在」，要主意要的是「该 / 不该」。
_ADVICE_ASK = (
    "该不该", "要不要", "用不用", "还用不用", "还需不需要", "还用学", "还要学", "还要不要",
    "继续学", "继续吗", "还要继续", "该学", "学不学", "该歇", "该睡", "该停", "该收",
    "能歇", "能不能歇", "能不能停", "能不能休息", "可以歇", "可以停", "可以休息",
    "收工", "到此为止", "够了没", "够了吗", "够不够", "今天就", "不用学", "别学了",
    "是不是该", "有必要吗", "会不会", "来得及", "太赶", "赶得上",
)

# 有了结论才叫回答。这些话里一个都没有，就是在拿安慰当答案
_ADVICE_WORDS = ("该", "别", "不用", "可以", "再", "先", "停", "睡", "歇", "换", "做",
                 "补", "够", "继续", "收工", "明天", "算了")

# 固定句式抓不全。实测「那我今天还要再学一会儿吗」就漏了——
# 它长得不像「该不该」，但它就是在要一个主意，于是模型自己编了个「15分钟」。
# 所以再补一条句式规则：问的是学习动作 + 句尾有疑问语气 + 说的是他自己的事。
_ADVICE_VERBS = ("学", "刷", "做", "练", "背", "继续", "歇", "停", "睡", "休息", "收工", "补")
# 句尾语气。刻意不含「么」——「我今天做了什么」是问账本，不是要主意，
# 那一问要走数据模式，把今天的数报给他。
_ASK_TAIL = re.compile(r"(?:吗|呢|吧|不|没有)\s*[？?]?\s*$")
_SELF_WORDS = ("我", "今天", "今晚", "现在", "接着")

# 「再学 15 分钟」这类**具体**承诺。只有判断模式里、且数算好了才许说。
# 刻意不收「再学一会儿」——那不是承诺，是随口一句，拦它只会让闲聊掉兜底。
_COMMIT_MINUTES = re.compile(r"(?:再|接着|继续)[^，。！？]{0,6}?(?:\d+|半小时|一小时)")


def _asks_advice(text: str) -> bool:
    """他在问「今晚还用不用学」这类要拿主意的话。

    「你睡了吗」不算——那是在问宠物，不是问自己。所以句式分支额外要求
    带上「我 / 今天 / 再」这类指自己的词。
    """
    t = (text or "").strip()
    if not t:
        return False
    if any(w in t for w in _ADVICE_ASK):
        return True
    return (bool(_ASK_TAIL.search(t))
            and any(v in t for v in _ADVICE_VERBS)
            and any(s in t for s in _SELF_WORDS))


def _asks_how_know(text: str) -> bool:
    """他在问「你凭什么知道」。这时候要的是出处，不是安慰，也不是数字。"""
    return any(w in (text or "") for w in _PROVENANCE_ASK)


_FALLBACK_SAD = [
    "唔……那就先歇一会儿。我趴这儿陪你，不说话也行。",
    "我把瓜子推你手边了，吃点再说。考不考得上，不是今天定的。",
    "累了就是累了，不用找个理由。我在这儿，又不会跑。",
]
_FALLBACK_ASK_MEMORY = [
    "你说的我记着呢，就是想不起来你原话是怎么说的了。",
    "那件事我记着，等我缓一缓，慢慢跟你说。",
]
_FALLBACK_NORMAL = [
    "我在呢，你说，我听着。",
    "唔，我听着呢，你慢慢说。",
    "瓜子刚剥好，你接着讲。",
]
# 被问「你怎么知道」时的兜底：宁可不提数字，也不能瞎猜一个来源
_FALLBACK_HOW = [
    "我知道的都是你告诉我的、还有你传给我看的那点东西。",
    "我没看见别的，就知道你跟我说的那些。",
]


def fallback(user_text: str, facts: dict | None = None) -> str:
    """模型不在（没网、超时、说了不该说的）时，它还是会说一句人话，只是笨一点。

    这些句子一个数字都不带 —— 笨可以，假不行。

    唯一例外是「该不该学」：那种时候「我在呢」等于没答，所以要照算好的结论说。
    哪怕模型挂了，他问「今天还用学吗」也得有个明确答复。
    """
    verdict = ((facts or {}).get("verdict") or {}).get("verdict")
    if verdict:
        return coach.fallback(verdict=verdict,
                              again_minutes=((facts or {}).get("verdict") or {}).get("again_minutes"),
                              seed=user_text)
    if _asks_how_know(user_text):
        pool = _FALLBACK_HOW
    elif any(w in (user_text or "") for w in _MEMORY_WORDS):
        pool = _FALLBACK_ASK_MEMORY
    elif looks_sad(user_text):
        pool = _FALLBACK_SAD
    else:
        pool = _FALLBACK_NORMAL
    # 不随机：同一句话按输入长度轮换，测试可复现
    return pool[len(user_text or "") % len(pool)]
