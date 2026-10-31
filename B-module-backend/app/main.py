import json
import os
import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import (
    db, pet_brain as brain, pet_chat as petchat, pet_llm, pet_memory as petmem,
    pet_persona as persona, pet_vision, service,
)
from .schemas import MemoryIn, RecordIn, SayIn, SeenIn, VerifyIn
from .store import Store

# 必须在读 DATA_DIR 之前把 .env 灌进环境变量，否则 HAMSTER_* 会全部落回默认值
pet_llm.load_env()

DATA_DIR = Path(os.environ.get("HAMSTER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
# 路演用日期钉死（HAMSTER_TODAY=2026-10-31），避免现场回放因日期漂移翻车
_PINNED_TODAY = os.environ.get("HAMSTER_TODAY")

# 模型探活结果缓存 30 秒：页面每次开面板都会问，但没必要每次都等 1.6 秒
_probe_cache: dict = {"at": 0.0, "value": None}
_PROBE_TTL = 30.0


def get_today() -> date:
    return date.fromisoformat(_PINNED_TODAY) if _PINNED_TODAY else date.today()


def create_app(data_dir: Path = DATA_DIR) -> FastAPI:
    app = FastAPI(title="kaogong-hamster-server")
    # 本服务无鉴权（单用户演示）。CORS 仅放开本地任意端口的前端，勿直接暴露到公网。
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    store = Store(data_dir)

    @app.post("/api/records")
    def post_records(body: RecordIn):
        rec = body.record.model_dump(mode="json")
        saved = store.add_record({
            **rec,
            "user_id": body.user_id,
            "edited_fields": body.edited_fields,
            "recognition_ref": body.recognition_ref,
            "confirmed_at": body.confirmed_at.isoformat() if body.confirmed_at else None,
            "manual": body.manual,
        })
        # edited_fields 逐字段留证（PRD 15.1，s2 修正率指标）
        print(f"[edited_fields] {saved['record_id']}: {body.edited_fields}")
        return {"ok": True, "record_id": saved["record_id"]}

    @app.get("/api/today")
    def get_today_state():
        return service.today_view(store.records, get_today())

    @app.get("/api/memories")
    def get_memories(user_id: str = "demo_zhang", with_views: bool = False):
        """它记得的事。

        默认返回原样契约（前端和测试都按 ``{"items": [...]}`` 断言）；
        要给人看「这条是他说的还是我记的旁白」，加 ``?with_views=1``。
        """
        items = store.memories
        out = {"items": items}
        if with_views:
            out["views"] = [persona._memory_view(m) for m in items]
        return out

    @app.post("/api/memories")
    def post_memory(body: MemoryIn):
        """把他的一句话记下来。这是记忆真正的写入口。

        抽不出可记的内容时返回 saved=false，不硬塞一条垃圾进库。
        """
        with store.db.lock:
            modules = db.module_stats(store.db.conn)
        item = petmem.remember(
            store, body.text, user_id=body.user_id,
            known_modules=[m["module"] for m in modules], kind=body.kind,
        )
        if not item:
            return {"ok": True, "saved": False, "reason": "这句话里没有值得记的事"}
        return {"ok": True, "saved": True, "memory": persona._memory_view(item)}

    @app.delete("/api/memories/{memory_id}")
    def delete_memory_api(memory_id: str):
        """忘掉一条。记错的事比忘掉更麻烦——名字记错了它就一直叫错。"""
        gone = store.remove_memory(memory_id)
        return {"ok": True, "deleted": gone, "id": memory_id}

    # ---- 数据库能力（SQL 聚合，不是内存遍历） ----
    @app.get("/api/health")
    def health():
        with store.db.lock:
            info = db.db_overview(store.db.conn)
        return {"ok": True, **info, "today": get_today().isoformat()}

    @app.get("/api/stats")
    def stats():
        with store.db.lock:
            return {
                "modules": db.module_stats(store.db.conn),
                "trend": db.daily_trend(store.db.conn, 7),
            }

    @app.get("/api/pet/chat")
    def pet_chat(intent: str = "today", user_id: str = "demo_zhang"):
        """宠物开口：数字全部来自库，不生成事实。

        intent ∈ today / weak / promise；未知意图返回反问，不硬答。
        """
        today = service.today_view(store.records, get_today())
        with store.db.lock:
            modules = db.module_stats(store.db.conn)
        return petchat.reply(intent, today=today, modules=modules, memories=store.memories)

    @app.get("/api/pet/context")
    def pet_context(intent: str = "today", user_id: str = "demo_zhang"):
        """模型嘴的事实底座：同一份数据，整理成带口径标签的 facts。

        前端拿它去调模型，模型只负责措辞；数字白名单与分句归属校验都在
        pet_brain 里，前端调完自己验一遍，验不过就回落 /api/pet/chat 的模板。
        """
        intent = (intent or "").strip().lower()
        if intent not in brain.INTENTS:
            intent = "today"
        today = service.today_view(store.records, get_today())
        with store.db.lock:
            modules = db.module_stats(store.db.conn)
        return brain.context(intent, today=today, modules=modules, memories=store.memories)

    @app.post("/api/pet/verify")
    def pet_verify(body: VerifyIn):
        """模型答完的复核。校验逻辑只放在后端一份，前端不复制一份 JS——
        两份实现必然漂移，而这种逻辑漂移在路演现场是没法当场发现的。

        不通过时 ok=false，前端回落到模板嘴，用户只会看到一句朴素但真的话。
        """
        today = service.today_view(store.records, get_today())
        with store.db.lock:
            modules = db.module_stats(store.db.conn)
        facts = brain.build_facts(body.intent, today=today, modules=modules, memories=store.memories)
        passed, reason = brain.check(body.text, facts)
        if not passed:
            print(f"[pet_verify] 拒绝模型回答：{reason} | 原文：{body.text[:80]}")
        return {"ok": passed, "reason": reason}

    # ---- 团团开口：接中转站的大模型，人设与数字闸都在后端 ----
    @app.get("/api/pet/llm")
    def pet_llm_status():
        """这一局到底有没有脑子。前端开机问一次，决定面板顶部显示什么。"""
        now = time.time()
        if _probe_cache["value"] is None or now - _probe_cache["at"] > _PROBE_TTL:
            _probe_cache["value"] = pet_llm.probe()
            _probe_cache["at"] = now
        info = dict(_probe_cache["value"])
        # 401 个模型名全回给前端没有任何用处，只留「配置的那个在不在」这一个信息
        info["models"] = [info.get("model")] if info.get("available") else []
        info["persona"] = persona.NAME
        return info

    @app.post("/api/pet/say")
    def pet_say(body: SayIn):
        """他说一句话，团团回一句。

        链路：落库他的话 → 抽记忆 → 召回 → 拼事实包 → 模型措辞 → 洗格式 → 过闸 → 上屏。
        任何一步失败都退到 ``persona.fallback``：宁可笨，不可假。
        返回 200 而不是 5xx —— 前端不需要区分"模型挂了"和"模型说了不该说的"，
        它只需要一句能显示的话和一个来源标签。
        """
        t0 = time.time()
        text = (body.text or "").strip()
        today = service.today_view(store.records, get_today())
        with store.db.lock:
            modules = db.module_stats(store.db.conn)
        known_modules = [m["module"] for m in modules]

        out = {
            "ok": True,
            "persona": persona.NAME,
            "source": "fallback",
            "model": None,
            "guard": {"ok": False, "reason": ""},
            "facts": {},
            "text": "",
            "remembered": None,
            "ms": 0,
        }

        # 历史要在落库**之前**取。反过来的话，他这一句会同时出现在历史和最后的
        # 「他说：……」里，模型一次看到两遍同一个问题——实测这会把它推向复读。
        #
        # 取两份是有原因的：
        # - ``dialogue`` 是库里的完整对话（含 assistant 的每一句），给 recap 用。
        #   他问「我们刚才说了什么」时，它必须看得见自己说过什么，否则只能报账本。
        # - ``history`` 是前端传来的那份，只保证有他的提问，给复读闸和拼请求用。
        dialogue = store.chat_history(user_id=body.user_id, limit=8)
        # 前端传来的那份不一定带它自己的回答（有的版本只发他的提问）。
        # 复读闸和「你上一遍说了什么」都要靠它的原话，少了就判不出重复——
        # 所以没带 assistant 时，以库里那份为准。
        has_reply = any(t.get("role") == "assistant" for t in (body.history or []))
        history = body.history if has_reply else dialogue
        # 出口的复读闸要拿它说过的话比。分两堆：答别的问题时说的（一律不许再出现）、
        # 答同一个问题时说的（只挡逐字照抄）。换了个问题却回同一句，
        # 才是用户截图里骂的那个毛病。
        avoid, avoid_same = persona.split_recent_replies(history, text)

        # 他说的话先落库，再抽一条记忆。顺序不能反：先落库，崩了也不丢他的话。
        if text:
            store.add_chat(user_id=body.user_id, role="user", content=text)
            item = petmem.remember(store, text, user_id=body.user_id, known_modules=known_modules)
            if item:
                out["remembered"] = petmem.view(item)

        facts = persona.build_facts(
            today=today, modules=modules, memories=store.memories, text=text,
            uploads=store.uploads(user_id=body.user_id),
            history=dialogue,
        )
        out["facts"] = facts

        if not text:
            out["text"] = persona.fallback("")
            out["ms"] = int((time.time() - t0) * 1000)
            return out

        try:
            messages = persona.build_messages(text, facts=facts, history=history)
            # 0.65 而不是更活的高温：这只宠物的活儿是「把算好的结论说成人话」，
            # 温度一高它就开始即兴——实测 0.85 时复读上一轮的问题、自己编时长。
            raw = pet_llm.chat(messages, temperature=0.65)
            reply = persona.sanitize(raw)
            # 不在判断模式就不许承诺时长。删掉那个子句，别拦整句——
            # 拦住重试它还会犯，两次过不去就掉兜底，比说错更难看
            if facts.get("mode") != "advice":
                reply = persona.strip_commit(reply)
            passed, reason = persona.check_reply(reply, facts=facts, user_text=text,
                                                 known_modules=known_modules,
                                                 avoid=avoid, avoid_same=avoid_same)

            if not passed:
                # 第一次被拦，把「哪句不行」喂回去让它自己改——只重试一次，
                # 第二次还错说明它不会，再试只是拖时间和烧钱
                print(f"[pet_say] 第一次被拦：{reason} | 原文：{reply[:60]}")
                raw2 = pet_llm.chat(persona.retry_messages(messages, reply, reason), temperature=0.8)
                reply2 = persona.sanitize(raw2)
                if facts.get("mode") != "advice":
                    reply2 = persona.strip_commit(reply2)
                passed2, reason2 = persona.check_reply(reply2, facts=facts, user_text=text,
                                                       known_modules=known_modules,
                                                 avoid=avoid, avoid_same=avoid_same)
                if passed2:
                    reply, passed, reason = reply2, True, ""
                else:
                    reason = f"两次都被拦：{reason} / {reason2}"
        except pet_llm.LLMError as e:
            # 模型侧的问题要留痕：现场如果一半回答都掉到兜底，看日志才知道是限流还是超时
            print(f"[pet_say] 模型不可用：{e}")
            out["guard"]["reason"] = f"模型不可用：{e}"
            out["text"] = persona.fallback(text, facts=facts)
            out["ms"] = int((time.time() - t0) * 1000)
            return out

        if passed:
            out.update({"source": "model", "text": reply, "model": pet_llm.config()["model"]})
            out["guard"] = {"ok": True, "reason": ""}
        else:
            # 说了不该说的：整句丢掉，换一句笨但真的。日志留证据，便于回看。
            print(f"[pet_say] 拦下模型回答：{reason} | 原文：{reply[:80]}")
            out["guard"] = {"ok": False, "reason": reason}
            # 同一件事问了两遍、两次都吐出同一句：这时候兜底要认一句「刚说过啦」，
            # 否则界面上还是两条一模一样的泡泡——正是用户截图里骂的那个样子。
            out["text"] = persona.fallback(text, facts=facts, repeat=bool(reason) and any(
                w in reason for w in ("原样说了一遍", "几乎一样", "整段搬过来")))

        store.add_chat(user_id=body.user_id, role="assistant", content=out["text"],
                       source=out["source"])
        out["ms"] = int((time.time() - t0) * 1000)
        return out

    @app.post("/api/pet/seen")
    def pet_seen(body: SeenIn):
        """他传了一张图，团团真的看一眼，然后说一句它看到了什么。

        这是「连我上传的图片做了什么都不知道」的正面回答：
        看之前不知道，看之后说得出科目、题量、对错、时长——
        而且说的每一个数都能在 ``seen`` 里对上。看不清就说看不清，不猜。

        同一张图（sha256 相同）不重复看、不重复记：重复上传会把时长累加成假数。
        """
        t0 = time.time()
        raw = pet_vision._decode(body.image)
        if not raw:
            return {"ok": False, "reason": "图片解不开", "text": "", "seen": None, "ms": 0}

        sha = pet_vision.fingerprint(raw)
        for old in store.uploads(user_id=body.user_id, limit=20):
            if old.get("image_sha") == sha:
                return {
                    "ok": True, "cached": True, "seen": old.get("seen"),
                    "text": old.get("said") or "这张我刚看过呀。",
                    "model": None, "ms": int((time.time() - t0) * 1000),
                }

        looked = pet_vision.see(raw)
        out = {
            "ok": looked["ok"],
            "cached": False,
            "seen": looked["seen"],
            "model": looked["model"],
            "reason": looked.get("reason", ""),
            "text": "",
            "ms": 0,
        }

        if not looked["ok"]:
            # 看不清就承认看不清。这句是设计过的兜底，不是故障话术。
            out["text"] = "这张我有点看不清呀，你跟我说说今天做了啥？"
            out["ms"] = int((time.time() - t0) * 1000)
            return out

        seen = looked["seen"]
        brief = pet_vision.summary(seen)
        said = ""
        if body.speak:
            facts = {
                "mode": "look",
                "what_i_just_saw": seen,
                "sources": [{"what": brief, "from": "你刚传给我的那张图"}],
            }
            try:
                msgs = [
                    {"role": "system", "content": persona.PERSONA},
                    {"role": "user", "content":
                        "事实（只能用它，一个数都不许改）："
                        + json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
                        + "\n\n他刚给你看了一张学习截图，你刚看完。用一句话说你看到了什么，"
                          "30 字以内，别夸他，别编图里没有的东西。"},
                ]
                raw_reply = pet_llm.chat(msgs, temperature=0.7)
                cand = persona.sanitize(raw_reply)
                ok, why = persona.check_reply(cand, facts=facts, user_text="我传了张截图",
                                              known_modules=[m["name"] for m in seen["modules"]])
                if ok:
                    said = cand
                else:
                    print(f"[pet_seen] 看图这句话被拦：{why} | 原文：{cand[:60]}")
            except pet_llm.LLMError as e:
                print(f"[pet_seen] 看图说话失败：{e}")

        if not said:
            # 兜底直接由抽取结果拼，不带任何形容词——它确实看到了这些
            said = f"这张我看了，{brief}。"

        store.add_upload({
            "id": "up_" + sha[:10],
            "user_id": body.user_id,
            "image_name": body.image_name,
            "image_sha": sha,
            "said": said,
            "seen": {**seen, "summary": brief},
            "record_id": body.record_id,
        })
        out["text"] = said
        out["ms"] = int((time.time() - t0) * 1000)
        return out

    return app


app = create_app()
