占位：B 的接口与 computeDailyState 放这里。

三个 P0（照 handoff-snapshot-1300/0_先看我.md 做）：
1. POST /api/records 入库接口
2. 复用 A 原型的 computeDailyState + 6 个测试用例
3. GET /api/today（必须带 gap 缺口行）
