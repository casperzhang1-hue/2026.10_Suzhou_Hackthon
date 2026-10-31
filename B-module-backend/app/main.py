import os
import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, pet_brain as brain, pet_chat as petchat, pet_llm, pet_persona as persona, service
from .schemas import RecordIn, SayIn, VerifyIn
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
    def get_memories():
        return {"items": store.memories}

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

        链路：召回记忆 → 拼事实包 → 模型措辞 → 洗格式 → 过闸 → 上屏。
        任何一步失败都退到 ``persona.fallback``：宁可笨，不可假。
        返回 200 而不是 5xx —— 前端不需要区分"模型挂了"和"模型说了不该说的"，
        它只需要一句能显示的话和一个来源标签。
        """
        t0 = time.time()
        text = (body.text or "").strip()
        today = service.today_view(store.records, get_today())
        with store.db.lock:
            modules = db.module_stats(store.db.conn)

        out = {
            "ok": True,
            "persona": persona.NAME,
            "source": "fallback",
            "model": None,
            "guard": {"ok": False, "reason": ""},
            "facts": {},
            "text": "",
            "ms": 0,
        }
        facts = persona.build_facts(
            today=today, modules=modules, memories=store.memories, text=text
        )
        out["facts"] = facts

        if not text:
            out["text"] = persona.fallback("")
            out["ms"] = int((time.time() - t0) * 1000)
            return out

        try:
            messages = persona.build_messages(text, facts=facts, history=body.history)
            raw = pet_llm.chat(messages, temperature=0.85)
            reply = persona.sanitize(raw)
            passed, reason = persona.check_reply(reply, facts=facts, user_text=text)

            if not passed:
                # 第一次被拦，把「哪句不行」喂回去让它自己改——只重试一次，
                # 第二次还错说明它不会，再试只是拖时间和烧钱
                print(f"[pet_say] 第一次被拦：{reason} | 原文：{reply[:60]}")
                raw2 = pet_llm.chat(persona.retry_messages(messages, reply, reason), temperature=0.95)
                reply2 = persona.sanitize(raw2)
                passed2, reason2 = persona.check_reply(reply2, facts=facts, user_text=text)
                if passed2:
                    reply, passed, reason = reply2, True, ""
                else:
                    reason = f"两次都被拦：{reason} / {reason2}"
        except pet_llm.LLMError as e:
            # 模型侧的问题要留痕：现场如果一半回答都掉到兜底，看日志才知道是限流还是超时
            print(f"[pet_say] 模型不可用：{e}")
            out["guard"]["reason"] = f"模型不可用：{e}"
            out["text"] = persona.fallback(text)
            out["ms"] = int((time.time() - t0) * 1000)
            return out

        if passed:
            out.update({"source": "model", "text": reply, "model": pet_llm.config()["model"]})
            out["guard"] = {"ok": True, "reason": ""}
        else:
            # 说了不该说的：整句丢掉，换一句笨但真的。日志留证据，便于回看。
            print(f"[pet_say] 拦下模型回答：{reason} | 原文：{reply[:80]}")
            out["guard"] = {"ok": False, "reason": reason}
            out["text"] = persona.fallback(text)
        out["ms"] = int((time.time() - t0) * 1000)
        return out

    return app


app = create_app()
