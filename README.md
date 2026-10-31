# 监督小宠 · 2026.10 苏州黑客松

> AI 学习监督助手：拍一张学习截图 → AI 识别学习数据 → 宠物养成式鼓励反馈
> 参赛时间：2026-10-31 ｜ 代码冻结：18:00（G4）｜ 截止 22:16
> 定位一句话：**卖督学，用陪伴交付（仓鼠五态），靠记忆锁住。别人用规则督你，我们用关系督你。**

---

## 模块地图

| 模块 | 职责 | 状态 | 入口 |
|---|---|---|---|
| A · 前端 | 上传 → 确认卡 → 今日屏 / 记忆屏 / 出分日屏，宠物五态 | ✅ 已入库（13:30 从交付包迁入） | [`A-module-frontend/`](A-module-frontend/) |
| **C · AI 学习截图识别** | 识别截图中的学习数据（来源 App / 时长 / 题量 / 正确率 / 模块明细），输出标准 JSON + 鼓励等级 | ✅ **已完成 v1.1-r5，验收通过（10/10 跑批）** | **[`C-module-recognition/`](C-module-recognition/)** |
| B · 后端与状态引擎 | `/api/records` 入库、`computeDailyState` + 6 测试、`/api/today`（**必须带 gap 缺口行**） | 🔴 进行中（全队唯一阻塞） | [`B-module-backend/`](B-module-backend/) |
| D · 数据与素材 | seed.json（45 天）、路演逐字稿、pitch.pdf、fallback.mp4 | 🔴 进行中 | [`D-module-materials/`](D-module-materials/) |

> 各模块负责人把自己的代码放进对应目录，**只动自己的目录**；跨模块的接口契约以
> [`C-module-recognition/docs/接口草案_C模块_识别结果JSON_v1.1.md`](C-module-recognition/docs/接口草案_C模块_识别结果JSON_v1.1.md)
> 为单一事实源。需求与验收以 [`docs/考公陪跑Agent_PRD_v1.1.md`](docs/考公陪跑Agent_PRD_v1.1.md) 为准。

## C 模块 30 秒速览（演示核心路径）

1. 前端引入一个文件：`<script src="C-module-recognition/recognize.js"></script>`
2. 调用：`const result = await window.recognizeScreenshot(file, "demo_zhang")`
3. 返回标准 JSON（接口 v1.1）：学习数据 + 异常警告 + 鼓励等级
4. 永不抛异常、永不返回 null——前端等待态不会被卡死

详细文档 → **[`C-module-recognition/README.md`](C-module-recognition/README.md)**

## 目录结构

```
2026.10_Suzhou_Hackthon/
├── README.md                    ← 本文件（仓库总览）
├── GIT_使用指南.md              ← 四人 Git 工作流 + 回退手册（每人必读，5 分钟）
├── docs/                        ← PRD v1.1 / 验收清单 / 四人任务卡 / 完整方案
├── prototype/                   ← SVG 版原型 Demo（历史参考）
├── A-module-frontend/           ← A：Vue 工程 + 仓鼠五态素材（hamster-kit）
├── C-module-recognition/        ← C：AI 学习截图识别（负责人：Nina）
├── B-module-backend/            ← B：接口与状态引擎（当前唯一阻塞，README 里有三个 P0）
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
