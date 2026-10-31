# A 模块 · 前端与视觉资产

> A 上传 ｜ 2026-10-31 ｜ 宠物形象：**仓鼠**（任务卡的「小芽」已作废）
> 用途：**让 B / C / D 不用找 A 要文件，全链路就能跑通**

---

## 一、这个目录解决什么问题

B 的三个接口还没交付，D 的 `seed.json` 已逾期。全链路卡在「后端没东西可接」。

所以除了素材，这里还放了两样**能让链路立刻跑起来的东西**：

1. **`mock-server/`** —— 零依赖 Node 后端，B 交付前全链路靠它跑通
2. **`seed/`** —— 45 天自洽假数据（D 逾期，A 先造一份兜底，D 来了直接替换）

**B 交付后，前端只改 `frontend/src/api.js` 里的 `API_BASE` 一个常量，业务代码一行不动。**

---

## 二、目录结构

```
A/
├── README.md                 本文件
│
├── pet-assets/               ★ CDN 素材，全队统一调用仓鼠形象
│   ├── hamster.css           五态切图 + 微动效 + 预加载
│   ├── hamster.js            HamsterKit（level → 态）
│   ├── index.html            预览页
│   └── img/                  五态 512 WebP（透明底）+ 解锁件 4 张
│
├── contract/                 ★ 三接口契约，B 照这个实现
│   ├── README.md             字段表 + 判定规则
│   ├── records.request.example.json        POST /api/records 请求体
│   ├── today.response.example.json         GET /api/today 响应
│   ├── memories.response.example.json      GET /api/memories 响应
│   └── recognition.response.example.json   C 的识别结果（已定稿 r4）
│
├── mock-server/              ★ B 交付前全链路靠它
│   ├── server.js             零依赖 node:http，8787 端口
│   ├── engine.js             状态引擎（从 A 原型原样移植，B 直接复用别重写）
│   └── data/
│       └── seed.json         45 天假数据（与 seed/seed.json 同一份）
│
├── seed/                     ★ 给 D 的假数据（D 可直接替换）
│   ├── make_seed.py          生成脚本，改完重跑会同步到 mock-server
│   └── seed.json             45 天，自洽校验通过
│
├── prototype/                四版原型 HTML
│   ├── 仓鼠陪跑_原型_接真数据_单文件版.html   ★ 双击即开，录屏从这里出
│   ├── 仓鼠陪跑_原型_接真数据版.html
│   ├── 仓鼠陪跑_原型_单文件版.html
│   └── img/                  五态 WebP
│
├── frontend/                 Vue 工程
│   ├── index.html / package.json / vite.config.js
│   ├── public/recognize.js   C 的 r4 识别脚本
│   └── src/                  App.vue、api.js、五屏组件、话术
│
└── test-images/              C 的 10 张真实截图测试集
    └── test5.jpg             ★ 唯一不带黄条的图（路演主演示图）
```

---

## 三、每个人从这里拿什么

### 👤 B（后端）—— 拿 `contract/` + `mock-server/`

```bash
cd A/mock-server && node server.js     # 先看它怎么返回，照着实现你的真后端
```

三个接口：

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/records` | POST | 确认后入库，返回最新 today |
| `/api/today` | GET | 今日屏：宠物态、活力值、用户态、话术档、**缺口行** |
| `/api/memories` | GET | 记忆屏：承诺/事件列表 |

⚠️ 两条硬要求：

- **`engine.js` 直接复用，别重写** —— 它是从原型 761–805 行原样移植的。否则前端一套算法、后端一套算法，现场两套结果不一致。
- **`gap` 字段不能省** —— RK-08 是全场最高风险（16 分）。`owed = 0` 时缺口行消失，防法失效。

### 👤 C（识别）—— 拿 `contract/recognition.response.example.json`

你的 r4 已全量接入（`frontend/public/recognize.js`），这里只是留档。**识别侧已结项**，守好 16:00 / 18:00 / 23:00 三个时间点即可。

### 👤 D（产品/路演）—— 拿 `seed/` + `prototype/` + `test-images/`

- `seed/seed.json` 已按故事线造好（D8 断签 / D15 凌晨崩溃 / D22 承诺 / 本周 48%），**直接用或改完重跑 `make_seed.py`**
- `prototype/仓鼠陪跑_原型_接真数据_单文件版.html` 双击即开，录屏素材从这儿出
- `test-images/test5.jpg` 是唯一不带 `OLD_SCREENSHOT` 黄条的图，**路演主演示图用它**
- ⚠️ **发现任务卡内部矛盾**：写的是「30 天假数据」，但记忆屏要引用「41 天前说的话」——30 天覆盖不到 41 天前，记忆屏会自相矛盾。**我已拉到 45 天**，请确认口径

---

## 四、CDN 调用（素材统一入口）

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/casperzhang1-hue/2026.10_Suzhou_Hackthon@v1.0.0/A/pet-assets/hamster.css">
<div class="hamster" data-state="yuanqi" style="--hamster-size:240px"></div>
<script src="https://cdn.jsdelivr.net/gh/casperzhang1-hue/2026.10_Suzhou_Hackthon@v1.0.0/A/pet-assets/hamster.js"></script>
```

不用 JS 也行：`el.dataset.state = 'pibei'` 一行切态。

⚠️ 三个坑：

1. 仓库必须 **public**，jsDelivr 才读得到
2. **锁 tag（`@v1.0.0`）别用 `@main`** —— CDN 缓存最长 7 天
3. CSS 和 `img/` 必须同层（CSS 里是相对路径 `img/`）

---

## 五、本地跑通全链路（三步）

```bash
# 1. 起 mock 后端（B 交付前）
cd A/mock-server && node server.js            # http://127.0.0.1:8787

# 2. 起前端
cd A/frontend && npm install && npm run dev   # http://127.0.0.1:5173

# 3. 接真识别
#    把 src/api.js 的 USE_MOCK 改成 false
```

**不想装依赖？** 直接双击 `A/prototype/仓鼠陪跑_原型_接真数据_单文件版.html`，图片和 recognize.js 都已内嵌。

---

## 六、已实测通过的两个关键场景（mock server 真跑）

| 场景 | 输入 | 输出 |
|---|---|---|
| 常规好图 | 115 分钟 / 81% / 20:30 | `vigour`（元气）+ `excellent` + 用户态「稳」 |
| **熬夜（最值钱那格）** | 210 分钟 / 22:40 开始 | **`tired`（疲惫）+ `过载` + `low`** → 仓鼠说「今天别学了」 |

第二行是任务卡里「全场最值钱的一格」——路演一定要演到。现在有数据支撑了。

---

## 七、seed 数据的自洽校验（防评委抓）

```
本周资料分析: 36/75 = 48.0%        ← 记忆屏引用
41 天前（2026-09-20）: 22/30 = 73.3%  ← 对比强烈
承诺日距今: 41 天                   ← 记忆屏引用
本周已学 3 天 / 目标 5 天 → 欠 2 次  ← 今日屏缺口行（RK-08）
```

改 `seed/make_seed.py` 后重跑，断言会自动校验这四项。

> 顺带修掉一个 bug：第一版 seed 本周 7 天全有记录 → `gap.owed = 0` → 今日屏显示「欠 0 次」，**等于缺口行没有**。评委问「你和打卡群差别在哪」就哑火了。已改成本周只学 3 天。
