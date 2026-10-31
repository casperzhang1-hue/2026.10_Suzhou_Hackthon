# 考公陪跑 Agent · 2026.10 苏州 Hackathon

> 一只仓鼠，记得住你 41 天前说过「资料分析我一定能拿下」。
> 上传学习截图 → AI 识别 → 你确认 → 仓鼠变化 → 它记得你。

---

## 一、一句话

考公人每天刷题，但**没人记得他 41 天前说过什么**。打卡群只记天数，App 只给冷冰冰的正确率曲线。

我们让一只仓鼠陪你：它会因为你的截图而变化，会在你学太晚时劝你停，会在你承诺过的模块下滑时把那句话翻出来给你看。

---

## 二、仓库怎么分工（每人一个目录）

| 目录 | 负责人 | 内容 | 状态 |
|---|---|---|---|
| **`A/`** | A · 前端/视觉 | 宠物素材、接口契约、mock 服务、seed 数据、原型、Vue 工程 | ✅ **已上传** |
| `B/` | B · 后端 | 三个真接口、状态引擎、入库 | ⏳ 待 B 推 |
| `C/` | C · AI 识别 | recognize.js、phrases、测试集 | ⏳ 待 C 推（r4 已定稿，识别侧已结项） |
| `D/` | D · 产品/路演 | 故事线、seed 数据、录屏、Pitch | ⏳ 待 D 推 |

> **请在自己的目录下操作，别动别人的。** 根目录只放这份 README。

---

## 三、A 已上传了什么

进入 **[`A/README.md`](A/README.md)** 看完整说明。六块：

```
A/
├── pet-assets/     ★ 仓鼠五态素材（CSS + JS + 透明 WebP）—— 全队统一形象入口
├── contract/       ★ 三接口契约 + 4 份示例 JSON —— B 照着实现
├── mock-server/    ★ 零依赖 Node 后端 —— B 交付前，全链路靠它跑通
├── seed/           45 天自洽假数据 —— D 直接用或替换
├── prototype/      四版原型 HTML（单文件版双击即开）—— D 录屏用
├── frontend/       Vue 工程 —— B 接手参考
└── test-images/    C 的 10 张真实截图测试集
```

**A 不只传了素材。** 因为 B 的接口没交、D 的 seed 逾期，光传素材链路照样是断的——所以额外放了 `mock-server/`（能立刻跑起来的后端）和 `seed/`（兜底数据）。

---

## 四、三分钟跑通全链路（B 没交接口也能跑）

```bash
# 1. 起 mock 后端（零依赖，不用 npm install）
cd A/mock-server && node server.js        # http://127.0.0.1:8787

# 2. 起前端
cd A/frontend && npm install && npm run dev   # http://127.0.0.1:5173

# 3. 不想装依赖？
#    双击 A/prototype/仓鼠陪跑_原型_接真数据_单文件版.html
```

**B 交付后**：前端只改 `A/frontend/src/api.js` 里的 `API_BASE` 一个常量，业务代码一行不动。

---

## 五、全队统一：宠物形象是**仓鼠**

任务卡里的「小芽」**已作废**，以本仓库 `A/pet-assets/` 为准。

五态：`元气`(yuanqi) · `踏实`(tashi) · `疲惫`(pibei) · `蔫了`(nianle) · `休眠`(xiumian)

CDN 引用（打 tag 后生效）：

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/casperzhang1-hue/2026.10_Suzhou_Hackthon@v1.0.0/A/pet-assets/hamster.css">
<div class="hamster" data-state="yuanqi" style="--hamster-size:240px"></div>
<script src="https://cdn.jsdelivr.net/gh/casperzhang1-hue/2026.10_Suzhou_Hackthon@v1.0.0/A/pet-assets/hamster.js"></script>
```

---

## 六、时间线（任务卡）

| 时间 | 事项 | 状态 |
|---|---|---|
| ~~23:00~~ | B 出 schema | ⚠️ 逾期，已被 A+C 协商出的契约绕过 |
| ~~24:00~~ | D 出 seed | ⚠️ 逾期，A 已造 45 天兜底版 |
| 16:00 | 五步动线一遍过 | 待 B |
| 18:00 | 视觉统一 + 冻结 | 待 B |
| 23:00 | C 复验 API 额度 | 待 C |

---

## 七、已知风险（写在前面，别等评委问）

- **RK-08 缺口行（16 分，全场最高）**：`GET /api/today` 必须返回 `gap`（本周目标/已完成/欠几次）。`owed=0` 时缺口行会消失，防法失效。契约里已写死。
- **识别结果会波动**：同一张图两次跑可能出 `normal` 和 `excellent`。**没有必成图**，路演话术统一成「AI 识别允许误差，所以确认卡可改」——把缺陷讲成设计。
- **测试图带黄条**：10 张里 8 张超 36 小时阈值触发 `OLD_SCREENSHOT`。路演主演示图用 `test-images/test5.jpg`，或 D 当天现截一张。
