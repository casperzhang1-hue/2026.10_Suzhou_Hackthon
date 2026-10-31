# 监督小宠 · 2026.10 苏州黑客松

> AI 学习监督助手：拍一张学习截图 → AI 识别学习数据 → 宠物养成式鼓励反馈
> 参赛时间：2026-10-31 ｜ 代码冻结：18:00（G4）

---

## 模块地图

| 模块 | 职责 | 状态 | 入口 |
|---|---|---|---|
| A · 前端 | 上传 → 确认卡 → 今日屏 / 记忆屏 / 出分日屏，宠物五态 | 联调中 | `A-module-frontend/`（A 推送后可见） |
| B · 后端与状态引擎 | `POST /api/records` 入库、`GET /api/today` 今日状态（含缺口行）、`GET /api/memories`；状态引擎移植自 A 原型并对拍 | ✅ 接口与 29 个测试通过，待接 seed | **[`B-module-backend/`](B-module-backend/)** |
| **C · AI 学习截图识别** | 识别截图中的学习数据（来源 App / 时长 / 题量 / 正确率 / 模块明细），输出标准 JSON + 鼓励等级 | ✅ **已完成 v1.1-r5，验收通过** | **[`C-module-recognition/`](C-module-recognition/)** |
| D · 数据与素材 | 测试截图、话术素材、演示物料 | 进行中 | `D-module-materials/`（D 推送后可见） |

> 各模块负责人把自己的代码放进对应目录，**只动自己的目录**；跨模块的接口契约以
> [`C-module-recognition/docs/接口草案_C模块_识别结果JSON_v1.1.md`](C-module-recognition/docs/接口草案_C模块_识别结果JSON_v1.1.md)
> 为单一事实源。

## C 模块 30 秒速览（演示核心路径）

1. 前端引入一个文件：`<script src="C-module-recognition/recognize.js"></script>`
2. 调用：`const result = await window.recognizeScreenshot(file, "demo_zhang")`
3. 返回标准 JSON（接口 v1.1）：学习数据 + 异常警告 + 鼓励等级
4. 永不抛异常、永不返回 null——前端等待态不会被卡死

详细文档 → **[`C-module-recognition/README.md`](C-module-recognition/README.md)**

## 目录结构

```
2026.10_Suzhou_Hackthon/
├── README.md                     ← 本文件（仓库总览）
├── B-module-backend/             ← B 模块：后端与状态引擎（FastAPI，负责人：Taoyu）
└── C-module-recognition/         ← C 模块：AI 学习截图识别（负责人：Nina）
    ├── README.md                 ← C 模块完整文档（从这里看起）
    ├── recognize.js              ← 核心交付物：单文件识别模块
    ├── index.html                ← C 侧演示页
    ├── encouragement.json        ← 演示页话术库
    ├── phrases.json              ← 鼓励话术（A 定稿 12 条）
    ├── batch-test.js             ← 跑批测试脚本
    └── docs/
        └── 接口草案_C模块_识别结果JSON_v1.1.md   ← A⇄C 接口契约（单一事实源）
```

## 参赛信息

- 时间：2026-10-31
- 地点：苏州黑客松
- 阶段：联调（11:30 起）→ 代码冻结 18:00 → 路演
