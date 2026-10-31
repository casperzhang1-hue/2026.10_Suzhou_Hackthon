# A 模块 · 前端与视觉

> 负责人：A（曹苏睿）｜ 2026-10-31 19:00 更新 ｜ 宠物形象：**仓鼠**（任务卡的「小芽」已作废）
> 一句话：**让 B / C / D 不用找 A 要文件，全链路就能跑通**

---

## 零、前端入口只有一个：`index.html`

**看前端、录屏、给评委看，只用这一个文件**：

```
A-module-frontend/index.html        ← 481 KB，自包含，双击即开，不需要 npm / 不需要后端
```

它就是 `原型/仓鼠陪跑_原型_接真数据_单文件版.html` 的同步副本（`sync_frontend.py` 生成，
别直接改 index.html；改原型后跑一次 `python A-module-frontend/sync_frontend.py`）。

**为什么是它而不是 Vue 工程**：五屏、仓鼠五态、缺口行、记忆墙、底部 dock 全在这个文件里，
样式和动效都已定稿；`app/dev.html`（Vue）只是 13:30 为了对接 B 的接口、C 的 recognize.js 搭的**联调壳**，
UI 是极简版，**不是演示门面**。

### 17:55 之后：`npm run dev` 打开的就是这一屏

之前 `npm run dev` 打开的是极简联调壳，跟原型完全不是一个东西——这是"前端怎么长得不一样"的全部原因。
现在工程里做了入口重排，两条路都留着：

```
app/
├── index.html            ← npm run dev 的首页：跳转 → ./prototype.html（= 原型，481KB）
├── dev.html              ← Vue 联调壳（原来的 index.html，接 B 的 /api/today、C 的 recognize.js）
└── public/prototype.html ← 原型的副本，由 sync_frontend.py 生成，别手改
```

- **要看视觉 / 录屏 / 给评委看** → `npm run dev`，打开 `http://localhost:5173/` 就是原型那一屏
- **要联调真后端** → 同一个服务，打开 `http://localhost:5173/dev.html`（右下角有「← 回到演示版」）
- 端口固定在 **5173**（`strictPort`），因为 B 的 CORS 只放行 5173，别改
- GitHub 上直接点 html 只能看源码；要变成能点开的链接，见下方「部署成链接」

### 信息架构（打开后看到的顺序）

| # | 屏 | 内容 | 数据来源 |
|---|---|---|---|
| 1 | 今日 `data-page="home"` | 陪你的第 47 天 / 距笔试 46 天 → 仓鼠五态 + 状态词（踏实）+ 一句话 → **本周欠 2 次**（缺口卡，可展开到模块级）→ 传今天的截图 / 今天没学 | 内置演示数据 + 真识别回填 |
| 2 | 记忆 `data-page="memory"` | 41 天前那句承诺 → 本周正确率 48% → 活力曲线（近 45 天，断签 2 次）→ 三条它注意到的事 | 内置演示数据 |
| 3 | 档案 `data-page="archive"` | 开始日 / 有效天数 39 / 缺勤 8 / 最长连续 27 / 深夜 63 / 各模块 52%→71% | 内置演示数据 |
| 4 | 出分日 `data-page="result"` | 想过放弃 3 次 / 还是坐下来 3 次 | 内置演示数据 |
| 5 | 确认卡 / 兜底 | 上传真实截图 → 识别等待 → 确认卡（可改字段）→ 非学习图走兜底手填 | **C 的 r6 真识别**（内联，SDK 已内嵌） |

- 底部 dock 七格：演示路径 / 今日 / 传截图 / 回忆 / 出分日 / 实拍 / 切屏（后两个是演示辅助，路演时可只用前五个）
- 仓鼠五态：`yuanqi 元气` / `tashi 踏实` / `pibei 疲惫` / `nianle 蔫了` / `xiumian 休眠`，
  五张 512 透明底 WebP 已 base64 内联在文件里，**离线也不会缺图**
- 识别：C 的 `recognize.js v1.1-r6` 全文内联（**SDK 已内嵌，不再依赖 jsdelivr**），上传真截图走真识别；识别服务连不上时降级到演示样本，不白屏

### 19:00 · 识别升级到 C 的 r6（去掉了 CDN 单点）

C 在 `main` 上把 `recognize.js` 升到 **v1.1-r6**（100,083 B）：**WorkBuddy SDK 已内嵌进文件末尾**，
不再运行时去 `cdn.jsdelivr.net` 下载。原因是实测本机直连 jsdelivr 超时（只有走代理才通，且慢到 21.8s），
而**浏览器不走系统代理** → r5 在浏览器里会加载 SDK 失败 → 识别整条挂、次次走兜底。

A 侧已同步，改动三处（前端代码零改动）：

| 文件 | 现在 |
|---|---|
| `A-module-frontend/index.html` | 481 KB，内联 **r6**（原 419 KB / r5） |
| `A-module-frontend/app/public/prototype.html` | 同上，`sync_frontend.py` 的同步副本 |
| `A-module-frontend/app/public/recognize.js` | r6，100,083 B |
| `C-module-recognition/recognize.js`（分支内镜像） | r6，100,083 B |

实测（`node batch-test.js`，**未加 `--use-env-proxy`**，即模拟浏览器不读代理的情形）：

- `test5.jpg` → `excellent · 粉笔 · 2026-10-30 · 115分 · 135题 · 81%`，5.9s
- `test9.jpg` → `normal · 21分 · 62题`，8.1s
- `test4.jpg` → `low · 15题 · 93%`，3.0s（r5 时代无代理这里是 `环境初始化失败: fetch failed`）

内联到单文件 HTML 时有一处坑：r6 文件头注释里有 `</script>`（用法示例），必须转义成 `<\/script`，
否则脚本块被浏览器提前截断。已在 `_sync_r6.py` 里处理并做了 `node --check` 语法校验。

### 三种打开方式

| 你要干什么 | 怎么做 |
|---|---|
| 看视觉 / 录屏 / 路演 | 双击 `A-module-frontend/index.html`（或浏览器拖进去）；或 `cd app && npm run dev` → `http://localhost:5173/`，**两者是同一屏** |
| 部署成链接 | 把这个文件放到任意静态托管（GitHub Pages 的 branch 根目录即可，根 `index.html` 已做跳转）；`npm run build` 产物里 `dist/index.html` 也是同一个跳转 |
| 跑真后端联调 | `npm run dev` 后开 `http://localhost:5173/dev.html`（Vue 壳，接 B 的 `/api/today`）；`index.html` / `prototype.html` 不连后端，它们是演示门面 |

---

## 一、目录结构

```
A-module-frontend/
├── index.html           ★ 前端入口（481KB 自包含原型，双击即开）
├── sync_frontend.py     ★ 原型 → index.html + app/public/prototype.html 同步脚本
├── app/                 Vue 工程：npm run dev 打开的是原型，dev.html 才是联调壳
│   ├── index.html       ★ 只做跳转 → ./prototype.html（演示门面）
│   ├── dev.html         ★ Vue 联调壳（接 B 的 /api/today、C 的 recognize.js）
│   ├── vite.config.js   端口锁 5173 + 双入口（index.html / dev.html）
│   ├── src/             App.vue、api.js、组件、话术、仓鼠五态图
│   └── public/
│       ├── prototype.html  原型的副本（sync_frontend.py 生成）
│       └── recognize.js    C 的识别脚本（v1.1-r6，97KB）
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
├── seed/                ★ 本次新增：给 D 的假数据生成器
│   └── make_seed.py     生成脚本，产物直接写到 mock-server/data/seed.json（唯一一份）
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

- 数据在 **`mock-server/data/seed.json`（唯一一份，45 天）**，已按故事线造好（D8 断签 / D15 凌晨崩溃 / D22 承诺 / 本周 48%）
- 要改数字就改 `seed/make_seed.py` 再 `python seed/make_seed.py`，**直接覆盖那一份 json**；`SEED_TODAY=2026-10-31` 可钉住生成日期，不钉就用运行当天
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
