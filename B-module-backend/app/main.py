import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, pet_brain as brain, pet_chat as petchat, service
from .schemas import RecordIn, VerifyIn
from .store import Store

DATA_DIR = Path(os.environ.get("HAMSTER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
# 路演用日期钉死（HAMSTER_TODAY=2026-10-31），避免现场回放因日期漂移翻车
_PINNED_TODAY = os.environ.get("HAMSTER_TODAY")


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

    return app


app = create_app()
