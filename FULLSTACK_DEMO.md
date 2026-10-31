# 全栈 Demo 说明（前端 + FastAPI + SQLite）

> 在原仓库基础上补齐"后端持久化 + 前端真连后端"这两块，形成一个可独立运行、可演示、可验收的全栈应用。
> 分支：`demo/fullstack`

---

## 1. 三层架构

```
浏览器 (A-module-frontend/index.html · 424KB 单文件)
   │  fetch /api/*
   ├─────────────► FastAPI (B-module-backend · 8000)
   │                   │
   │                   ▼
   │              SQLite (data/hamster.db)
   │                   │
   └── recognize.js ───┘  (C 模块 · 截图识别，云 SDK 调用)
```

| 层 | 技术 | 位置 | 说明 |
|---|---|---|---|
| 前端 | 原生 HTML/CSS/JS 单文件 | `A-module-frontend/index.html` | 无构建、无依赖，双击或静态托管即可 |
| 后端 | FastAPI + Pydantic | `B-module-backend/app/` | 原有状态引擎（`service.py`）与接口契约保持不变 |
| 数据库 | SQLite 3（WAL 模式） | `B-module-backend/data/hamster.db` | 首次启动自动从 `seed.json` 导入 44 天数据 |
| 识别 | recognize.js v1.1-r5 | `C-module-recognition/` | 由前端内联调用，输出标准 JSON |

## 2. 一键启动

```bash
python start_fullstack.py
```

打开 <http://127.0.0.1:8899/index.html>。右上角出现 `SQLite 已连接 · 44 条记录` 即表示全栈打通。

手动启动（等价）：

```bash
# 后端
cd B-module-backend
HAMSTER_TODAY=2026-10-31 .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# 前端（另开一个终端）
cd A-module-frontend && python -m http.server 8899
```

> `HAMSTER_TODAY` 把"今天"钉死，路演回放不会因系统日期漂移。

## 3. 接口

| 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|
| POST | `/api/records` | 确认卡提交入库（含 120 秒内去重） | 原有 |
| GET | `/api/today` | 今日状态：宠物五态、活力、缺口、明细 | 原有 |
| GET | `/api/memories` | 记忆墙 | 原有 |
| GET | `/api/health` | 数据库概况：表、记录数、时间跨度 | **新增** |
| GET | `/api/stats` | 模块正确率 + 近 7 天时长趋势（SQL 聚合） | **新增** |

`/api/stats` 是真 SQL，不是内存遍历：

```sql
SELECT json_extract(m.value,'$.name') AS module,
       COUNT(*), SUM(json_extract(m.value,'$.question_count'))
FROM records r, json_each(r.modules) m
GROUP BY module
```

实测输出：资料分析 36 次 / 955 题 / 62.4%，言语理解 72.9%，判断推理 69.7%，常识判断 68.2%，数量关系 52.0%。

## 4. 数据库

| 表 | 行数（seed 后） | 说明 |
|---|---|---|
| `records` | 44 | 学习记录，按接口契约拆列；`modules` / `edited_fields` / `recognition_ref` 用 JSON 列 |
| `memories` | 3 | 记忆墙；额外保留 `payload` 原始 JSON，保证 `/api/memories` 返回形状不变 |

索引：`event_date`、`(user_id, event_date)`。删除 `hamster.db` 即可回到 seed 起点。

## 5. 相对原仓库的改动

| 文件 | 改动 |
|---|---|
| `B-module-backend/app/db.py` | **新增**：schema、seed 导入、聚合查询 |
| `B-module-backend/app/store.py` | 存储从 JSON 文件换成 SQLite，**对外接口不变**（`records` / `memories` / `add_record`），并修掉 record_id 可能覆盖旧记录的隐患 |
| `B-module-backend/app/main.py` | 新增 `/api/health`、`/api/stats` |
| `B-module-backend/tests/test_api.py` | 2 处断言从读 `store.json` 改为查 SQLite（测试意图不变：数据确实落盘、去重只存一条） |
| `A-module-frontend/原型/…单文件版.html` | 新增第 5 节"后端对接"：启动探测、`/api/today` 驱动 UI、确认入库 `POST /api/records`、断线回落本地演示数据 |
| `A-module-frontend/index.html`<br>`app/public/prototype.html` | 由 `sync_frontend.py` 从上面的源文件自动生成，勿手改 |
| `start_fullstack.py` | **新增**：一键启动 |

## 6. 已验证（2026-10-31 实测）

| 项 | 结果 |
|---|---|
| 后端回归 | `pytest` **40 passed**（换 SQLite 后全绿，无行为变化） |
| 数据库自举 | 空库启动自动导入 44 条记录 / 3 条记忆 / 2549 分钟 / 2026-09-17 ~ 10-30 |
| 前端读链路 | 页面加载后徽章显示 `SQLite 已连接 · 44 条记录`；写入一条记录后**重载页面**，缺口 2→1、提示文案切换为"今天已记下" |
| 前端写链路 | 用 CDP 驱动真实页面调用 `postRecordAndRefresh()`：数据库 45→46 条，UI 活力 62→81，`has_record` false→true |
| SQL 聚合 | `/api/stats` 返回 5 个模块正确率 + 7 天趋势 |
| 断线降级 | 后端未启动时页面正常渲染，使用本地演示数据（不白屏） |

## 7. 演示动线

1. 打开首页 —— 宠物「踏实」，本周欠 2 次
2. 点「传今天的截图」，选 `C-module-recognition/test/test12_粉笔_1031_判断推理.jpg`
3. C 模块真识别（约 3-8 秒）→ 确认卡显示识别字段
4. 点「没问题，记下」→ 写入 SQLite，今日屏刷新，缺口 2→1
5. 右上角徽章记录数 +1，即"数据真的进库了"
6. 打开 <http://127.0.0.1:8000/api/health> 或 `/api/stats` 给评委看数据库
