import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import service
from .schemas import RecordIn
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

    return app


app = create_app()
