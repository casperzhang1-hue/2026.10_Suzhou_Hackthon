#!/usr/bin/env python3
"""把 A 的 seed.json（days 结构）转成 B 后端能吃的 data/seed.json（records 结构）。

为什么需要这个：A 的 seed 用 `days: [...]`，B 的 Store 只认 `records: [...]`。
合并分支后两边都在 main 上，但**格式没对齐**——直接拷过去 B 会读到空 records，
今日屏变成「休眠 / 活力 50 / 欠 5 次」，演示当场归零。

用法：
    python D-module-materials/tools/seed_to_backend.py \
        --src A-module-frontend/seed/seed.json \
        --dst B-module-backend/data/seed.json

字段映射：
    days[].date            → records[].event_date
    days[].start_time      → records[].event_time
    days[].duration_minutes→ records[].duration_minutes
    days[].modules         → records[].modules（原样）
    days[].total_questions → records[].total_questions
    days[].accuracy        → records[].accuracy
    memories               → memories（原样）
    user / gap             → 丢弃（B 侧 WEEK_TARGET 常量、单用户）
"""
import argparse
import json
from pathlib import Path


def convert(src: Path) -> dict:
    raw = json.loads(src.read_text(encoding="utf-8"))
    days = raw.get("days") or raw.get("records") or []
    records = []
    for i, d in enumerate(days, start=1):
        if not d.get("date"):
            continue
        records.append({
            "record_id": f"seed_{i:04d}",
            "user_id": "demo_zhang",
            "source_app": d.get("source_app"),
            "event_date": d["date"],
            "event_time": d.get("start_time"),
            "duration_minutes": d.get("duration_minutes"),
            "modules": d.get("modules") or [],
            "total_questions": d.get("total_questions"),
            "accuracy": d.get("accuracy"),
            "manual": False,
            "seed": True,
        })
    out = {"records": records, "memories": raw.get("memories") or []}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="A-module-frontend/seed/seed.json")
    ap.add_argument("--dst", default="B-module-backend/data/seed.json")
    a = ap.parse_args()
    data = convert(Path(a.src))
    dst = Path(a.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    days = sorted({r["event_date"] for r in data["records"]})
    print(f"写入 {dst}：{len(data['records'])} 条记录 / {len(data['memories'])} 条记忆")
    print(f"日期范围 {days[0]} → {days[-1]}（{len(days)} 个有记录的日子）")


if __name__ == "__main__":
    main()
