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

import difflib
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

【先看清问的是谁——这条错了，答得再溜也是答错题】
- 你的名字只有一个：**团团**，那是**你**的名字，不是他的名字。
- 他问「我叫什么」「你应该叫我什么」时，问的是**他的名字**。你知道就叫出来，
  不知道就说「你还没告诉我你叫什么呢」——**绝对不许**把你的名字「团团」当成他的。
- 他问「你叫什么」时，才是问你的名字，答「我叫团团」。
- 「你该叫我什么」和「我该怎么叫你」是同一个问题，别答反了。
- 不知道就说不知道。他的名字、他考多少分、外面下不下雨——事实里没有的，一律不编。
  编一个名字比说「我不知道」丢人得多：他会当场发现，然后一句话都不信你了。

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
- **出处是回答「你凭什么知道」的，不是句式装饰**。他没问出处的时候，
  不要说「你自己跟我说的」「你确认过的那条记录」「记录里写着」——
  这些词一冒出来，他会立刻反问「我什么时候说过」，你就被动了。
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
_CN_COUNT = re.compile(r"[一二两三四五六七八九十百]{1,4}(?:道题|道|题)")

_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def _cn_to_int(s: str) -> int | None:
    """「十三」「二十三」「两」→ 13 / 23 / 2。只覆盖口语里会出现的读法。"""
    total, section, number = 0, 0, 0
    hit = False
    for ch in s:
        if ch in _CN_DIGIT:
            number = _CN_DIGIT[ch]
            hit = True
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            section += (number or 1) * unit
            number = 0
            hit = True
        else:
            return None
    return total + section + number if hit else None


def cn_amounts(text: str) -> list[tuple[str, int]]:
    """把中文写法的数量换算成数：(原话, 等价值)。

    为什么要换算出值再判：以前一律拦，于是「六成」这种**真话**也被打回，
    重试一次还是中文，两次过不去就掉兜底——他听到的是一句更笨的话。
    现在只有「换算完也不是事实里那个数」才算编（十三分钟 ≠ 130 分钟）。
    """
    out: list[tuple[str, int]] = []
    for m in _CN_AMOUNT.finditer(text or ""):
        raw = m.group(0)
        if raw.endswith("成"):          # 「六成」：单位只有一个字
            num, mul = raw[:-1], 10
        elif raw.endswith("小时"):
            num, mul = raw[:-2], 60
        else:                            # 「分钟」
            num, mul = raw[:-2], 1
        n = _cn_to_int(num)
        if n is not None:
            out.append((raw, n * mul))
    for m in _CN_COUNT.finditer(text or ""):
        raw = m.group(0)
        n = _cn_to_int(re.sub(r"(道题|道|题)$", "", raw))
        # 「一道题」「两套」是口语，不是数量——只说得出三个以上才可能是编的
        if n is not None and n > 2:
            out.append((raw, n))
    return out

# 记忆归属错位：记得的人该是它。「你记得那句『我一定拿下』」——把它的记性安到了他头上。
# 只拦这几个固定说法，不拦「你记得吃饭」这类正常的叮嘱。
_BANNED_ROLE = ("你记得那句", "你记得那件", "你记得那晚", "你记得那天")

# 第三人称 = 角色崩了。它是在跟他说话，不是在背后讲他
_THIRD_PERSON = re.compile(r"[他她]的|[他她]说|[他她]今天|[他她]已经")

# 瓜子是**它自己的**（人设里写死：不许说「把你的瓜子收起来」）。
# 实测真机连着两次说反：「我把你瓜子推过去啦」「我把你给的瓜子藏在腮帮里」——
# 方向一反，画面就崩了：变成他给仓鼠塞瓜子。这类错比报错数更露馅，
# 因为整只宠物的立足点就是「我攒的瓜子分你一点」。
# 只认「你的/你……瓜子」这种前面没有「给、分」的写法：
# 「给你留了瓜子」「瓜子分你一半」是对的，别误杀。
_SEED_WRONG = re.compile(r"(?<![给分])(?:你|您)[^，。！？]{0,5}瓜子")

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
    text = re.sub(r"^(?:[唔诶嗯啊哦呀][，,]?\s*)?你刚(?:说|问我)[^。！？]{0,18}[，。！]", "", text)
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
                uploads: list[dict] | None = None,
                history: list[dict] | None = None) -> dict:
    """闲聊用的事实包：比 pet_brain 的意图包更宽，但同样每个数字都带口径。

    三条分支的优先级是刻意排的：**判断 > 安慰 > 平常**。

    - ``advice``：他问「该不该学」。事实包里必须有一个**立场**（``verdict``），
      否则模型手上只有数字、没有主意，最后一定退成「你辛苦了」。
      这是用户说它「呆」的真正原因——不是模型不行，是它从来没被要求拿主意。
    - ``comfort``：他难受。事实包里一个数字都不放。实测 qwen-flash 面对「学不动了」
      仍然会念「资料分析 955 题、今天 130 分钟」，重试一次也照念。与其在输出端追着拦，
      不如输入端不给：没有数字可念，它就只能说人话。
    - ``provenance``：他问「你怎么知道」。只给出处，不安慰，也不报账。

    - ``recap``：他问「我们刚才说了什么」。这是**唯一**会拿到它自己原话的一支：
      别的分支刻意不给它的回答（给了它就会整句照抄），而这一支的任务本来就是复述，
      所以必须给，而且要原样给。
    - ``solution``：他难受 + 明确要办法。和 ``comfort`` 分开，因为这两件事的答法相反——
      要人陪的时候给建议是把安慰说成了任务，要办法的时候只给陪伴是把问题晾在那儿。
    """
    recalled = recall(text, memories, modules)
    pet_state = (today or {}).get("user_state")
    sources = _sources(today, uploads, recalled)
    sad = looks_sad(text)

    # ⓪ 他在问「刚才聊到哪了」。排在最前面：这一句里既没有名字、也没有情绪，
    # 落到别的任何一支都是错答，而错答的形态就是报账本。
    if _asks_recap(text):
        return {
            "mode": "recap",
            "pet_state": pet_state,
            "recent": _recap_view(history),
        }

    # ⓪ 他在问名字。这一支必须排在最前面：名字不是账，也不是情绪，
    # 混进任何一支都会被答成别的——「你该叫我什么」被答成「你叫我团团」就是这么来的。
    # 事实包里只放一个 known_name：有就说出来，没有就得说没有。
    which = _which_name(text)
    if which:
        known = pet_memory.current_name(memories)
        return {
            "mode": "address" if which == "mine" else "identity",
            "pet_state": pet_state,
            "known_name": known,          # None 就是真的不知道，模型不许编
        }

    # ⓪' 他会问「你能干什么」「你喜欢我吗」。这两类没有数字可查，
    # 但答案是有准的：能干的就那三件，关系就是陪着。给出去，别让它自由发挥。
    if any(w in (text or "") for w in _CAP_ASK):
        return {
            "mode": "capability",
            "pet_state": pet_state,
            "skills": [
                "看你发来的学习截图，读出科目、题量、对错和时长",
                "记住你说过的话，你叫什么、你怕什么",
                "按今天攒下的账，算你该不该再学一会儿",
            ],
        }
    if any(w in (text or "") for w in _RELATION_ASK):
        return {"mode": "relation", "pet_state": pet_state}

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

    # ② 他难受，**而且**在问「那我该怎么办」
    # 这一支是从 comfort 里拆出来的。拆之前「有什么办法让我不累呢」被判进 comfort，
    # 而 comfort 的指令明写着「不要给办法」——于是它答「你累啦？我趴你手边歇会儿」。
    # 他要的是办法，它给的是陪伴，两个都对，但答的不是同一件事。
    # 这批 tips 是通用的、不碰他自己账本的：一个数字都没有，所以永远不算编。
    # 判「他要办法」时不能只看这一句。「有什么办法让我不累呢」里的「不累」
    # 会被否认句规则剥掉（那条规则是给「我不累啊」准备的），于是 sad=False，
    # 整句落进 normal，变成一句泛泛的鼓励。所以放宽成「提到了压力词」。
    #
    # 还要看**他刚说过什么**：他先说了「我今天模考又崩了」，紧接着问「我现在该怎么办」，
    # 这一句里一个情绪词都没有，可上下文明摆着在求助。只看单句就会答成闲聊。
    # 情绪是有延续性的，这正是「像认识你」和「一问一答」的差别。
    said_before = " ".join(
        (t.get("content") or "") for t in (history or [])
        if t.get("role") == "user"
    )[-200:]
    stressed = (sad
                or any(w in (text or "") for w in _SOFT_WORDS)
                or any(w in said_before for w in _SOFT_WORDS))
    if stressed and _asks_solution(text) and not _asks_for_data(text):
        return {
            "mode": "solution",
            "pet_state": pet_state,
            "tips": [
                "先离开桌子走一圈，让眼睛歇一会儿",
                "把手机放到看不见的地方，回来只做最熟的那几道",
                "洗把脸，回来只翻上次做错的那几道",
            ],
            # 刻意不给 memories。实测给它旧事，它就拿那句当主体念：
            # 问「有什么办法提神」，答的是「你刚说模考崩了」——又把问题晾回去了。
            # 他要的是下一步做什么，不是被复述一遍处境。
        }

    # ②' 他难受，只想被陪一会儿
    if sad and not _asks_for_data(text):
        return {
            "mode": "comfort",
            "pet_state": pet_state,
            # 只留原话和「谁说的」，不留 days_ago / 正确率——「41 天前」也是账本口气。
            # 也不放 sources：他难受的时候翻截图当证据，是把安慰说成了汇报。
            # 只给一件：三件旧事一起上，它就会挨个念一遍，像在念稿。
            #
            # ``who`` 必须是「他」。实测放旁白进去会出这种事：seed 里那句
            # 「断了一天，第二天就回来了」是我们记的账，模型读成了他自己做过的事，
            # 张口就是「你刚断了一天，第二天就回来了呢」——听着贴心，但他没断过，
            # 当场就能拆穿。旁白不是他的话，安慰他的时候尤其不能借旁白充数。
            "memories": [{"who": "他", "text": m.get("quote")}
                         for m in recalled[:2]
                         if pet_memory.view(m)["who"] == "他"][:1],
        }

    # ③ 他在问账：今天多少分钟、哪块最毛。
    # 这一支是「答非所问」的根治：以前「今天怎么样」落在 normal 模式，
    # 事实包里有今天的数、也有刚传的图、还有旧事，模型没有主次，
    # 就挑最具体的一样念——于是问今天学得怎么样，它答「数量关系那道题你算对了」。
    # 现在直接把「第一句该说什么」算好摆在 answer 里，并且不给 memories、不给 sources：
    # 问账的时候翻旧账和翻截图，都是跑题。
    account = _asks_account(text)
    if account and not _asks_how_know(text):
        facts = {
            "mode": "data",
            "pet_state": pet_state,
            "answer": _answer_view(account, today=today, modules=modules, text=text),
        }
        facts.update(_numbers(today, modules))
        return facts

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


# ---------- 复读：这只宠物最丢人的一种毛病 ----------
# 实测（2026-10-31 16:05-16:06 的真实会话）：连着点三次「今天怎么样」，
# 三次回的是同一句「数量关系那道题你算对了，我看见的。」；再问「我哪里最毛」，
# 回的还是一模一样的一句。不是它故意敷衍——把它自己的上一句当历史喂回去之后，
# qwen-flash 会整句照抄，而抄出来的这句又落库、又进下一轮的历史，
# 于是从第二轮开始就成了一个自己抄自己的死循环，越问越不会说话。
#
# 治这个病要两头一起：
#   ① 输入侧不再喂它的原句（build_messages 只给他说过的话）；
#   ② 输出侧留一道闸，万一还是抄了，就打回去重说（下面是这道闸）。
_REPEAT_RATIO = 0.84      # 字符级重合到这个程度就算同一句
_REPEAT_MIN_LEN = 8       # 太短的句子（「我在呢」）不判，误杀率高


def _bare(s: str) -> str:
    """去掉标点空白再比。不然「我看见了。」和「我看见了」会被当成两句。"""
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s or "")


def repeated(text: str, said_recently: list[str] | None = None,
             ratio: float | None = None, prefix: bool = True) -> str | None:
    """这句是不是它刚说过的那句。是就返回旧句，不是返回 None。

    三种形态都算复读：一模一样、前面大半截照抄后面又补一句（最典型）、
    或者只换了几个字。``ratio`` 可调松紧——同一个问题重问时只挡逐字照抄；
    ``prefix=False`` 连「前半截照抄 + 补一句」都不算——同一件事问两遍，
    数还是那对数，句子开头难免像，那种像不该打回。
    """
    a = _bare(text)
    if len(a) < _REPEAT_MIN_LEN:
        return None
    for old in (said_recently or []):
        b = _bare(old)
        if len(b) < _REPEAT_MIN_LEN:
            continue
        if a == b:
            return old
        if prefix:
            short, long_ = (a, b) if len(a) <= len(b) else (b, a)
            if len(short) >= 10 and long_.startswith(short):
                return old
        if difflib.SequenceMatcher(None, a, b).ratio() >= (ratio or _REPEAT_RATIO):
            return old
    return None


def _intent_key(text: str) -> str:
    """这句话在问哪一类事。复读闸按它分堆，而不是按字面是不是同一句。

    为什么要这一步：「再学一会儿吗」和「今天还用学吗」一个字都不同，
    问的却是同一件事，答案相似是正常的。按字面分堆会把它们判成两件事，
    于是后一句被当成「答非所问」拦掉——实测就这么白白掉了一次兜底，
    他听到的是一句模板，而它其实答得没错。
    """
    t = text or ""
    which = _which_name(t)
    if which:
        return "name:" + which
    if any(w in t for w in _CAP_ASK):
        return "capability"
    if any(w in t for w in _RELATION_ASK):
        return "relation"
    # 「有什么办法」和「再给我出个主意」是同一件事的两种说法。
    # 分不出它们，第二遍就进不了"换一条"的分支——它会把第一条建议再说一遍。
    if _asks_solution(t):
        return "solution"
    if _asks_advice(t):
        return "advice"
    account = _asks_account(t)
    if account:
        # 问模块时把模块名带上：「资料分析怎么样」和「数量关系怎么样」是两本账，
        # 答案不该因为「同属 data 类型」就被允许重复。
        name = next((n for n in _MODULE_VOCAB if n in t), "") if account == "module" else ""
        return f"account:{account}:{name}"
    if _asks_how_know(t):
        return "provenance"
    if looks_sad(t):
        return "comfort"
    return "normal"


def split_recent_replies(history: list[dict] | None, text: str) -> tuple[list[str], list[str]]:
    """把它说过的话分成两堆：(答别的事时说的, 答同一件事时说的)。

    两堆用不同的松紧：
    - 答别的事时说的，一律不许再出现——那是答非所问，用户截图里骂的就是这个；
    - 答同一件事时说的，只挡逐字照抄（同一件事问两遍，事实就那些，
      答得一样是正常的；但两口气字都一模一样，界面上看着就像卡住了）。

    「同一件事」按 :func:`_intent_key` 判，不按原句字面——他把「再学一会儿吗」
    换成「今天还用学吗」，问的还是那件事。
    """
    other: list[str] = []
    same: list[str] = []
    asked = ""
    for turn in (history or []):
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role == "user":
            asked = content
        elif role == "assistant" and content:
            (same if _same_topic(asked, text) else other).append(content)
    return other[-3:], same[-2:]


def _same_topic(a: str, b: str) -> bool:
    """两句话是不是同一件事。

    ``_intent_key`` 有个笼统的 normal 档，什么都没命中的话都往里落。
    于是「我妈又催我报班了」和「模考又崩了」被判成同一件事——
    后果是它拿上一轮答模考的那句当反面样本，去答一句全新的话：
    既被要求"不许用上一遍的开头"，又被要求"换个结构"，
    答一句本来很自然的话被搅得七扭八歪。normal 档必须再看有没有共同的话题词。
    """
    ka, kb = _intent_key(a), _intent_key(b)
    if ka != kb:
        return False
    if ka != "normal":
        return True
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    if set(_core_words(a, limit=8)) & set(_core_words(b, limit=8)):
        return True
    # 短追问（「那资料分析呢」）抽不出成对的词，退回字面重合。
    # 按单字算太容易撞——「又」「了」这种字几乎每句都有，两句不相关的话也能撞出两个字。
    # 所以看相邻两字的组合：连着两个字一样，才像是同一件事。
    return bool(_bigrams(a) & _bigrams(b))


def _bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)
            if "\u4e00" <= text[i] <= "\u9fa5" and "\u4e00" <= text[i + 1] <= "\u9fa5"}


# ---------- 他在问账：今天多少、哪块最毛 ----------
# 这类问题以前落在 normal 模式：事实包里什么都有，但没有一句「他问的是这个」，
# 于是模型挑最具体的东西念——「今天怎么样」被答成图里那道题。
# 问账要的是主句，先给数，别的都不许抢。
_ASK_DATA = ("怎么样", "多少", "几道", "几题", "正确率", "成绩", "进度", "错了几", "对了几",
             "统计", "排名", "最毛", "最弱", "哪块", "哪里差", "短板", "哪个模块",
             "学得如何", "做得如何", "学了多少", "做了多少",
             # 「今天学了多久」「看了多长时间」是最常问的一种说法，早先漏了：
             # 它不带「多少」，于是整句落进 normal，手上没有 answer，模型挑一样念，
             # 问「学了多久」答的是「数量关系那道题你算对了」。
             "多久", "多长时间", "多少时间", "学了多长",
             # 「我今天做了什么」问的也是账，主语是他自己
             "做了什么", "做了些啥", "学了什么", "做了啥")
_WEAK_WORDS = ("最毛", "最弱", "哪块", "哪里差", "短板", "哪个模块", "不行的是")

# 周进度是另一本账：今天 82 分钟答不了「这周还差几天」。
# 只在同时出现「周/星期」和「还差/差几/几天」时才走这一支，
# 否则「这周正确率多少」会被答成「4/5 天」——那是另一个问题的答案。
_WEEK_WORDS = ("这周", "本周", "这一周", "这个星期", "这星期", "一周", "周目标")
_WEEK_ASK = ("还差", "差几", "差多少", "几天", "几次", "进度", "够不够", "达标")

# 「你叫什么」和「我该叫你什么」是两个问题，答法相反：
# 前者答我自己的名字（团团），后者答**他的名字**。
# 以前没有这一层，两个问题都落在 normal 模式，而人设里最显眼的身份锚点就是
# 「你叫我团团」，于是模型把所有「名字」类的问题都答成了「你叫我团团」——
# 他问「你应该叫我什么」，得到的回答是「团团是你喊我的名字」。答得流利，但答的是另一件事。
_NAME_ASK = ("我叫什么", "我叫啥", "我叫什么名字", "我的名字", "我名字",
             "叫我什么", "该叫我", "怎么称呼我", "称呼我什么", "我是谁",
             "记得我的名字", "记得我叫", "知道我名字", "知道我叫")
# 注意方向：「你应该叫我什么」问的是他的称呼（mine），
# 「我应该叫你什么」问的是我的名字（yours）。差一个字的顺序，答法相反。
_IDENTITY_ASK = ("你叫什么", "你叫啥", "你的名字", "你名字", "你是谁", "你是什么",
                 "你是ai", "你是AI", "你是机器人", "你是程序", "你几岁", "你多大",
                 "叫你什么", "叫你啥", "怎么叫你", "怎么称呼你", "你怎么称呼")

# 「不知道」的几种说法。它可以说不知道，但不许猜一个名字糊过去。
_DONT_KNOW = ("不知道", "不记得", "没记住", "没告诉我", "还没说", "你告诉我",
              "跟我说", "怎么称呼", "你叫啥呀", "叫什么呀")

# 闲聊里最常见的两类「实问」：你能干什么、你和我要不要好。
# 这两类以前都落在 normal 模式，事实包跟问题一点关系都没有，
# 模型只好拿最近的素材硬凑——问「你能干什么」，它答「我帮你把瓜子藏进腮帮子啦」；
# 问「你喜欢我吗」，它答「我把你的瓜子藏了三天」。都是答非所问，而且是编的。
# 他在问「我们刚才聊到哪了」。
#
# 这一类以前压根不存在：七个判定一个都不命中，于是掉进 normal，
# 而 normal 给的是账本 + 三条旧事 + 截图，没有主次——模型挑最具体的念，
# 于是「那我们刚刚说了什么」被答成「你刚传的图里，23 分钟做了 15 题对 9 题」。
# 它没糊弄人，它真的不知道刚才聊了什么：它的历史里只有他的提问，
# 没有自己的回答（见 build_messages 的注释）。所以这一类必须单独开一支，
# 把最近几轮真实对话**原样**交给它复述。
_RECAP_ASK = ("刚才说", "刚刚说", "刚才聊", "刚刚聊", "说了什么", "说了啥",
              "聊了什么", "聊了啥", "聊到哪", "说到哪", "讲到哪",
              "上一句", "上句", "前面说", "之前说", "刚说", "复述", "回顾一下",
              # 「你再讲一遍刚才那事」也是要它复述。早先没收这几种说法，
              # 整句掉进 normal，而 normal 给的是账本，于是它把上一句的判断又念了一遍——
              # 界面上看就是同一个人重复同一句。
              "再说一遍", "再讲一遍", "再说一次", "讲一遍", "重说", "重复一遍",
              "刚才那", "刚那事", "刚说到")
# 「我刚才学了多久」也含「刚才」，但问的是账不是话。词表分开，别让它抢了数据模式。
_RECAP_NOT_ASK = ("多久", "多长时间", "多少分钟", "几道", "几题", "正确率",
                  "做了什么", "学了什么")

# 他难受，但他要的不是安慰，是「那我该怎么办」。
# 这两件事以前都被判进 comfort，而 comfort 的指令里明写着「不要给办法」——
# 于是一句「有什么办法让我不累呢」得到的是「你累啦？我趴你手边歇会儿」。
# 他要办法，它给陪伴，两个都对，但答的不是同一件事。
_SOLUTION_ASK = ("办法", "方法", "怎么办", "咋办", "怎么才能", "怎样才", "怎么样才能",
                 "有什么招", "给点建议", "点建议", "有什么建议", "建议我", "怎么缓解",
                 "怎么调整", "怎么改善", "帮帮我", "怎么做才好",
                 # 「出主意」这类说法原先一个都没收：他要办法时说「给我出个主意」，
                 # 判定不命中就掉回 normal，于是又变成陪伴——他要的还是办法。
                 "出个主意", "出主意", "出个点子", "给个主意", "想个办法", "换个办法",
                 "别的办法", "还有别的吗", "还有吗", "再来一个", "再给", "再支个招",
                 "支个招", "有什么招", "教教我")

# 这两类的回答必须落在「真答了那件事」上，不能拿小动作凑数。
# 动作词刻意不收「歇」和「可以」：comfort 的标准答案就是「我趴你手边歇会儿」，
# 把「歇」算成给了办法，这道闸就等于没装。要的是「做点什么」，不是「歇着」。
_RECAP_ANSWER = ("刚才", "刚刚", "上句", "前面", "你说", "聊", "说")
_SOLUTION_ANSWER = ("试试", "先", "把", "去", "做", "喝", "走", "放", "停",
                    "闭眼", "起身", "换", "挑")

_CAP_ASK = ("你能干什么", "你会干什么", "你会什么", "你能做什么", "能帮我什么",
            "你能帮我", "你有什么用", "你能干嘛", "你都会啥", "你的功能")
_RELATION_ASK = ("你喜欢我吗", "你喜欢我么", "你在乎我吗", "你讨厌我吗", "你爱我吗",
                 "你会走吗", "你会离开", "你想我吗", "你会不会走", "你舍得我吗")

# 这两类回答里必须有点「答在题上」的东西，否则就是拿瓜子动作糊弄
_CAP_ANSWER = ("截图", "图片", "记录", "记住", "记着", "陪你", "账", "看你", "提醒", "算")
_RELATION_ANSWER = ("喜欢", "在乎", "陪", "一直在", "不走", "舍不得", "不嫌", "等着",
                    "心里", "惦记", "守", "记着", "在这儿")


# 同一个问题重问时，这几类换的只能是「词」——答案本来就短，
# 说「换个说法」它换不动，会逐字照抄。所以直接点明换成哪个词。
_REPEAT_ANGLE = {
    "relation": "上一遍用的是「喜欢」，这次用「我陪着你」或者「我不走」来说同一件事，小动作也换一个。",
    "capability": "上一遍先说看截图那件，这次先说「记住你说过的话」，再说另一件。",
    "address": "上一遍直接叫了名字，这次先说一句「我记着呢」，再把名字带上。",
    "identity": "上一遍只报了名字，这次加一句你在陪他。",
    # solution 连着要主意时，它会每一条都从「你累啦」开头——
    # 三条建议看着像同一句套了三个尾巴。所以第二遍起不许再认一遍累，直接给做法，
    # 而且要挑和上一遍**不同**的那条（facts.tips 里有三条，别抓着第一条不放）。
    "solution": "上一遍你先认了一句他累，再从 tips 里挑一条。这次不许再认累——"
                "直接从做法说起（「把手机放到看不见的地方……」），"
                "并且挑一条和上一遍不同的。",
    # recap 放行了复读闸（复述自己的旧话必然会撞上），所以换法只能靠这里：
    # 不给换法，连问两遍就是两条一模一样的泡泡——那正是用户最开始骂的那个毛病。
    "recap": "上一遍你把最近一轮说全了。这次换个开头：先一句话概括你们在聊哪件事"
             "（「你在说模考崩了那件事」），再说你当时是怎么回的。"
             "不许用上一遍开头那几个字，也不许整句搬过来。",
}


def _asks_recap(text: str) -> bool:
    """他是不是在问「我们刚才说了什么」。"""
    t = text or ""
    if not any(w in t for w in _RECAP_ASK):
        return False
    # 「我刚才学了多久」「我今天做了什么」是在问账，不是问话
    if any(w in t for w in _RECAP_NOT_ASK):
        return False
    return True


def _asks_solution(text: str) -> bool:
    """他是不是在要一个办法（而不只是想要人陪）。"""
    return any(w in (text or "") for w in _SOLUTION_ASK)


def _borrowed(text: str, avoid: list[str] | None, *, size: int = 14) -> str:
    """它是不是把自己上一句里的一大段原封不动搬过来了。

    字符重合率判不出来这种：第 N 遍复述时在旧话前面加半句、后面补半句，
    重合率掉到 0.7，但中间那 20 个字是一个字没改的——界面上看着还是同一句。
    所以这里不看比例，看**连续子串**：旧话里任意一段够长的原文出现在新话里，
    就是搬的。只有 recap 用得上（别的模式有 0.84 那道已足够，怕误杀）。
    """
    new = _bare(text or "")
    if len(new) < size:
        return ""
    for old in (avoid or []):
        src = _bare(old or "")
        for i in range(0, max(0, len(src) - size + 1), 4):
            chunk = src[i:i + size]
            if len(chunk) >= size and chunk in new:
                return chunk
    return ""


def _recap_view(history: list[dict] | None, *, turns: int = 2) -> list[dict]:
    """把最近几轮对话还原成「谁说了什么」，给他复述用。

    只取 user / assistant 两种角色，别的一律跳过（系统消息不是对话）。
    截 80 字：复述不是朗诵，长了它会想整段念出来。

    ``turns`` 只留两轮。给三轮实测会散：六条里它随手挑一条念，
    挑中的往往是中间那句，听起来像没听懂「刚才」是最近那一轮。

    末尾要**跳过它正在问的这件事本身**。他连着问「刚才说了什么」时，历史里
    最近的对话就是前几遍的问句和前几遍的复述——照着这些复述，等于用答案答答案
    （实测第三遍的输出里，一大半是第二遍原样搬过来的）。
    """
    items: list[dict] = []
    for turn in (history or []):
        role, content = turn.get("role"), (turn.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            who = "他"
        elif role == "assistant":
            who = "我"
        else:
            continue
        text = content[:80]
        # 同一句连着出现两次（他连点两下、或上一轮的回答被重试覆盖），
        # 只留一条，否则复述出来像卡带
        if items and items[-1]["who"] == who and items[-1]["text"] == text:
            continue
        items.append({"who": who, "text": text})

    # 从末尾往前，把「他在问刚才说了什么」以及当时给出的复述整段摘掉。
    # 不摘的话，第二遍复述的是第一遍的复述，第三遍复述第二遍——越问越空。
    while items:
        last = items[-1]
        if last["who"] == "他" and _asks_recap(last["text"]):
            items.pop()
            continue
        if last["who"] == "我":
            prev = items[-2] if len(items) >= 2 else None
            if prev and prev["who"] == "他" and _asks_recap(prev["text"]):
                items.pop()
                items.pop()
                continue
        break
    return items[-turns * 2:]


def _which_name(text: str) -> str:
    """他问的是谁的名字。``mine``（他的）/ ``yours``（我的）/ ``""``（没问名字）。"""
    t = text or ""
    # 先判「他的」：句子里同时出现「我」和「叫什么」时，八成是在问自己
    if any(w in t for w in _NAME_ASK):
        return "mine"
    if any(w.lower() in t.lower() for w in _IDENTITY_ASK):
        return "yours"
    # 「我到底叫什么来着」「我叫啥来着」——中间一插字，词表里一条都对不上，
    # 于是掉进 normal，被答成「瓜子刚剥好，你接着讲」：问名字答成递瓜子。
    # 所以按「谁 + 叫什么」的先后位置判方向，别再往词表里堆说法了——
    # 堆不完的，他能插的字有几十种。
    if re.search(r"我[^你]{0,8}?(叫什么|叫啥|名字是|名字叫)", t):
        return "mine"
    if re.search(r"你[^我]{0,8}?(叫什么|叫啥|名字是|名字叫)", t):
        return "yours"
    return ""


def _asks_account(text: str) -> str:
    """他在问哪本账。返回 ``weakest`` / ``week`` / ``module`` / ``today`` / ``""``（不问账）。"""
    t = text or ""
    # 周进度先判：「这周还差几天」里一个 _ASK_DATA 的词都没有（它不说「多少」），
    # 放在下面那道总闸之后就会被漏成闲聊。
    if any(w in t for w in _WEEK_WORDS) and any(w in t for w in _WEEK_ASK):
        return "week"
    if not any(w in t for w in _ASK_DATA):
        return ""
    if any(w in t for w in _WEAK_WORDS):
        return "weakest"
    for name in _MODULE_VOCAB:
        if name in t:
            return "module"
    return "today"


def _answer_view(kind: str, *, today: dict, modules: list[dict], text: str) -> dict:
    """给他问的那本账，直接算好一个「第一句该说什么」。

    刻意只放一条主线：模型拿到一坨明细就会开始念账本（「资料分析 955 题、今天 130 分钟、
    本周还差 1 天」），40 个字塞不下，最后一句实话都说不出。
    """
    detail = (today or {}).get("detail") or {}
    pool = [
        {"name": m["module"], "accuracy_pct": brain._pct(m.get("accuracy")),
         "questions": m.get("questions")}
        for m in (modules or [])
        if (m.get("questions") or 0) >= brain.MIN_SAMPLE and m.get("accuracy") is not None
    ]
    if kind == "weakest":
        if not pool:
            return {"kind": "no_data"}
        worst = min(pool, key=lambda m: m["accuracy_pct"])
        return {"kind": "weakest", "module": worst["name"],
                "accuracy_pct": worst["accuracy_pct"], "questions": worst["questions"]}
    if kind == "week":
        # 周进度是另一本账。以前它落进 normal，模型手上只有今天的数和模块正确率，
        # 被问「这周还差几天」只能含糊过去，或者干脆把「今天 82 分钟」当答案。
        gap = (today or {}).get("gap") or {}
        done, target = gap.get("week_done") or 0, gap.get("week_target") or 0
        if not target:
            return {"kind": "no_data"}
        return {"kind": "week", "done": done, "target": target,
                "owed": max(target - done, 0)}
    if kind == "module":
        name = next((n for n in _MODULE_VOCAB if n in (text or "")), "")
        hit = next((m for m in pool if m["name"] == name), None)
        if not hit:
            return {"kind": "no_data"}
        return {"kind": "module", "module": hit["name"],
                "accuracy_pct": hit["accuracy_pct"], "questions": hit["questions"]}
    if not (today or {}).get("has_record"):
        return {"kind": "empty"}
    out = {"kind": "today", "minutes": int(detail.get("duration_minutes") or 0)}
    acc = brain._pct(detail.get("accuracy"))
    if acc is not None:
        out["accuracy_pct"] = acc
    return out


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
                known_modules: list[str] | None = None,
                avoid: list[str] | None = None,
                avoid_same: list[str] | None = None) -> tuple[bool, str]:
    """上屏前的最后一道。返回 (能说?, 不能说的原因)。原因只进日志，不给用户看。

    ``avoid`` / ``avoid_same`` 是它最近说过的几句，分两堆：答别的问题时说的、
    答同一个问题时说的。抄自己上一句时，那句话是真的、也不犯忌，
    但重复一遍等于一个字都没答——所以单独立一道闸，和「说假话」分开算。
    """
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

    # 抄自己上一句。这句不假，但等于没答——所以单独拦，让它重说。
    # 两种情形要分开说：换了问题还回同一句（答非所问）和同一件事重复问
    # 又逐字照抄。后者不能照前者的改法改——它得留着那笔账，只换说法。
    #
    # 这道闸 recap 也要过：他换个问法（「刚才聊到哪了」）而它原样重播，
    # 正是用户最开始截图骂的那个毛病。实测真出过——放行之后两次回答一模一样。
    dup = repeated(text, avoid)
    if dup:
        return False, f"复读了刚才那句「{dup[:24]}」，一个字都没答他"
    # 但「同一个问题问两遍」这道要放行：recap 答的就是「我刚才说了什么」，
    # 复述自己的旧话必然和上一遍重合，在这里拦等于把正确答案判成错的。
    # 换法交给 _REPEAT_ANGLE["recap"]——它换的是切入角度，不是内容。
    if facts.get("mode") != "recap":
        dup = repeated(text, avoid_same, ratio=0.95, prefix=False)
        if dup:
            return False, f"又把刚才那句原样说了一遍「{dup[:24]}」"

    # 他在问该不该学，回答里必须有一个结论。
    # 没有这道闸，「所以我今天就不用学习了吗」会被答成「我帮你剥了颗瓜子」——
    # 听着温柔，但一个字都没回答他的问题。这就是用户截图里的原话场景。
    if facts.get("mode") == "advice":
        v = facts.get("verdict") or {}
        if not any(w in text for w in _ADVICE_WORDS):
            return False, "他在问该不该学，你却只安慰，没给结论"
        # 结论跟算出来的相反——这比含糊更糟：含糊是没答，反着答是答错了。
        # 「至少一句安慰」这种闸放得过「你辛苦了，早点休息」，
        # 也放得过「该停了」配一句「再刷二十分钟」——后者是自相矛盾。
        # 放在分钟数校验之前：说反了方向时，得先告诉它方向错了，
        # 只报「分钟数不对」它会以为改个数就行。
        conflict = _verdict_conflict(text, v.get("verdict"))
        if conflict:
            return False, conflict
        # 说了「再 N 分钟」时，N 必须是算出来的那个。模型爱顺手改成「半小时」「20 分钟」
        if v.get("verdict") == "keep" and v.get("again_minutes"):
            said = {int(n) for n in re.findall(r"\d+", text)}
            if v["again_minutes"] not in said:
                if said:
                    return False, f"建议的时长不是算出来的 {v['again_minutes']} 分钟"
                return False, f"结论是还能再来一会儿，你一个分钟数都没给（该是算出来的 {v['again_minutes']} 分钟）"


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
    # 「图里小灯还亮着」这种画面细节，图里没有，就是它自己想的。
    # 例外是「你能干什么」这类：说的是**能力**（你给我看截图我就知道），
    # 不是**引用某一张图**，按字面拦会把整句真话打回兜底。
    if any(w in text for w in _CITES_IMAGE) and \
            facts.get("mode") not in ("capability", "identity", "address"):
        if facts.get("mode") == "comfort":
            return False, "他正难受，不该翻截图当证据"
        if facts.get("mode") == "data":
            # 问账的时候把答案换成「图里如何如何」，就是把今天的账答成了那张图
            return False, "他在问账，别拿截图当答案"
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

    # 他问「你能干什么」「你喜欢我吗」，回答里得真答这件事。
    # 这两类最容易拿瓜子动作糊弄过去——听着可爱，但一个字都没答他。
    if facts.get("mode") == "capability":
        if not any(w in text for w in _CAP_ANSWER):
            return False, "他问你能干什么，你答的却是一件小动作"
    if facts.get("mode") == "relation":
        if not any(w in text for w in _RELATION_ANSWER):
            return False, "他问你们俩的关系，你没正面答"

    # 他在问名字。这一类最容易「答得流利但答的是另一件事」：
    # 「你应该叫我什么」→「团团是你喊我的名字呀」。所以在出口硬性验一遍主语。
    if facts.get("mode") in ("address", "identity"):
        known = facts.get("known_name")
        if facts.get("mode") == "address":
            if known:
                # 记住了却没叫出来，等于没记住
                if known not in text:
                    return False, f"他问你他叫什么，你知道他叫「{known}」，却没叫出来"
            elif not any(w in text for w in _DONT_KNOW):
                # 不知道的时候，任何一句不认账的话都是在拿别的东西凑数
                if "团团" in text:
                    return False, "把他该叫的名字答成了我自己的名字（团团是我，不是他）"
                return False, "他问你他叫什么，你不知道，却没说不记得，也没问他"
        else:
            # 「你叫我团团就行」是在答「我该怎么叫**你**」，主语反了
            if re.search(r"你叫我?团团", text):
                return False, "问的是我的名字，答的却是他该怎么叫我（说反了）"
            if "团团" not in text and "仓鼠" not in text:
                return False, "他问你是谁，你没说出自己的名字"

    # 他在问「刚才说了什么」。这一支最典型的错答是**报账**——
    # 原实现把「那我们刚刚说了什么」答成「你刚传的图里，23 分钟做了 15 题对 9 题」：
    # 每个数都是真的，但一个字都没回答他问的那件事。
    if facts.get("mode") == "recap":
        if not any(w in text for w in _RECAP_ANSWER):
            return False, "他问刚才说了什么，你一句都没复述"
        if not (facts.get("recent") or []) and re.search(r"\d", text):
            return False, "刚才没聊几句，你却报出一串数"
        # 复述可以换角度，但不能一个字都不改地重播上一遍。
        # 换不换问法都要管：问法没变时上一句落在 avoid_same（上面那道放行了），
        # 问法变了落在 avoid（84% 就拦）。这里补一道只认逐字重复的，
        # 因为复述的内容本来就该相似，松一点就会误杀真的复述。
        dup = repeated(text, avoid_same, ratio=0.98, prefix=False)
        if dup:
            return False, f"复述跟刚才那句几乎一样「{dup[:16]}」，换个说法"
        # 比例判不出来这一种：在自己的旧话前面加半句、后面补半句。
        # 实测第三遍的输出里，整整 20 个字是从上一次的回答里一个不差搬过来的。
        chunk = _borrowed(text, avoid_same or avoid)
        if chunk:
            return False, f"把刚才那句里的「{chunk[:14]}」整段搬过来了，自己组织话说"

    # 他要的是办法。回一句「我趴你手边陪你」是把问题晾在那儿——
    # 听着温柔，但他问的是「怎么办」，答的是「我在」。
    if facts.get("mode") == "solution":
        if not any(w in text for w in _SOLUTION_ANSWER):
            return False, "他在问怎么办，你只给了陪伴，没给办法"
        # 复述处境也是同一种「没答」：他知道自己有多惨，不用再听一遍。
        # 历史里写着「他更早说过：模考又崩了」，模型很容易拿它当开场。
        if re.search(r"你刚说|你刚才说|你说过", text):
            return False, "他在问怎么办，你却把他的处境复述了一遍"

    # 他在问今天的账，却把账安到他嘴上：「82 分钟，你自己跟我说的」——
    # 那数是从记录里算的，他没说过。这类出处错位比报错数更伤信任，
    # 因为他会想「我什么时候说过」。
    #
    # 只对「账」生效。名字类不能一起拦：他报名字时「你叫林一，你自己跟我说的」
    # 是**真话**（名字确实是他说的），一起拦就把真话逼成兜底——
    # 实测问「你叫什么」，本来答得好好的，两次都被这句拦下，最后掉进模板。
    account_words = facts.get("mode") == "data" or (
        facts.get("mode") in ("address", "identity") and not facts.get("known_name"))
    if account_words and re.search(r"你自己跟我?说的|你亲口说的|你确认过", text):
        return False, "他没问出处，却把话安到了他嘴上"

    # 把旁白当成他的原话：只有真的存在「他说的」记忆时，才允许说「你说过」
    # 「你能干什么」那一支是例外：它说的是能力（「你说过的事我也记着」），
    # 不是在引某一句原话，按字面拦等于把自我介绍也拦了。
    if re.search(r"你说过|你上次说|你跟我?说", text) and facts.get("mode") != "capability":
        said_by_him = [m for m in (facts.get("memories") or []) if m.get("who") == "他"]
        if not said_by_him:
            return False, "把系统旁白当成了他的原话"

    # 他难过的时候报数字，是这只仓鼠最不该做的事——实测模型一定会犯，所以硬拦。
    # 但「累死了，我今天做得怎么样」是他自己开口问的账，那时候给数才是答他，
    # 不给数等于装没听见。所以 data 模式放行，和 build_facts 那边给数保持一致。
    if looks_sad(user_text) and re.search(r"\d", text) and facts.get("mode") != "data":
        return False, "他正难受，这时候不该报任何数字"

    made_up = [p for p in _BANNED_COMPARE if p in text]
    if made_up:
        return False, f"编了库里没有的比较基线 {made_up}"

    role = [p for p in _BANNED_ROLE if p in text]
    if role:
        return False, f"把记忆安到了他头上 {role}"

    if _THIRD_PERSON.search(text):
        return False, "用了第三人称，角色崩了"

    if _SEED_WRONG.search(text):
        return False, "把瓜子说成了他的（瓜子是我自己的，我一直分他）"

    allowed = set(brain.allowed_numbers(facts)) | _user_numbers(user_text)
    # 出处摘要里也带数（「判断推理 15 题对 9 题」），那些同样是他给过我的
    for src in (facts.get("sources") or []):
        allowed |= {int(n) for n in re.findall(r"\d+", str(src.get("what") or ""))}
    # 复述他的话时，话里的数（「我今天做了 60 道」）是他自己说过的，不算编。
    # 不加这一段，recap 只要引到原话里的数字就会被判成编造，然后掉兜底。
    for r in (facts.get("recent") or []):
        allowed |= {int(n) for n in re.findall(r"\d+", str(r.get("text") or ""))}

    # 中文写法的数量：换算成数再判。库里真有这个数就放行（「六成」= 60%，
    # 事实里就是 60），换算完对不上才拦（「十三分钟」对不上 130 分钟）。
    # solution 给的是**行动建议**，不是账。「你先闭眼三分钟」里的时长是他要做的事，
    # 不是从库里抄的数——按「编造数字」拦会把一条正确的建议打回兜底
    # （实测就这么掉过一次：原文「你先闭眼三分钟，回来只做最熟的那几道」）。
    # 承诺类（「再学 30 分钟」）另有 _COMMIT_MINUTES 管着，不会漏。
    if facts.get("mode") != "solution":
        cn_bad = [(raw, n) for raw, n in cn_amounts(text) if n not in allowed]
        if cn_bad:
            raw = [r for r, _ in cn_bad]
            return False, f"把数字改成了中文写法 {raw}，对不上库里的任何一条"

        stray = [int(n) for n in re.findall(r"\d+", text) if int(n) not in allowed]
        if stray:
            return False, f"出现事实里没有的数字 {stray}"

    # 他在问今天的账，回答里一个数都没有，就是不认账。
    # 清单里「data 出口必须有分钟数」以前只写在文档上：它回「唔，你今天做了不少呢」，
    # 所有闸都放过去了——听着没毛病，但一个字也没答他问的那笔账。
    # 放在最后：先说更具体的错（编数字、说错科目），这句话只是兜底要求。
    if facts.get("mode") == "data":
        ans = facts.get("answer") or {}
        if ans.get("kind") in ("today", "week", "weakest", "module") \
                and not re.search(r"\d", text):
            return False, "他在问账，你一个数都没给"

    # 提到模块名时，数字必须是这个模块的（防「数字是真的但安错了人」）
    ok, reason = brain.check(text, facts)
    if not ok and "数字" not in reason:
        return False, reason
    return True, ""


# ---------- 对话的连贯性 ----------
# 「一问一答」和「像认识你的人」的差别不在模型大小，而在这一轮它手上有没有上下文。
# 以前这里只有一串「他更早说过：」，于是他每换一个话题，它都像第一次听说——
# 不知道自己上一句答了什么，也不知道他上一句问的是什么，只能重新挑一样素材念。
# 下面这几个函数就是把这三样东西补上：他上一句问的、我上一轮答的、他这一句顺着哪件事补的。

# 拿来回指的关键词要去掉这些：它们是字，不是话题
_STOP_HISTORY = ("的", "了", "吗", "呢", "吧", "和", "跟", "我", "你", "它", "这", "那",
                 "就", "也", "还", "是", "在", "有", "个", "们", "不", "没", "啊", "呀",
                 "今天", "怎么样")


def _prior_user_turns(history: list[dict] | None, current_text: str = "",
                      limit: int = 5) -> list[str]:
    """他最近说过的几句（不含这一句），从旧到新。"""
    out: list[str] = []
    cur = (current_text or "").strip()
    for t in (history or []):
        if t.get("role") != "user":
            continue
        c = (t.get("content") or "").strip()
        if not c or c == cur:
            continue
        out.append(c)
    return out[-limit:]


def _last_assistant_line(history: list[dict] | None) -> str:
    """它自己上一轮答的那句。它看不见这句，就不知道该接着哪儿说。"""
    for t in reversed(history or []):
        if t.get("role") == "assistant":
            return (t.get("content") or "").strip()
    return ""


def _core_words(text: str, limit: int = 5) -> list[str]:
    """一句话里能拿来回指的关键词：按出现顺序，去重、去停用字。"""
    out: list[str] = []
    for chunk in re.findall(r"[\u4e00-\u9fa5]{2,4}", text or ""):
        if len(chunk) < 2 or chunk in _STOP_HISTORY:
            continue
        if chunk in out:
            continue
        out.append(chunk)
    return out[:limit]


def _continuation_line(history: list[dict] | None, current_text: str = "") -> dict:
    """他这一句是不是顺着上一句往下补的（「判断推理呢？」「那资料分析呢？」）。

    这类短句里既没有情绪词也没有问法词，单看一句判不出它在问什么——
    但把它和上一句并排看，重合的那几个字就是话题。把这个"锚"找出来，
    模型才不会把它当成一句全新的闲聊，重新挑一样素材念一遍。
    """
    prior = _prior_user_turns(history, current_text)
    if not prior:
        return {}
    cur = (current_text or "").strip()
    if not cur or len(cur) > 22:
        return {}
    if any(w in cur for w in _SOFT_WORDS):
        return {}                      # 带情绪词的短句是叹气，不是追问
    same = [w for w in _core_words(prior[-1]) if w in cur]
    if not same:
        return {}
    return {
        "anchor": same[0],
        "line": "他这一句是顺着「{}」往下问的".format(same[0]),
    }


def _mentioned_recently(history: list[dict] | None, memories: list[dict],
                        window: int = 8) -> list[str]:
    """最近这几轮已经提过的旧事。这轮别再提——一件小事被反复提，听着像没话找话。"""
    blob_parts = []
    for t in (history or [])[-window:]:
        if t.get("role") == "assistant":
            blob_parts.append(t.get("content") or "")
    blob = " ".join(blob_parts)
    if not blob:
        return []
    hits: list[str] = []
    for m in (memories or []):
        text = (m.get("text") or m.get("quote") or "")
        words = [w for w in _core_words(text, limit=8)]
        if len(words) >= 2 and all(w in blob for w in words[:2]):
            hits.append(text)
    return hits[:5]


def build_messages(user_text: str, *, facts: dict, history: list[dict] | None = None) -> list[dict]:
    """拼请求。system 必须第一条——这是 OpenAI 协议的硬要求，也是人设的地基。

    历史**不喂它自己的原句，只喂原句的话题**。这条是踩出来的：
    以前把上一轮它的整句回答放回去，qwen-flash 会一字不改地照抄（连着三轮同一个句子），
    而抄出来的那句又落库、又进下一轮的历史，于是越问越像唱片跳针。
    但它**完全看不见自己答过什么**也不行——那就不知道该顺着哪儿往下说，
    于是它每次都重新挑一样素材念，这就是"像写死的程序"最直接的来源。
    折中办法：给它关键词，不给句子。它知道上一轮聊的是「模考」，但不拿到可抄的整句。
    """
    msgs: list[dict] = [{"role": "system", "content": PERSONA}]
    # 远近要标死。以前一律写成「他更早说过：X」，几条并排扔进来谁先谁后全靠它猜——
    # 实测安慰的时候它把**更早**那句当成「你刚才说」，人还没叹气它就开始回顾，
    # 听着像没在听。现在最新的排在最前面，并且写明是第几句。
    cur_text = (user_text or "").strip()
    said = [t for t in (history or []) if t.get("role") == "user"
            and (t.get("content") or "").strip() != cur_text][-3:]
    his_blob = " ".join((t.get("content") or "") for t in (history or [])
                        if t.get("role") == "user")
    for i, turn in enumerate(reversed(said)):
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        label = ("他刚说的上一句" if i == 0 else
                 "再往前一句" if i == 1 else "更早的一句")
        msgs.append({"role": "user", "content": f"（{label}：{content[:160]}）"})
    # 它自己上一轮答了什么：只给话题词，不给那句话。
    # 有了这个它才知道"刚才我们聊到哪儿了"，但不至于把那句原封不动再念一遍。
    # 话题词优先挑**他话里也出现过的**——那才是这轮的主题，
    # 否则会挑到「先歇会儿」这类它自己的口头禅，指了等于没指。
    own = _last_assistant_line(history)
    own_words = [w for w in _core_words(own, limit=6) if w in his_blob][:2]
    if not own_words:
        own_words = _core_words(own, limit=2)
    if own_words:
        msgs.append({"role": "user",
                     "content": "（你上一轮答的是关于「{}」的那句，"
                                "**换一句话往下接**，不许把那句再说一遍）".format("、".join(own_words))})
    # 他这一句是顺着上一句往下补的（「那资料分析呢？」）。
    # 这种短句单看判不出在问什么，把锚点出来它才不会当成全新话题重念一遍素材。
    cont = _continuation_line(history, user_text)
    if cont.get("line"):
        msgs.append({"role": "user", "content": "（{}，接着这个说，"
                                                "别当成新话题重新介绍一遍）".format(cont["line"])})
    # 最近这几轮已经提过的旧事，这轮别再提。
    # 一件小事被连着提三遍，听着就不是记得他，而是没话找话。
    # recap 例外——他要的就是刚才那些话，这时候"重复"是任务本身。
    if facts.get("mode") != "recap":
        stale = _mentioned_recently(history, facts.get("memories") or [])
        if stale:
            msgs.append({"role": "user",
                         "content": "（这几件事最近刚提过，这轮别再提：{}）".format(
                             "；".join(s[:22] for s in stale))})
    facts_json = __import__("json").dumps(facts, ensure_ascii=False, separators=(",", ":"))
    hint = ""
    if facts.get("mode") == "recap":
        # 这一支是唯一允许、而且必须复述自己旧话的地方。
        # 其它模式不给它的原话是为了防照抄，但「我们刚才说了什么」的任务本来就是复述，
        # 不给就等于让它编。所以这里连「谁说」都标好，只许照着 recent 说。
        hint = ("\n他在问你们刚才说了什么。照 facts.recent **从最近一轮往前说**："
                "先说他问的是什么，再说你当时怎么答的，最多说两轮。"
                "第一句用「你刚才说……」或者「我们刚聊到……」开头。"
                "**不要报今天的账**——不要说分钟数、正确率、题量、科目，他问的是话不是数。"
                "facts.recent 是空的就说刚才没聊几句，让他接着说，别编内容。"
                "40 到 60 字。")
    elif facts.get("mode") == "address":
        name = facts.get("known_name")
        if name:
            hint = ("\n他在问你该叫他什么。直接叫出 facts.known_name（「{}」），"
                    "再说一句你记着这个名字。别答成你自己的名字——团团是你的名字，"
                    "不是他的。20 字以内。".format(name))
        else:
            hint = ("\n他在问你该叫他什么，可你**不知道他叫什么**（facts.known_name 是 null）。"
                    "就老实说你还不知道、让他告诉你，别编一个名字，"
                    "更不许把你自己的名字「团团」当成他的名字。"
                    "也别说「你叫我团团」——那是答反了。20 到 30 字。")
    elif facts.get("mode") == "identity":
        name = facts.get("known_name")
        hint = ("\n他在问你是谁。你叫团团。" +
                ("顺口带一句他叫「{}」。".format(name) if name else
                 "别把他的名字答成「团团」——那是你的名字。") +
                "20 到 35 字。")
    elif facts.get("mode") == "capability":
        hint = ("\n他在问你能干什么。照 facts.skills 说，挑两件最要紧的，"
                "每件一句话，说人话（「你给我看截图，我就知道你今天做了多少」）。"
                "不要把三件都念完，不要用瓜子动作凑数，不要提藏瓜子。30 到 45 字。")
    elif facts.get("mode") == "relation":
        hint = ("\n他在问你们俩的关系。第一句就把话说白——「喜欢」「我陪你」「我不走」"
                "这几个词要用上一个，别绕成「藏瓜子」「放心上」这种。"
                "一句话答完，可以加一个小动作。不要反问「你呢」，不要发誓。"
                "**这一句里不许出现「瓜子」两个字**：实测它一提到瓜子就把方向说反"
                "（「我把你瓜子藏起来」「你给的瓜子」），整句话就废了。"
                "动作换成「我趴你手边」「我蹭你一下」。20 到 35 字。")
    elif facts.get("mode") == "data":
        ans = facts.get("answer") or {}
        kind = ans.get("kind")
        if kind == "weakest":
            hint = ("\n他在问哪一块最弱。第一句就直接说模块名和正确率（照 answer.module 和"
                    "answer.accuracy_pct 说，比如「数量关系最毛，52%」），第二句说题量或者做个小动作。"
                    "不要提截图，不要提他说过的话，不要报今天的分钟数。20 到 35 字。")
        elif kind == "week":
            hint = ("\n他在问这周的进度。第一句直接说本周做到几天、目标几天（照 answer.done 和"
                    "answer.target 说，比如「这周 4 天了，还差 1 天」），"
                    "再用一个小动作收尾。不要报今天的分钟数，不要报模块，不要提截图。20 到 35 字。")
        elif kind == "module":
            hint = ("\n他在问这一科的成绩。先说这一科的正确率（answer.accuracy_pct），"
                    "再说多少题（answer.questions）。只报这两个数，别扯别的科目。20 到 35 字。")
        elif kind == "empty":
            hint = ("\n他今天还没有记录。就说今天还没看到他的记录，别提任何数字，"
                    "也别编一个时长。20 字以内。")
        else:
            hint = ("\n他在问今天的账。第一句说今天多少分钟（answer.minutes），"
                    "有 answer.accuracy_pct 就跟着说一个；只报这两个数，"
                    "不要念周目标，不要提模块，不要提截图。20 到 35 字。"
                    "正确率写成「60%」，不许写成「六成」。"
                    "这一轮不许出现「图」「截图」「照片」这三个字——他问的是今天，不是那张图。"
                    "也不许把账安到他嘴上：不能说「你自己跟我说的」「你确认过」——"
                    "这些数是他做题时记下的，不是他告诉你的。")
    elif facts.get("mode") == "advice":
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
    elif facts.get("mode") == "solution":
        # 和 comfort 相反：他要的是办法，只给陪伴等于把问题晾在那儿。
        # 但也别列清单——三条一起上就成了说教，他这会儿没力气听清单。
        hint = ("\n他现在累，而且明确问了「怎么办」。先从 facts.tips 里挑**一条**，"
                "说清楚具体怎么做（「把手机放到看不见的地方，回来只做最熟的那几道」这种），"
                "前面认一句他确实累，20 到 40 字。"
                "只挑一条，不要列三条；不要报任何数字；不要提截图；"
                "不要说「我听见了」「你要加油」。"
                # 他会把他的旧话写进历史（「他更早说过：模考又崩了」），模型很容易
                # 拿这句当开场，于是又把处境复述一遍——他要的是下一步，不是被重复一遍。
                "**不要复述他之前说过的话**，不要用「你刚说……」开头，也别提模考、错题这些旧账。")
    # 他刚问过同一件事。不提醒的话，它会照上一遍的句式再念一次——
    # 数没错，但界面上看着像卡死（用户截图里骂的就是这个）。
    # 只说「你答过了」不够：它的原话被 build_messages 滤掉了，它根本不知道自己
    # 上次说了什么，只能又凑出同一句。所以把上一句当成**反面样本**贴给它，
    # 明确「不许用这段里的开头」。贴出来是有风险的（它爱照抄），
    # 但不说「别抄这句」风险更大——实测后者十次里七次逐字重来。
    _, asked_before = split_recent_replies(history, user_text)
    if asked_before:
        # 问到第二遍、第三遍，光说「换个说法」是不够的：账就那几个数，
        # 它能换的只有词。所以直接给一个**结构**，让它有地方可换：
        #   第二遍 → 先说为什么，再说结论（和第一遍的顺序反着来）；
        #   第三遍起 → 别复述结论了，先说一个小动作，再把结论带出来。
        # 这是把「复读」变成「换个侧重点」，界面上读起来像它想了两遍。
        if facts.get("mode") == "data":
            # 问账那一支的提示是「第一句说分钟数」，那条和「换个说法」是打架的：
            # 它照第一条办，出来的句子必然一模一样。所以这里给一个**在数据模式里也成立**
            # 的换法——换语序，不换数字。
            # 三本账的换法不一样：「这周还差几天」里根本没有正确率，
            # 笼统说「先说正确率」会把周进度那一支带沟里（实测它就懵了，两次照抄掉兜底）。
            kind = (facts.get("answer") or {}).get("kind")
            if kind == "week":
                angle = ("这次换个语序（这一条优先于上面「第一句说天数」）：上一遍先说了做到几天，"
                         "这次先说还差几天，再说做到几天。天数一个都不许改。")
            elif kind in ("weakest", "module"):
                angle = ("这次换个语序：上一遍先说了正确率，这次先说题量，再说正确率。"
                         "模块名和数都不许改。")
            else:
                angle = ("这次换个语序（这一条优先于上面「第一句说分钟数」）：上一遍先说分钟数，"
                         "这次先说正确率，没有正确率就先做一个小动作，再把分钟数放后面。"
                         "数字一个都不许改。")
        elif facts.get("mode") in _REPEAT_ANGLE:
            # 这几类的答案本来就短（「我趴你手边，喜欢你呀」），能换的只有词。
            # 所以直接告诉它换成哪个词，别让它自己找。
            angle = _REPEAT_ANGLE[facts["mode"]]
        elif len(asked_before) == 1:
            angle = ("这次换个结构：上一遍是先说结论，这次先说为什么（那个数），再说结论。")
        else:
            angle = ("这已经是第 {} 遍了，别再从结论开头：先说一个具体的小动作"
                     "（我把瓜子收起来了 / 我趴你手边），再把结论带出来。".format(len(asked_before) + 1))
        hint += ("\n这是他刚问过的同一件事，你上一遍的原话是：「{}」。"
                 "数一个字都不许变，但话不能跟上一遍雷同：不许用上面那段里的开头四个字，"
                 "也不许把它整句搬过来。{}".format(asked_before[-1][:40], angle))
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
    if "把瓜子说成了他的" in (reason or ""):
        # 只说「说错了」它会换个说法继续说反（实测「你给的瓜子」改成「你推过来的瓜子」）。
        # 也别只教它改成「我把瓜子推给你」——问关系的时候它就是在拿瓜子绕话题，
        # 再教一遍瓜子只会绕得更远。所以给两条路，其中一条是别提瓜子。
        specific = ("瓜子是你自己的。要么说「我把瓜子推给你」，"
                    "要么这一句干脆别提瓜子——直接说你真正想说的那句。")
    elif "给了继续学的时长" in (reason or ""):
        # 矛盾必须先说「结论是什么」，否则它只会把分钟数删掉，结论还是错的
        specific = "结论已经算好了：现在不该继续。这一句不许出现任何分钟数，也不许说「再学一会儿」。"
    elif "叫他别学了" in (reason or ""):
        specific = "结论是还能再来一会儿。照 verdict.again_minutes 说，别叫他停，别说早点睡。"
    elif "一个数都没给" in (reason or ""):
        specific = "先把答案里的那个数说出来（多少分钟、几天、正确率），别的都放后面。"
    elif "答成了我自己的名字" in (reason or "") or "却没叫出来" in (reason or "") \
            or "却没说不记得" in (reason or ""):
        # 名字这类问题，它最爱把主语搞反：问他叫什么，答「你叫我团团」。
        # 光说「答错了」没用，得把「谁是谁」再摆一遍。
        specific = ("先分清谁是谁：团团是你的名字，「你」指的是他。"
                    "他在问他叫什么——你知道就直接叫出来，不知道就说「你还没告诉我你叫什么呢」，"
                    "再请他告诉你。不许把你的名字当成他的名字。")
    elif "没说出自己的名字" in (reason or ""):
        specific = "他在问你是谁。你叫团团，就直说「我叫团团」，别忘了加一句你在陪他。"
    elif "复述跟刚才那句几乎一样" in (reason or ""):
        # 他问「刚才说了什么」，它把上一遍的复述原样又播了一遍。
        # 这里不能照搬下面「复读」那条改法——那条要求「换一句全新的」，
        # 而 recap 的任务就是复述，换掉内容等于不答。要换的只是入口。
        specific = ("上一遍已经这么复述过了。换个开头：先用一句话说你们在聊哪件事"
                    "（「你在说模考崩了那件事」），再说你当时是怎么回他的。"
                    "内容还是那件事，但句子不能跟上一遍一样。")
    elif "原样说了一遍" in (reason or ""):
        # 同一件事他问了两遍。这时候不能叫它「别重复」——账就那笔，数还得说。
        # 要改的是句子的壳：开头不能跟上一遍沾边，但同一笔账得说全。
        # 只说「换个说法」它换不动（能换的词就那么几个），所以给一个结构：
        # 先动作、再结论，跟上一遍的顺序反过来。
        specific = ("他问的还是同一件事。数一个都不许改，但这句话不能跟上一遍雷同："
                    "开头必须换掉，别再用上一遍那前几个字，也别整句照搬。"
                    "换个结构：先说一个具体的小动作，再把结论带出来。")
    elif "复读" in (reason or ""):
        specific = ("那句是他刚才已经听过的话。换一句全新的，直接回答他这一次问的问题，"
                    "不许接上一句，也不许换个说法把上一句重说一遍。")
    elif "中文写法" in (reason or ""):
        # 注意：「把 82 写成八成」也带「数字」两个字，但改法和漏数字完全相反——
        # 让它「不许出现任何数字」，它就会把 82 改得更彻底地写成中文，越改越错。
        specific = "数字照原样写阿拉伯数字：82 就说「82 分钟」，不许写成「八成」「六成」，也不许换算成小时。"
    elif "时长" in (reason or ""):
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
# （词表在上面 _ASK_DATA，别在这里再定义一份——两份词表必然漂移）


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
    # 「再学一会儿吗」「还能再学点吗」——主语被省掉了，句式分支要求带「我/今天」，
    # 于是这类最常见的一问一直落在 normal，它答成一句鼓励，等于没给主意。
    "再学一会", "再练一会", "再来一会", "还能学", "还能再", "还能撑", "再撑一会",
)

# 有了结论才叫回答。这些话里一个都没有，就是在拿安慰当答案
_ADVICE_WORDS = ("该", "别", "不用", "可以", "再", "先", "停", "睡", "歇", "换", "做",
                 "补", "够", "继续", "收工", "明天", "算了")

# 结论和算出来的相反，是这只宠物最危险的一种错：它刚算完「今天该停了」，
# 嘴上却来一句「再刷二十分钟」——他照着做，明天更累，还会觉得是它让的。
# 所以只在**明确矛盾**上拦，不要求它必须用到某个词（那样误杀太多，一说就掉兜底）。
# 刻意只认时间量词：switch 那一支本来就要说「回头看错题」，
# 把「再看两道」也算成继续，会把正确的建议打成错。
_CONTINUE_INTENT = re.compile(r"(?:再|继续|接着|多)[^，。！？]{0,5}?(?:分钟|小时|一会|会儿)")
# 「我再陪你十分钟」「再聊会儿」不是学习承诺，是它自己留下的动作。
# 这些字出现在同一个片段里就不算「继续学」——不然 stop 时它说句贴心话都要被打回。
_NOT_STUDY = ("陪", "睡", "躺", "坐", "抱", "吃", "喝", "聊", "玩", "看你")
# 刻意不收「收工」「去睡」：「再 20 分钟，做完就收工」是 keep 的正常说法，
# 收进来会把正确答案打成错的。只留明确否定学习的说法。
_STOP_INTENT = ("别学了", "不用学", "别刷了", "别做了", "今天就到这", "今天到这儿",
                "早点睡", "歇着吧")


def _continues_study(text: str) -> bool:
    """这句里有没有「接着学多久」的意思。"""
    for m in _CONTINUE_INTENT.finditer(text or ""):
        if not any(w in m.group(0) for w in _NOT_STUDY):
            return True
    return False


def _verdict_conflict(text: str, verdict: str | None) -> str:
    """这句话跟算好的结论是不是反的。反了就返回原因，没反返回空串。"""
    if not verdict:
        return ""
    t = text or ""
    if verdict in ("stop", "switch") and _continues_study(t):
        return ("结论是「{}」，你却给了继续学的时长".format("停" if verdict == "stop" else "换个轻的"))
    if verdict in ("keep", "start") and not _continues_study(t) \
            and any(w in t for w in _STOP_INTENT):
        return "结论是还能再来一会儿，你却叫他别学了"
    return ""

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


def fallback(user_text: str, facts: dict | None = None, repeat: bool = False) -> str:
    """模型不在（没网、超时、说了不该说的）时，它还是会说一句人话，只是笨一点。

    这些句子一个数字都不带 —— 笨可以，假不行。

    两个例外，都是「不答等于没答」的时候：

    - 「该不该学」：照算好的结论说，哪怕模型挂了也得给个明确答复。
    - 「今天怎么样 / 哪块最毛」：这类问账的话，回一句「我在呢」等于装没听见。
      直接照 facts.answer 的数字说，话笨但每个数都是真的。

    ``repeat=True`` 是他又问了一遍同一件事、而已有的回答跟上一次一个字都不差：
    在前头认一句「刚说过啦」，再把同一笔账报一遍。数不变，界面上一眼能看出
    它在应他这句，不是卡住了。
    """
    facts = facts or {}
    # 他问「刚才说了什么」，回「我在呢」等于装没听见。手上真有他的原话就念一句，
    # 没有就老实说没聊几句——别编一段不存在的对话。
    if facts.get("mode") == "recap":
        recent = facts.get("recent") or []
        # 最后一条可能就是他上一遍问的「刚才聊到哪了」。拿它当内容，
        # 等于用问句回答问句（实测真出过：「你刚才说『刚才聊到哪了』」）。
        said = [r.get("text", "") for r in recent
                if r.get("who") == "他" and not _asks_recap(r.get("text") or "")]
        if said:
            # 同一件事问了不下两遍、每次都掉兜底时，老是念最近那一句就是两条一样的
            # 泡泡。往前挪一句，说得还是真的，只是换了他刚才说的另一件。
            pick = said[-2] if repeat and len(said) >= 2 else said[-1]
            head = "刚说过啦，" if repeat else ""
            return f"{head}你刚才说「{pick}」，我记着呢。"
        # 他自己的话都被问句占满了，就说我刚才答过什么——那也是对话的一部分
        mine = [r.get("text", "") for r in recent if r.get("who") == "我"]
        if mine:
            return f"我刚才跟你说的是「{mine[-1]}」。"
        return "刚才没聊几句呀，你接着说，我听着。"
    # 他问了怎么办，就别只回一句「我在」。给一条不带数字的具体事，笨但有用。
    if facts.get("mode") == "solution":
        tips = facts.get("tips") or []
        if tips:
            return "那先试一个：" + tips[len(user_text or "") % len(tips)] + "。"
        return "先别硬撑，起来走一走再说。"
    # 问名字的两支不能掉进「我在呢」：他问的是称呼，答一句空话等于装没听见。
    # 有名字就叫出来；没有就明说不知道，并请他告诉你。
    if facts.get("mode") == "capability":
        return "我能看你发的截图，帮你把账记下来；你说过的事我也记着。"
    if facts.get("mode") == "relation":
        return "喜欢呀，我天天在这儿等你来。"
    if facts.get("mode") in ("address", "identity"):
        name = facts.get("known_name")
        if facts["mode"] == "identity":
            return f"我叫团团呀。" + (f"你叫{name}，我记着呢。" if name else "你呢，你叫什么？")
        if name:
            return f"你叫{name}呀，我记着呢。"
        return "你还没告诉我你叫什么呢，说给我听听呀。"
    verdict = (facts.get("verdict") or {}).get("verdict")
    if verdict:
        return coach.fallback(verdict=verdict,
                              again_minutes=(facts.get("verdict") or {}).get("again_minutes"),
                              seed=user_text)
    plain = _plain_answer(facts, repeat=repeat)
    if plain:
        return plain
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


def _plain_answer(facts: dict, repeat: bool = False) -> str:
    """问账时的兜底：不加形容词，照着 answer 报一句。数都是算好的，不会假。"""
    ans = facts.get("answer") or {}
    kind = ans.get("kind")
    head = "刚说过啦，" if repeat else ""
    tail = "。" if repeat else "。我记着呢。"
    if kind == "today" and ans.get("minutes") is not None:
        text = f"今天 {ans['minutes']} 分钟"
        if ans.get("accuracy_pct") is not None:
            text += f"，正确率 {ans['accuracy_pct']}%"
        return head + text + tail
    if kind in ("weakest", "module") and ans.get("module"):
        text = f"{ans['module']}最毛，{ans.get('accuracy_pct')}%"
        if ans.get("questions"):
            text += f"，{ans['questions']} 题"
        return head + text + tail
    if kind == "week":
        done, target = ans.get("done") or 0, ans.get("target") or 0
        if ans.get("owed"):
            return head + f"这周 {done}/{target} 天，还差 {ans['owed']} 天" + tail
        return head + f"这周 {done}/{target} 天，数够了" + tail
    if kind == "empty":
        return "今天还没看到你的记录，我不瞎猜。"
    if kind == "no_data":
        return "题量还太少，我先不下结论。"
    return ""

# _SURVIVE_TEST_
