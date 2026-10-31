# A 前端：识别仍走 mock，学习日期永远是 10-30

> 写给：A ｜ 时间：2026-10-31 ｜ 对应复核文档：`docs/全分支复核_问题汇总_1515.md` 的 **P1-9**
> 结论先说：**不是 bug，是 `USE_MOCK = true` 还开着。** 改它之前，界面上看到的"识别结果"跟你上传的截图无关。

---

## 一、现象

用 Vue 工程（`A-module-frontend/app`）上传任意截图 → 确认卡里「学习日期」永远是 `2026-10-30`，时长、题数、模块也永远是同一套。

## 二、原因（可复现）

| 位置 | 内容 |
|---|---|
| `app/src/api.js:5` | `export const USE_MOCK = true` |
| `app/src/api.js:50-54` | `recognize()` 里 `if (USE_MOCK)` 直接 `sleep` 4~6 秒，然后从 `SCENARIOS` 里取固定样本返回，**`file` 参数根本没被读** |
| `app/src/mockData.js:14, 55, 74, 96, 138, 158` | 样本里 `event_date` 写死 `'2026-10-30'` |
| `app/src/components/ConfirmCard.vue:14` | 确认卡只是回显 `recognition.event_date` |
| `app/src/App.vue:94-96` | 顶部"演示场景"下拉用来选 mock 样本，真识别时没有意义 |

所以链路是：上传 → **假装识别 5 秒** → 返回写死的 10-30 样本 → 确认卡回显。C 的 `recognize.js` 虽然在 `index.html` 里加载了，但这条路径下**一次都没被调用**。

## 三、为什么这事不只是"显示不对"

你最近的提交（`1684481`）把 `submitRecord` / `fetchToday` 改成了**真接口优先**。现在是"识别假、入库真"：

1. 确认卡提交后，那条 **10-30 的假记录会真的写进 B 的 `store.json`**；
2. B 的状态引擎按这条假记录重算 → 今日屏的仓鼠状态、缺口行（欠几次）**基于假数据**；
3. 同一个样本反复点，B 的去重（`05259f8`，120 秒内同内容只留一条）会挡掉，隔 2 分钟以上又会再记一条，**同日时长被累加**。

路演现场如果跑 Vue 工程，评委看到的"识别"是假的，而缺口行是真的，两者对不上。

## 四、怎么改（三选一，推荐 A 方案）

### A 方案：直接删掉 mock 路径（推荐）

1. `api.js`：删 `USE_MOCK`、`import { SCENARIOS }`，删 `recognize()` 里的 `if (USE_MOCK) {...}` 整块，`recognize(file)` 去掉 `scenarioKey` 参数。
2. `App.vue`：删 `import { SCENARIOS }`、`scenario` ref、顶部"演示场景"下拉（`dev-bar`），`recognize(file, scenario.value)` 改 `recognize(file)`。
3. `mockData.js`：`MODULE_NAMES` / `APP_NAMES` 是确认卡真实选项，**不是 mock**，迁到新文件 `src/constants.js`，`ConfirmCard.vue` / `FallbackChips.vue` 的 import 指向 `../constants`；然后删除 `mockData.js`。
4. `style.css` 删 `.dev-bar`。

### B 方案：只翻开关（最小改动）

`api.js:5` 改成 `USE_MOCK = false`。代价：mock 代码和下拉还在，下拉选什么都不再生效，容易误导后来的人。

### C 方案：不改，现场不跑 Vue 工程

复核文档里已定"演示用单文件原型，工程只做架构展示"。可以，但 README 要明确写"Vue 工程默认是 mock 识别，勿用于演示"。

## 五、改完怎么验收

| 检查 | 通过标准 |
|---|---|
| 上传 `test-images/test5.jpg` | 浏览器 Network 面板能看到对 C 云端的识别请求；等待 5~10 秒是真实耗时，不是固定 4~6 秒 |
| 确认卡「学习日期」 | 是截图里的日期，不再恒为 `2026-10-30` |
| 换一张不同截图 | 时长/题数/模块随之变化 |
| 上传一张非学习截图 | 走 `NOT_A_STUDY_SCREENSHOT` → 兜底手填页 |
| `grep -rn "USE_MOCK\|mockData\|SCENARIOS" app/src` | 无结果 |
| `vite build` | 通过 |

## 六、顺带发现的三个小问题（不阻塞，A 自行判断）

1. **探测端口列表包含 8787**（`api.js:92`）。8787 是 `mock-server`，不是 B。如果 B 没起、`mock-server` 在跑，界面会显示「已连通」，实际连的是假后端。建议去掉 8787，或在界面标出当前连的是哪个地址。
2. **入库失败静默**：`submitRecord` 失败时返回 `{ ok: true, persisted: false }`（`api.js` 约 125 行），但 `App.vue` 没读 `persisted`，用户看不到"没存上"。建议今日屏提示一句"本次未同步到后端"。
3. **`ALLOW_MOCK_WHEN_OFFLINE` 默认开启**：后端不可达且无缓存时，今日屏会显示 `MOCK_TODAY`（欠 2 次）。已打了「离线 · 演示数据」标签，没有冒充，但路演前确认一下是否是你想要的行为。

## 七、B 侧同步情况（供 A 参考）

`05259f8` 已推送：`POST /api/records` 对同 `user_id + event_date + modules + total_questions` 且 `confirmed_at` 相差 <120 秒的提交返回已有 `record_id`；CORS 放开 `localhost` / `127.0.0.1` 任意端口。pytest 40 passed。
