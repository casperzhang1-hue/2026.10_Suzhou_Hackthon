"""SQLite 存储层（原 JSON 文件版的等价替换）。

对外接口保持不变：`records` / `memories` / `add_record()`，
上游 service 与 main 无需改动，40 个既有测试即回归网。

读取顺序：SQLite（data/hamster.db）> 首次自动从 data/seed.json 导入
写入：同时落库与内存缓存，保证同一进程内读到的状态即时可见
"""
from datetime import datetime
from pathlib import Path

from .db import Database, import_seed, insert_record, load_memories, load_records

DEDUPE_WINDOW_SECONDS = 120  # 同一张图在窗口内重复提交视为同一条记录


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "hamster.db"
        self.seed_path = self.data_dir / "seed.json"

        self.db = Database(self.db_path)
        self.seeded_rows = import_seed(self.db.conn, self.seed_path)

        self.records: list[dict] = load_records(self.db.conn)
        self.memories: list[dict] = load_memories(self.db.conn)

    @staticmethod
    def _is_duplicate(a: dict, b: dict) -> bool:
        if not (a.get("confirmed_at") and b.get("confirmed_at")):
            return False
        same = all(a.get(k) == b.get(k) for k in ("user_id", "event_date", "modules", "total_questions"))
        gap = abs(datetime.fromisoformat(a["confirmed_at"]) - datetime.fromisoformat(b["confirmed_at"]))
        return same and gap.total_seconds() < DEDUPE_WINDOW_SECONDS

    def _next_id(self) -> str:
        """生成不冲突的 record_id —— 不再覆盖同号旧记录。"""
        n = len(self.records) + 1
        existing = {r.get("record_id") for r in self.records}
        while f"rec_{n:04d}" in existing:
            n += 1
        return f"rec_{n:04d}"

    def add_record(self, rec: dict) -> dict:
        with self.db.lock:
            for old in self.records:
                if self._is_duplicate(old, rec):
                    return old
            rec = {**rec, "record_id": self._next_id()}
            insert_record(self.db.conn, rec)
            self.db.conn.commit()
            self.records.append(rec)
            return rec

    def close(self) -> None:
        try:
            self.db.conn.close()
        except Exception:
            pass
