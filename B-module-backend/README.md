# kaogong-hamster-server

考公陪跑 · 仓鼠打卡 的后端与状态引擎（FastAPI）。前端仓库：`kaogong-hamster`。

## 运行

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8000
.venv/bin/python -m pytest -q
```

环境变量：

| 变量 | 作用 |
|---|---|
| `HAMSTER_TODAY` | 钉死"今天"（如 `2026-10-31`），路演回放不随日期漂移 |
| `HAMSTER_DATA_DIR` | 数据目录，默认 `./data` |

数据：优先读 `data/store.json`（运行期写入），否则读 `data/seed.json`（D 交付）。删掉 `store.json` 即回到种子状态。

## 接口

- `POST /api/records` 入库，请求体见前端 `api.js`；`edited_fields` 落库并打日志。返回 `{ok, record_id}`
- `GET /api/today` 今日状态，必含 `gap`（本周缺口）
- `GET /api/memories` 记忆屏条目，来自 seed
- 自动文档：`/docs`

## 状态引擎

`app/engine.py` 是 A 原型 `computeDailyState` 的移植，纯函数。
`tests/golden.json` 由 `tools/gen_golden.mjs` 从原型 JS 生成，pytest 逐字段对拍，保证两边算法一致：

```bash
node tools/gen_golden.mjs <原型.html> > tests/golden.json
```

## 安全

无鉴权，单用户演示用。CORS 只放开 `localhost:5173`，不要直接暴露到公网。
