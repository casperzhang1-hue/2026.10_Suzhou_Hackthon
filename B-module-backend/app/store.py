"""SQLite 存储层（原 JSON 文件版的等价替换）。

对外接口保持不变：`records` / `memories` / `add_record()`，
上游 service 与 main 无需改动，40 个既有测试即回归网。

读取顺序：SQLite（data/hamster.db）> 首次自动从 data/seed.json 导入
写入：同时落库与内存缓存，保证同一进程内读到的状态即时可见
"""
from datetime import datetime
from pathlib import Path

from .db import (
    Database, append_chat, delete_memory, import_seed, insert_memory, insert_record,
    insert_upload, load_chat, load_memories, load_records, load_uploads,
)

DEDUPE_WINDOW_SECONDS = 120  # 同一张图在窗口内重复提交视为同一条记录

# 跨窗口的同一张图：识别出来的 event_time 来自图本身，同一个时刻、同样的题量、
# 同样的模块、同样的正确率，只可能是同一张图被传了两遍。
# 只靠 120 秒窗口挡不住——实测今天同一张粉笔截图被传了 4 次，
# 分别落在 11:59 / 12:08 / 12:45 / 13:18，于是「今天 154 分钟」这个数是假的，
# 而宠物只是老老实实念了这个假数。



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

    @staticmethod
    def _same_image(a: dict, b: dict) -> bool:
        """同一张图 = 同一个指纹。指纹优先于时间窗口。

        120 秒窗口挡不住真实的重复上传：实测今天同一张粉笔截图被传了 4 次，
        落在 11:59 / 12:08 / 12:45 / 13:18，于是「今天 154 分钟」这个数是假的，
        而宠物只是老老实实念了这个假数——它没撒谎，它的账本是假的。
        时间窗口不能放宽（同样一组题隔几小时再做一遍是正常的），
        所以只能靠图本身的指纹来判。
        """
        ha = (a.get("recognition_ref") or {}).get("image_sha")
        hb = (b.get("recognition_ref") or {}).get("image_sha")
        return bool(ha) and ha == hb

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
                if self._is_duplicate(old, rec) or self._same_image(old, rec):
                    return old
            rec = {**rec, "record_id": self._next_id()}
            insert_record(self.db.conn, rec)
            self.db.conn.commit()
            self.records.append(rec)
            return rec

    # ---- 记忆 ----

    def add_memory(self, item: dict) -> dict:
        with self.db.lock:
            insert_memory(self.db.conn, item)
            self.memories.append(item)
            return item

    def remove_memory(self, memory_id: str) -> bool:
        """删一条。内存里那份也要同步删，否则它这一轮还「记得」。"""
        with self.db.lock:
            n = delete_memory(self.db.conn, memory_id)
            if n:
                self.memories = [m for m in self.memories if m.get("id") != memory_id]
            return bool(n)

    # ---- 对话 ----

    def add_chat(self, *, user_id: str, role: str, content: str, source: str | None = None) -> None:
        with self.db.lock:
            append_chat(self.db.conn, user_id=user_id, role=role, content=content, source=source)

    def chat_history(self, *, user_id: str = "demo_zhang", limit: int = 10) -> list[dict]:
        with self.db.lock:
            return load_chat(self.db.conn, user_id=user_id, limit=limit)

    # ---- 他给我看的图 ----

    def add_upload(self, item: dict) -> dict:
        with self.db.lock:
            insert_upload(self.db.conn, item)
            return item

    def uploads(self, *, user_id: str = "demo_zhang", limit: int = 3) -> list[dict]:
        with self.db.lock:
            return load_uploads(self.db.conn, user_id=user_id, limit=limit)

    def close(self) -> None:
        try:
            self.db.conn.close()
        except Exception:
            pass
