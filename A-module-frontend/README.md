# A 模块 · 前端与视觉

> 负责人：A（曹苏睿）｜ 2026-10-31 更新 ｜ 宠物形象：**仓鼠**（任务卡的「小芽」已作废）
> 一句话：**让 B / C / D 不用找 A 要文件，全链路就能跑通**

---

## 一、目录结构

```
A-module-frontend/
├── app/                 Vue 工程（npm install && npm run dev）
│   ├── src/             App.vue、api.js、五屏组件、话术、仓鼠五态图
│   └── public/
│       └── recognize.js C 的识别脚本（v1.1-r5）
│
├── hamster-kit/         ★ 仓鼠五态素材，全队统一形象入口
│   ├── hamster.css      五态切图 + 微动效 + 预加载
│   ├── hamster.js       HamsterKit（level → 态）
│   ├── index.html       素材预览页
│   └── img/             五态 512 WebP（透明底）+ 解锁件 4 张
│
├── 原型/                四版原型 HTML + 构建脚本
│   └── 仓鼠陪跑_原型_接真数据_单文件版.html   ★ 双击即开，录屏从这里出
│
├── mock-server/         ★ 本次新增：零依赖 Node 后端
│   ├── server.js        node:http，8787 端口，三个接口全实现
│   ├── engine.js        状态引擎（从原型原样移植）
│   └── data/seed.json   45 天假数据
│
├── seed/                ★ 本次新增：给 D 的假数据
│   ├── make_seed.py     生成脚本，改完重跑会同步到 mock-server
│   └── seed.json        45 天，自洽校验通过
│
├── contract/            ★ 本次新增：三接口契约
│   ├── README.md        字段表 + 判定规则
│   ├── records.request.example.json
│   ├── today.response.example.json
│   ├── memories.response.example.json
│   └── recognition.response.example.json
│
└── test-images/         ★ 本次新增：C 的 10 张真实截图
    └── test5.jpg        唯一不带黄条的图（路演主演示图）
```

---

## 二、本次新增了什么（13:30 之后）

B 的三个接口没交、D 的 seed 逾期，光有素材链路照样是断的。所以补了三样**能让链路立刻跑起来的东西**：

| 新增 | 解决什么 |
|---|---|
| `mock-server/` | B 交付前，前端有后端可接，全链路能跑 |
| `seed/` | D 逾期，A 先造 45 天兜底数据，D 来了直接替换 |
| `contract/` | B 有明确的字段表照着实现，不用猜 |

---

## 二·补、15:30 本次改动（任务一 + 任务二）

依据 D 的 `docs/合并后复评_1510.md`，A 被点了 5 条。本次修掉其中 3 条 P0/P1：

| # | 问题 | 处理 |
|---|---|---|
| A-1 🔴 | 缺口行硬编码：按话术档位猜「本周欠 2 次」，**根本没读数据** | ✅ 删掉硬编码，改读 `today.gap.owed` |
| A-2 🔴 | `fetchToday()` 写好了但 `App.vue` 里 0 次调用，等于没插电 | ✅ `onMounted` 真的发起调用，入库后立刻刷新 |
| A-5 🔴 | `API_BASE` 指向我自己的 mock（8787），不是 B 的服务 | ✅ 改自动探测 `8000 → 8015 → 8787` |
| A-3 🟡 | 原型内联的是 C 的 r3，C 已到 r5 | ✅ 覆盖 `app/public/recognize.js`，重建两版原型 |
| A-4 🟡 | 工程缺记忆屏 / 出分日屏 | ⏸ 按 D 判断不补（原型里已有），已 `npm run build` 通过 |

**改动文件**：

```
app/src/api.js                        后端地址自动探测 + 1.5s 超时 + 离线缓存回落
app/src/App.vue                       进页面拉 /api/today，顶部显示后端连通状态
app/src/components/TodayScreen.vue    缺口行读数据；形态优先用后端 pet_state
app/public/recognize.js               C 的 v1.1-r5
原型/仓鼠陪跑_原型_接真数据版.html        重建（内联 r5）
原型/仓鼠陪跑_原型_接真数据_单文件版.html   重建（内联 r5，408KB，双击即开）
原型/build_realdata.py                版本标记 r3 → r5
```

**实测**（本机真跑）：

- `GET /api/today` 真实响应 `gap.owed = 1` → 界面渲染 `本周 4/5，还欠 1 次` ✅
- 后端没给 `gap` → 显示 `本周缺口 —`（**不编数字**）✅
- 完全拉不到 → 用上次缓存 + 灰色「离线 · 上次同步」标记 ✅
- r5 识别 test5：`excellent · 粉笔 · 115分 · 135题 · 81% · 6.8s`，与 r4 一致无退化 ✅
- `npm run build` 通过（27 modules，1.1s）✅

**给 B 的完整对接说明 → [`docs/给B的对接材料.md`](docs/给B的对接材料.md)**

---

## 三、每个人从这里拿什么

### 👤 B（后端）—— 拿 `contract/` + `mock-server/`

```bash
cd A-module-frontend/mock-server && node server.js   # 先看它怎么返回，照着实现真后端
```

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/records` | POST | 确认后入库，返回最新 today |
| `/api/today` | GET | 今日屏：宠物态、活力值、用户态、话术档、**缺口行** |
| `/api/memories` | GET | 记忆屏：承诺/事件列表 |

⚠️ 两条硬要求：

- **`engine.js` 直接复用，别重写** —— 它是从原型 761–805 行原样移植的。否则前端一套算法、后端一套算法，现场两套结果不一致。
- **`gap` 字段不能省** —— RK-08 是全场最高风险（16 分）。`owed = 0` 时缺口行消失，防法失效。

### 👤 C（识别）—— 拿 `contract/recognition.response.example.json`

r5 已全量接入（`app/public/recognize.js`），这里只是留档。识别侧已结项，守好 16:00 / 18:00 / 23:00 三个时间点。

### 👤 D（产品/路演）—— 拿 `seed/` + `原型/` + `test-images/`

- `seed/seed.json` 已按故事线造好（D8 断签 / D15 凌晨崩溃 / D22 承诺 / 本周 48%），**直接用或改完重跑 `make_seed.py`**
- `原型/仓鼠陪跑_原型_接真数据_单文件版.html` 双击即开，录屏素材从这儿出
- `test-images/test5.jpg` 是唯一不带 `OLD_SCREENSHOT` 黄条的图，**路演主演示图用它**
- ⚠️ **任务卡内部矛盾**：写的是「30 天假数据」，但记忆屏要引用「41 天前说的话」——30 天覆盖不到 41 天前，记忆屏会自相矛盾。**已拉到 45 天**，请确认口径

---

## 四、CDN 调用（素材统一入口）

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/casperzhang1-hue/2026.10_Suzhou_Hackthon@v1.0.1/A-module-frontend/hamster-kit/hamster.css">
<div class="hamster" data-state="yuanqi" style="--hamster-size:240px"></div>
<script src="https://cdn.jsdelivr.net/gh/casperzhang1-hue/2026.10_Suzhou_Hackthon@v1.0.1/A-module-frontend/hamster-kit/hamster.js"></script>
```

不用 JS 也行：`el.dataset.state = 'pibei'` 一行切态。

⚠️ 三个坑：

1. 仓库必须 **public**，jsDelivr 才读得到（当前 ✅ public）
2. **锁 tag 别用 `@main`** —— CDN 缓存最长 7 天
3. CSS 和 `img/` 必须同层（CSS 里是相对路径 `img/`）

---

## 五、本地跑通全链路（三步）

```bash
# 1. 起后端（二选一）
#    B 的真后端（已交付）：
cd ../../B-module-backend && HAMSTER_TODAY=2026-10-31 uvicorn app.main:app --port 8000
#    A 的 mock 兜底（B 没起时用，零依赖不用 npm install）：
cd A-module-frontend/mock-server && node server.js      # http://127.0.0.1:8787

# 2. 起前端 —— 必须是 5173，B 的 CORS 只放了这个端口
cd A-module-frontend/app && npm install && npm run dev   # http://127.0.0.1:5173

# 3. 接真识别
#    把 src/api.js 的 USE_MOCK 改成 false
```

后端地址**不用手填**：`api.js` 会按 `8000 → 8015 → 8787` 自动探测第一个通的，
顶部会显示「后端 http://127.0.0.1:xxxx 已连通」。想固定就在 `.env` 写 `VITE_API_BASE`。

**不想装依赖？** 直接双击 `原型/仓鼠陪跑_原型_接真数据_单文件版.html`，图片和 recognize.js 都已内嵌。

---

## 六、已实测通过的两个关键场景（mock server 真跑）

| 场景 | 输入 | 输出 |
|---|---|---|
| 常规好图 | 115 分钟 / 81% / 20:30 | `vigour`（元气）+ `excellent` + 用户态「稳」 |
| **熬夜（最值钱那格）** | 210 分钟 / 22:40 开始 | **`tired`（疲惫）+ `过载` + `low`** → 仓鼠说「今天别学了」 |

第二行是任务卡里「全场最值钱的一格」——路演一定要演到，现在有数据支撑了。

---

## 七、seed 数据的自洽校验（防评委抓）

```
本周资料分析: 36/75 = 48.0%           ← 记忆屏引用
41 天前（2026-09-20）: 22/30 = 73.3%  ← 对比强烈
承诺日距今: 41 天                      ← 记忆屏引用
本周已学 3 天 / 目标 5 天 → 欠 2 次     ← 今日屏缺口行（RK-08）
```

改 `seed/make_seed.py` 后重跑，断言会自动校验这四项。

> 修掉的一个 bug：第一版 seed 本周 7 天全有记录 → `gap.owed = 0` → 今日屏显示「欠 0 次」，**等于缺口行没有**。评委问「你和打卡群差别在哪」就哑火了。已改成本周只学 3 天。
