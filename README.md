# 监督小宠 · 2026.10 苏州黑客松

> AI 学习监督助手：拍一张学习截图 → AI 识别学习数据 → 宠物养成式鼓励反馈
> 参赛时间：2026-10-31 ｜ 代码冻结：18:00（G4）｜ 截止 22:16
> 定位一句话：**卖督学，用陪伴交付（仓鼠五态），靠记忆锁住。别人用规则督你，我们用关系督你。**

---

## 模块地图

| 模块 | 职责 | 状态 | 入口 |
|---|---|---|---|
| A · 前端 | 上传 → 确认卡 → 今日屏 / 记忆屏 / 出分日屏，宠物五态 | ✅ **已接 `/api/today`（缺口行读真数据、断网回落）+ 识别升 r5**（15:28，`1684481`） | [`A-module-frontend/`](A-module-frontend/) |
| **C · AI 学习截图识别** | 识别截图中的学习数据（来源 App / 时长 / 题量 / 正确率 / 模块明细），输出标准 JSON + 鼓励等级 | ✅ **已完成 v1.1-r5，验收通过（10/10 跑批）** | **[`C-module-recognition/`](C-module-recognition/)** |
| B · 后端与状态引擎 | `POST /api/records` 入库、`GET /api/today` 今日状态（含缺口行）、`GET /api/memories`；状态引擎移植自 A 原型并对拍 | ✅ FastAPI + **40 个测试通过**（29 原有 + 4 集成 + 3 对拍 + 4 去重/CORS） | **[`B-module-backend/`](B-module-backend/)** |
| D · 数据与素材 | seed.json（45 天）、路演逐字稿、pitch.pdf、fallback.mp4 | 🔴 进行中 | [`D-module-materials/`](D-module-materials/) |

> 各模块负责人把自己的代码放进对应目录，**只动自己的目录**；跨模块的接口契约以
> [`C-module-recognition/docs/接口草案_C模块_识别结果JSON_v1.1.md`](C-module-recognition/docs/接口草案_C模块_识别结果JSON_v1.1.md)
> 为单一事实源。需求与验收以 [`docs/考公陪跑Agent_PRD_v1.1.md`](docs/考公陪跑Agent_PRD_v1.1.md) 为准。
>
> ⚠️ **现行问题账本**：[`docs/全分支复核_问题汇总_1515.md`](docs/全分支复核_问题汇总_1515.md) —— 15:15 实测版，
> 含 P0/P1/P2 全部未修项、责任人与验收方式。**模块状态以该文件为准，个人自评不算。**

## 分支状态（14:30 全员合并完毕）

四个个人分支已全部合入 `main`，**后续直接提交 main，不再开分支**：

| 分支 | 负责人 | 独有内容 | 处理 |
|---|---|---|---|
| `Taoyu_Chen` | B · 陶宇 | FastAPI 后端 + 状态引擎 + 40 个 pytest + golden 对拍数据 | ✅ 已合并 |
| `Surui_Cao` | A · 曹苏睿 | 仅分支 README 横幅（A 的代码早就在 main） | ✅ 已合并，横幅已删 |
| `nina_chen` | C · Nina | 无（已在 main） | ✅ 已包含 |
| `Yuchen_Zhang` | D · 张宇辰 | 无（已在 main） | ✅ 已包含 |

存档点：`pre-merge-1425`（合并前）、`v0-baseline`、`v1.0.0`、`v1.0.1`

## C 模块 30 秒速览（演示核心路径）

1. 前端引入一个文件：`<script src="C-module-recognition/recognize.js"></script>`
2. 调用：`const result = await window.recognizeScreenshot(file, "demo_zhang")`
3. 返回标准 JSON（接口 v1.1）：学习数据 + 异常警告 + 鼓励等级
4. 永不抛异常、永不返回 null——前端等待态不会被卡死

详细文档 → **[`C-module-recognition/README.md`](C-module-recognition/README.md)**

## A 模块 30 秒速览

```bash
cd A-module-frontend/mock-server && node server.js    # 零依赖，8787 端口，三个接口全实现
```

| 目录 | 解决什么 |
|---|---|
| `A-module-frontend/mock-server/` | B 交付前，前端有后端可接，全链路能跑（B 已交付，现作兜底） |
| `A-module-frontend/seed/` | 45 天自洽演示数据（副本，内容与 D 的 `seed.json` 一致） |
| `A-module-frontend/contract/` | 三接口字段表，B 照此实现 |
| `A-module-frontend/hamster-kit/` | ★ 仓鼠五态素材（CSS + JS + 透明 WebP），全队统一形象入口 |

> **seed 唯一源：`D-module-materials/seed.json`。** 改数据只改这份，再同步到 `A-module-frontend/seed/`、`A-module-frontend/mock-server/data/`；B 的 `B-module-backend/data/seed.json` 用 `D-module-materials/tools/seed_to_backend.py` 重新生成（格式不同，不能直接拷）。

路演主演示图 → `A-module-frontend/test-images/test5.jpg`（10 张里唯一不带 `OLD_SCREENSHOT` 黄条的）

详细文档 → **[`A-module-frontend/README.md`](A-module-frontend/README.md)**

## B 模块 30 秒速览

```bash
cd B-module-backend
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q                          # 40 个测试
.venv/bin/python -m uvicorn app.main:app --port 8000   # 起服务
```

- 环境变量 `HAMSTER_TODAY` 可钉死"今天"，路演回放不随日期漂移
- 状态引擎移植自 A 原型并做了 golden 对拍（`tests/golden.json`），保证前后端算出一个结果

详细文档 → **[`B-module-backend/README.md`](B-module-backend/README.md)**

## 目录结构

```
2026.10_Suzhou_Hackthon/
├── README.md                    ← 本文件（仓库总览）
├── GIT_使用指南.md              ← 四人 Git 工作流 + 回退手册（每人必读，5 分钟）
├── docs/                        ← PRD v1.1 / 验收清单 / 四人任务卡 / 完整方案
├── prototype/                   ← SVG 版原型 Demo（历史参考）
├── A-module-frontend/           ← A：Vue 工程 + 仓鼠素材 + 原型 + mock 服务 + seed + 接口契约
├── B-module-backend/            ← B：FastAPI 后端 + 状态引擎 + 40 个 pytest + golden 对拍
├── C-module-recognition/        ← C：AI 学习截图识别（负责人：Nina）
│   ├── README.md                ← C 模块完整文档（从这里看起）
│   ├── recognize.js             ← 核心交付物：单文件识别模块
│   ├── index.html               ← C 侧演示页
│   ├── phrases.json             ← 鼓励话术（A 定稿 12 条）
│   ├── batch-test.js            ← 跑批测试脚本
│   └── docs/                    ← A⇄C 接口契约（单一事实源）
├── D-module-materials/          ← D：seed / 逐字稿 / pitch
└── handoff-snapshot-1300/       ← 13:00 A+C 联调成果冻结快照（只读基线，谁都不许改）
```

## 版本管理纪律（细则见 GIT_使用指南.md）

- **所有人直接提交 main**（目录隔离 → 零冲突），提交信息格式：`人名: 干了什么`
- **小步提交**：每完成一个功能就 commit，至少每 40 分钟一次——commit 是存档点，不是作品
- **Tag 存档点**（过一道闸门打一个）：`v0-baseline` ✅ → `g2-pass` → `g3-pass` → `g4-frozen` → `final`
- 出问题回退：`git reset --hard g3-pass` 一秒回到存档点；已推送的用 `git revert`
- ❌ **严禁 force push** ｜ ❌ 不要动别人的目录 ｜ ❌ 不要提交密钥和 node_modules

## 参赛信息

- 时间：2026-10-31 ｜ 地点：苏州黑客松
- 阶段：联调（11:30 起）→ G3 五步动线 16:00 → 代码冻结 18:00 → 故障演练 20:00 → 路演 22:16 前
