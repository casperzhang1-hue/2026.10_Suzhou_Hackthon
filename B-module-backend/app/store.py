"""内存 + JSON 落盘。单用户、单进程。

读取顺序：data/store.json（运行期数据）> data/seed.json（D 交付的种子）> 空。
写入只写 store.json，seed.json 不会被改动；删掉 store.json 即可回到种子状态。
"""
import json
import os
import threading
from pathlib import Path


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.store_path = self.data_dir / "store.json"
        self.seed_path = self.data_dir / "seed.json"
        self._lock = threading.Lock()
        self.records: list[dict] = []
        self.memories: list[dict] = []
        self._load()

    def _load(self):
        for path in (self.store_path, self.seed_path):
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self.records = list(data.get("records", []))
                self.memories = list(data.get("memories", []))
                return

    def add_record(self, rec: dict) -> dict:
        with self._lock:
            rec = {**rec, "record_id": f"rec_{len(self.records) + 1:04d}"}
            self.records.append(rec)
            self._flush()
            return rec

    def _flush(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"records": self.records, "memories": self.memories}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.store_path)  # 原子替换，进程被杀也不会留下半截文件
