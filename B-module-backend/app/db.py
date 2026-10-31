"""SQLite 持久层：建表、seed 导入、聚合查询。

设计要点
- 单文件数据库（data/hamster.db），零外部依赖，适合演示与本地部署。
- 记录表按 API 契约字段拆列，modules / edited_fields / recognition_ref 用 JSON 列存。
- 首次启动且 records 表为空时，自动从 seed.json 导入 45 天数据（幂等）。
- 查询走 SQL，不走 Python 遍历，方便后续加统计/报表。
"""
import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    record_id        TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL DEFAULT 'demo_zhang',
    event_date       TEXT,
    event_time       TEXT,
    duration_minutes INTEGER,
    source_app       TEXT,
    modules          TEXT NOT NULL DEFAULT '[]',
    total_questions  INTEGER,
    accuracy         REAL,
    edited_fields    TEXT NOT NULL DEFAULT '[]',
    recognition_ref  TEXT,
    confirmed_at     TEXT,
    manual           INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_records_date ON records(event_date);
CREATE INDEX IF NOT EXISTS idx_records_user ON records(user_id, event_date);

CREATE TABLE IF NOT EXISTS memories (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL DEFAULT 'demo_zhang',
    type          TEXT,
    days_ago      INTEGER,
    said_at       TEXT,
    quote         TEXT,
    module        TEXT,
    then_accuracy REAL,
    week_accuracy REAL,
    question      TEXT,
    payload       TEXT
);

-- 他说过的每一句话都落库。之前只存在页面内存里，刷新就没，
-- 于是「记得」只能靠 prompt 里那三条种子撑着。
CREATE TABLE IF NOT EXISTS chat_turns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL DEFAULT 'demo_zhang',
    role       TEXT NOT NULL,              -- user / assistant
    content    TEXT NOT NULL,
    source     TEXT,                       -- model / fallback / template
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_turns(user_id, id);

-- 他给我看的每一张图。宠物说过什么、认出了什么，都在这里留证。
-- 没有这张表，它就只能"猜"他刚做了什么——也就是这次翻车的直接原因。
CREATE TABLE IF NOT EXISTS uploads (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT 'demo_zhang',
    image_name TEXT,
    image_sha  TEXT,
    said       TEXT,                       -- 它看完说的那一句
    seen       TEXT,                       -- 它从图里读到的结构化内容（JSON）
    record_id  TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_uploads_user ON uploads(user_id, created_at);
"""

RECORD_COLUMNS = (
    "record_id", "user_id", "event_date", "event_time", "duration_minutes",
    "source_app", "modules", "total_questions", "accuracy",
    "edited_fields", "recognition_ref", "confirmed_at", "manual",
)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _as_json(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def row_to_record(row: sqlite3.Row) -> dict:
    rec = dict(row)
    rec.pop("created_at", None)
    rec["modules"] = json.loads(rec.get("modules") or "[]")
    rec["edited_fields"] = json.loads(rec.get("edited_fields") or "[]")
    ref = rec.get("recognition_ref")
    rec["recognition_ref"] = json.loads(ref) if ref else None
    rec["manual"] = bool(rec.get("manual"))
    return rec


def insert_record(conn: sqlite3.Connection, rec: dict) -> None:
    values = (
        rec.get("record_id"),
        rec.get("user_id") or "demo_zhang",
        rec.get("event_date"),
        rec.get("event_time"),
        rec.get("duration_minutes"),
        rec.get("source_app"),
        _as_json(rec.get("modules") or []),
        rec.get("total_questions"),
        rec.get("accuracy"),
        _as_json(rec.get("edited_fields") or []),
        _as_json(rec.get("recognition_ref")),
        rec.get("confirmed_at"),
        1 if rec.get("manual") else 0,
    )
    placeholders = ",".join("?" * len(values))
    conn.execute(
        f"INSERT OR REPLACE INTO records ({','.join(RECORD_COLUMNS)}) VALUES ({placeholders})",
        values,
    )


def load_records(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM records ORDER BY event_date, event_time, record_id"
    ).fetchall()
    return [row_to_record(r) for r in rows]


def load_memories(conn: sqlite3.Connection) -> list[dict]:
    """按原始 JSON 形状还原（不做字段拍平），保证 /api/memories 的返回契约不变。

    拆列只是为了可查询（按 module 检索），不改变 API 暴露的结构。
    """
    rows = conn.execute("SELECT * FROM memories ORDER BY days_ago DESC").fetchall()
    items = []
    for r in rows:
        raw = r["payload"]
        if raw:
            items.append(json.loads(raw))
            continue
        item = {k: v for k, v in dict(r).items() if k not in ("payload", "user_id") and v is not None}
        items.append(item)
    return items


def insert_memory(conn: sqlite3.Connection, item: dict) -> None:
    """写一条记忆。payload 存整条 JSON，拆出来的列只为查询方便。

    ``days_ago`` 由调用方给（0 = 今天说的）。缺了它，41 天前和刚才对它是一回事。
    """
    conn.execute(
        "INSERT OR REPLACE INTO memories (id,user_id,type,days_ago,said_at,quote,module,"
        "then_accuracy,week_accuracy,question,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            item.get("id"),
            item.get("user_id") or "demo_zhang",
            item.get("type"),
            item.get("days_ago"),
            item.get("said_at"),
            item.get("quote"),
            item.get("module"),
            item.get("then_accuracy"),
            item.get("week_accuracy"),
            item.get("question"),
            json.dumps(item, ensure_ascii=False),
        ),
    )
    conn.commit()


def append_chat(conn: sqlite3.Connection, *, user_id: str, role: str,
                content: str, source: str | None = None) -> None:
    conn.execute(
        "INSERT INTO chat_turns (user_id, role, content, source) VALUES (?,?,?,?)",
        (user_id or "demo_zhang", role, content or "", source),
    )
    conn.commit()


def load_chat(conn: sqlite3.Connection, *, user_id: str = "demo_zhang", limit: int = 12) -> list[dict]:
    """最近几轮对话，按时间正序返回（越靠后越新），直接可以喂给模型。"""
    rows = conn.execute(
        "SELECT role, content FROM chat_turns WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id or "demo_zhang", limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def insert_upload(conn: sqlite3.Connection, item: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO uploads (id,user_id,image_name,image_sha,said,seen,record_id,created_at)"
        " VALUES (?,?,?,?,?,?,?,COALESCE(?,datetime('now')))",
        (
            item.get("id"),
            item.get("user_id") or "demo_zhang",
            item.get("image_name"),
            item.get("image_sha"),
            item.get("said"),
            _as_json(item.get("seen")),
            item.get("record_id"),
            item.get("created_at"),
        ),
    )
    conn.commit()


def load_uploads(conn: sqlite3.Connection, *, user_id: str = "demo_zhang", limit: int = 5) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM uploads WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (user_id or "demo_zhang", limit),
    ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["seen"] = json.loads(item["seen"]) if item.get("seen") else None
        out.append(item)
    return out


def import_seed(conn: sqlite3.Connection, seed_path: Path) -> int:
    """records 表为空时导入 seed.json；已有数据则跳过（幂等）。"""
    if not seed_path.exists():
        return 0
    count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    if count:
        return 0
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    for i, rec in enumerate(data.get("records", []), start=1):
        rec.setdefault("record_id", f"rec_{i:04d}")
        rec.setdefault("user_id", "demo_zhang")
        insert_record(conn, rec)
    for i, mem in enumerate(data.get("memories", []), start=1):
        conn.execute(
            "INSERT OR REPLACE INTO memories (id,user_id,type,days_ago,said_at,quote,module,"
            "then_accuracy,week_accuracy,question,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                mem.get("id") or f"mem_{i:03d}",
                mem.get("user_id", "demo_zhang"),
                mem.get("type"),
                mem.get("days_ago"),
                mem.get("said_at"),
                mem.get("quote"),
                # 兼容两种写法：拍平的 module/week_accuracy，或嵌套的 reality{}
                (mem.get("reality") or {}).get("module", mem.get("module")),
                mem.get("then_accuracy"),
                (mem.get("reality") or {}).get("week_accuracy", mem.get("week_accuracy")),
                mem.get("question"),
                json.dumps(mem, ensure_ascii=False),
            ),
        )
    conn.commit()
    return len(data.get("records", []))


def module_stats(conn: sqlite3.Connection) -> list[dict]:
    """按模块聚合：直接用 SQL 拆 JSON 列，证明这里是真数据库查询而非字典遍历。"""
    rows = conn.execute(
        """
        SELECT
            json_extract(m.value, '$.name')              AS module,
            COUNT(*)                                     AS sessions,
            SUM(json_extract(m.value, '$.question_count')) AS questions,
            SUM(json_extract(m.value, '$.correct_count'))  AS correct
        FROM records r, json_each(r.modules) m
        WHERE json_extract(m.value, '$.name') IS NOT NULL
        GROUP BY module
        HAVING questions > 0
        ORDER BY questions DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        questions = r["questions"] or 0
        correct = r["correct"] or 0
        out.append({
            "module": r["module"],
            "sessions": r["sessions"],
            "questions": questions,
            "accuracy": round(correct / questions, 3) if questions else None,
        })
    return out


def daily_trend(conn: sqlite3.Connection, limit: int = 7) -> list[dict]:
    rows = conn.execute(
        """
        SELECT event_date AS date,
               SUM(COALESCE(duration_minutes,0)) AS minutes,
               SUM(COALESCE(total_questions,0))  AS questions
        FROM records
        WHERE event_date IS NOT NULL
        GROUP BY event_date
        ORDER BY event_date DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def db_overview(conn: sqlite3.Connection) -> dict:
    records = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    days = conn.execute(
        "SELECT COUNT(DISTINCT event_date) FROM records WHERE event_date IS NOT NULL"
    ).fetchone()[0]
    minutes = conn.execute(
        "SELECT COALESCE(SUM(duration_minutes),0) FROM records"
    ).fetchone()[0]
    first = conn.execute("SELECT MIN(event_date) FROM records").fetchone()[0]
    last = conn.execute("SELECT MAX(event_date) FROM records").fetchone()[0]
    return {
        "engine": "sqlite3",
        "tables": ["records", "memories", "chat_turns", "uploads"],
        "records": records,
        "memories": memories,
        "days": days,
        "total_minutes": minutes,
        "range": [first, last],
    }


class Database:
    """连接 + 锁的薄封装，供 Store 使用。"""

    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.conn = connect(self.path)
        self.lock = threading.Lock()
        init_schema(self.conn)
