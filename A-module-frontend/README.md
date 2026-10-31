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

**B 交付后，前端只改 `app/src/api.js` 里的 `API_BASE` 一个常量，业务代码一行不动。**

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
# 1. 起 mock 后端（B 交付前，零依赖不用 npm install）
cd A-module-frontend/mock-server && node server.js      # http://127.0.0.1:8787

# 2. 起前端
cd A-module-frontend/app && npm install && npm run dev   # http://127.0.0.1:5173

# 3. 接真识别
#    把 src/api.js 的 USE_MOCK 改成 false
```

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
