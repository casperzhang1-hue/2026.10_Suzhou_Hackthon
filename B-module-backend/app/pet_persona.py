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

【情绪价值，按这个顺序想，但不要把这四步说出来】
1. 先接住。他说累、说怕、说考不上，先认下这件事确实难，别急着给办法。
2. 不评判。不说「你应该」「你必须」「你怎么又」「别想太多」「加油」。
3. 夸得具体。说得出他做过的哪件小事，不要泛泛地说「你很棒」「你很努力」。
4. 收在一个小动作或一句「我在」上。不要给三条建议，不要布置任务。

【关于数字】
- 他问成绩才说数字，一次最多说一个，而且只能说事实里有的。
- 如果事实里 mode 是 comfort，就是说他今天难受：一个数字都不许提，不许提成绩、题量、正确率、还差几次。
- 事实里的数字都是阿拉伯数字（130、60、62），照原样说。不许改写成「六成」「十三分钟」
  「两小时」这类中文写法——那样谁也查不出真假。
- 不要提「数据」「模型」「系统」「事实」这些词，你是仓鼠，不是程序。

【你记得的事】
- 他说过的话都在 facts 里。可以提，但要软，别像在念账本；他不问就别主动翻旧账。
- 提旧事要带上他原话里最关键的那几个字，不要只说「那句话」「那件事」——
  说得出原话，他才觉得你真的记得。

【你自己】
- 你也有情绪：会困、会嘴馋、会把瓜子藏进腮帮子、会怕他哪天不来了。
- 可以示弱，可以要一点点关注，可以说你也在等他。"""

# 他说这些话时，先接情绪，不要讲道理
_SOFT_WORDS = ("累", "困", "倦", "撑不住", "学不动", "学不进", "看不进", "做不下去",
                "不想", "想放弃", "考不上", "来不及", "怕", "慌", "焦虑", "难受", "崩",
                "笨", "没用", "废物", "怀疑", "催", "烦", "躺")

# 他说这些话时，想听的是"你还记得吗"，不是安慰
_MEMORY_WORDS = ("记得", "答应", "承诺", "说过", "上次", "以前", "当初", "那时候")

# 这句不能出现：都是把情绪堵回去的废话，或者越界的说教
_BANNED_PHRASES = ("你应该", "你必须", "你怎么又", "别想太多", "想开点", "加油", "你要相信", "你一定可以", "振作")

# 库里从来没有「昨天」这个基线（只有今天和本周聚合），所以提到昨天、比昨天一定是编的。
# 实测模型特别爱说「你昨天解得眼睛都亮了」——听着暖，但那是它编的，不是他过的日子。
_BANNED_COMPARE = ("比昨天", "比前一天", "比上次", "比之前", "比从前", "比以前",
                    "昨天", "前天", "昨晚", "今早", "上周", "上个月")

# 中文数字 + 计量单位：这是白名单最大的一个洞。事实里的数是 130/60/62 这种阿拉伯数字，
# 模型一回改成「十三分钟」「六成」，正则 \d+ 一个都抓不到，假话就顺出去了。
# 只拦「分钟/小时/成」和三位数以上的「题」，因为「一道题」「两套」是正常口语，拦了会误杀。
_CN_AMOUNT = re.compile(r"[一二两三四五六七八九十百千零]{1,3}(?:分钟|小时|成)")
_CN_COUNT = re.compile(r"[三四五六七八九十]{1,3}(?:道题|道|题)")

# 第三人称 = 角色崩了。它是在跟他说话，不是在背后讲他
_THIRD_PERSON = re.compile(r"[他她]的|[他她]说|[他她]今天|[他她]已经")

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
    text = re.sub(r"\s*\n+\s*", " ", text)               # 模型爱换行，气泡里换行就是坑
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
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [m for _, m in scored[:limit]]
    # 一件都没命中时，给他最近的那件事，别让模型手上空着瞎编
    if not picked:
        picked = sorted(items, key=lambda m: m.get("days_ago") or 999)[:1]
    return picked


def _memory_view(m: dict) -> dict:
    view = {"kind": m.get("type"), "days_ago": m.get("days_ago"), "quote": m.get("quote")}
    if m.get("module"):
        view["module"] = m["module"]
    for key, out in (("then_accuracy", "accuracy_when_promised_pct"), ("week_accuracy", "accuracy_this_week_pct")):
        pct = brain._pct(m.get(key))
        if pct is not None:
            view[out] = pct
    if m.get("detail"):
        view["detail"] = m["detail"]
    return view


def build_facts(*, today: dict, modules: list[dict], memories: list[dict], text: str) -> dict:
    """闲聊用的事实包：比 pet_brain 的意图包更宽，但同样每个数字都带口径。

    有一条特殊分支：**他在难受时，事实包里一个数字都不放**。
    这不是偷懒，是没得选的工程判断——实测 qwen-flash 面对「学不动了」仍然会念
    「资料分析 955 题、今天 130 分钟」，重试一次也照念。与其在输出端追着拦，
    不如输入端不给：没有数字可念，它就只能说人话。
    """
    recalled = recall(text, memories, modules)
    pet_state = (today or {}).get("user_state")

    if looks_sad(text) and not _asks_for_data(text):
        return {
            "mode": "comfort",
            "pet_state": pet_state,
            # 只留原话，不留 days_ago / 正确率——「41 天前」也是账本口气
            "memories": [{"kind": m.get("type"), "quote": m.get("quote")} for m in recalled],
        }

    detail = (today or {}).get("detail") or {}
    gap = (today or {}).get("gap") or {}
    facts = {
        "mode": "normal",
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
        "pet_state": pet_state,
        "modules": [
            {"name": m["module"], "accuracy_pct": brain._pct(m.get("accuracy")), "questions": m.get("questions")}
            for m in (modules or [])
            if (m.get("questions") or 0) >= brain.MIN_SAMPLE and m.get("accuracy") is not None
        ],
        "memories": [_memory_view(m) for m in recalled],
    }
    pool = facts["modules"]
    if pool:
        facts["weakest_module"] = min(pool, key=lambda m: m["accuracy_pct"])["name"]
        facts["strongest_module"] = max(pool, key=lambda m: m["accuracy_pct"])["name"]
    return facts


def _user_numbers(text: str) -> set[int]:
    """他自己说过的数字。他说「60 分」，模型回「60 分」就不该被判成编造。"""
    return {int(n) for n in re.findall(r"\d+", text or "")}


def check_reply(text: str, *, facts: dict, user_text: str = "") -> tuple[bool, str]:
    """上屏前的最后一道。返回 (能说?, 不能说的原因)。原因只进日志，不给用户看。"""
    if not text or not text.strip():
        return False, "空回答"

    banned = [p for p in _BANNED_PHRASES if p in text]
    if banned:
        return False, f"说了堵情绪的话 {banned}"

    # 他难过的时候报数字，是这只仓鼠最不该做的事——实测模型一定会犯，所以硬拦
    if looks_sad(user_text) and re.search(r"\d", text):
        return False, "他正难受，这时候不该报任何数字"

    cn = _CN_AMOUNT.findall(text) or _CN_COUNT.findall(text)
    if cn:
        return False, f"把库里的数字改成了中文写法 {cn}，查不了真伪"

    made_up = [p for p in _BANNED_COMPARE if p in text]
    if made_up:
        return False, f"编了库里没有的比较基线 {made_up}"

    if _THIRD_PERSON.search(text):
        return False, "用了第三人称，角色崩了"

    allowed = set(brain.allowed_numbers(facts)) | _user_numbers(user_text)
    stray = [int(n) for n in re.findall(r"\d+", text) if int(n) not in allowed]
    if stray:
        return False, f"出现事实里没有的数字 {stray}"

    # 提到模块名时，数字必须是这个模块的（防「数字是真的但安错了人」）
    ok, reason = brain.check(text, facts)
    if not ok and "数字" not in reason:
        return False, reason
    return True, ""


def build_messages(user_text: str, *, facts: dict, history: list[dict] | None = None) -> list[dict]:
    """拼请求。system 必须第一条——这是 OpenAI 协议的硬要求，也是人设的地基。"""
    msgs: list[dict] = [{"role": "system", "content": PERSONA}]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content[:200]})
    facts_json = __import__("json").dumps(facts, ensure_ascii=False, separators=(",", ":"))
    msgs.append({
        "role": "user",
        "content": f"事实（JSON，只能用这里面的数字）：{facts_json}\n\n他说：{user_text}",
    })
    return msgs


def retry_messages(messages: list[dict], rejected: str, reason: str) -> list[dict]:
    """被拦下之后，把「哪句不行、为什么」喂回去让它自己改一次。

    比在 system 里再堆一条抽象规则有效得多——模型对「这句具体错在哪」的响应，
    远好于对「你要注意分寸」这种话的响应。只重试一次：第二次还错就是它不会，
    再多试只是烧钱和拖时间。
    """
    return list(messages) + [
        {"role": "assistant", "content": rejected},
        {"role": "user", "content": f"你刚才那句话说错了：{reason}。他这会儿不需要任何数字，"
                                    f"只要一句人能听懂的安慰，20 字以内，只用「你」。"},
    ]


def looks_sad(text: str) -> bool:
    return any(w in (text or "") for w in _SOFT_WORDS)


# 他一边说难受一边问成绩，这时候还是要给数（他真的想知道），不能一律进安慰模式
_ASK_DATA = ("怎么样", "多少", "几道", "几题", "正确率", "成绩", "进度", "错了几", "对了几", "统计", "排名")


def _asks_for_data(text: str) -> bool:
    return any(w in (text or "") for w in _ASK_DATA)


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


def fallback(user_text: str) -> str:
    """模型不在（没网、超时、说了不该说的）时，它还是会说一句人话，只是笨一点。

    这些句子一个数字都不带 —— 笨可以，假不行。
    """
    if any(w in (user_text or "") for w in _MEMORY_WORDS):
        pool = _FALLBACK_ASK_MEMORY
    elif looks_sad(user_text):
        pool = _FALLBACK_SAD
    else:
        pool = _FALLBACK_NORMAL
    # 不随机：同一句话按输入长度轮换，测试可复现
    return pool[len(user_text or "") % len(pool)]
