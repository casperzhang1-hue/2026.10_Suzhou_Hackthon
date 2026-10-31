# C 模块对接说明（给 A / B / D）

> 版本：**v1.1-r6**（2026-10-31 18:40）｜ 更新：2026-10-31 ｜ 维护：C（Nina）
> 接口字段的**唯一权威定义**见同目录《接口草案_C模块_识别结果JSON_v1.1.md》，本文不重复字段表，只讲「你是谁、要用什么、注意什么」。

## ⚠️ r6 必读（A 必须覆盖文件，否则现场可能识别全挂）

`recognize.js` 已升级到 **r6**，**`main` 和 `nina_chen` 两个分支都是 r6**（同一个文件，97KB）。

| | r5（旧） | r6（当前） |
|---|---|---|
| SDK 来源 | 运行时从 `cdn.jsdelivr.net` 下载 | **已内嵌进 recognize.js** |
| 网络要求 | 必须能访问 jsdelivr，否则**识别完全不可用** | 无额外网络要求（CDN 仅作兜底） |
| 文件大小 | 25KB | **97KB（正常，别以为是传错了）** |
| 前端改动 | — | **零改动，覆盖文件即可** |

**背景**：实测这台机器直连 jsdelivr 超时（只有走代理才通，且慢到 21.8s），浏览器不走代理 → SDK 加载失败 → 整条识别链路瘫痪、每次都走兜底。**现场网络同样有这个风险**，所以 r6 把 SDK 直接内嵌，消除这个单点依赖。

---

## 给 A（前端）

### 你要用的东西

| 物品 | 位置 | 用法 |
|---|---|---|
| `recognize.js` | `C-module-recognition/` | **r6**：覆盖 `app/public/recognize.js`，`<script>` 引入，前端代码零改动（文件 97KB 属正常） |
| 调用方式 | — | `const r = await window.recognizeScreenshot(file, userId)` |
| 标准测试图 | `C-module-recognition/test/` | 联调验收用，预期值见同目录《预期结果.md》 |

### 返回契约（三条铁律）

1. **永不返回 null、永不抛异常**——超时/断网/非学习图都返回标准 JSON，看 `warnings` 判断
2. **`encouragement` 只有 `{level}`**，没有 message——话术从 `phrases.json` 按 level 取，别等 C 给文案
3. **识别结果是概率输出，确认卡必须可手改**——同一张图两次识别数字可能不同（模型特性，接口文档有「稳定性声明」），这是产品设计的一部分，不是 bug

### 验收对照（传 test12 标准图）

```
event_date=2026-10-31 · duration=24 · total=15 · accuracy=0.6 · level=good
warnings=[] 或 [UNRECOGNIZED_APP]（source_app 偶尔读不出 Fb 角标，允许手改）
```

- `accuracy` 为 `null` 时确认卡显示「—」，**不能显示 0%**
- 非学习图（自拍/风景）→ `warnings` 含 `NOT_A_STUDY_SCREENSHOT` → 走兜底手填页，不能弹全空确认卡
- 等待态按 **20~25 秒**设计（实测平均 5~7s，但模型有波动，超时上限 20s）
- >10MB 大图建议前端按 `file.size` **前置拦截**，别等 C 返回

### 已排除的风险

- ✅ **CORS 不会被拦**（2026-10-31 实测：云服务网关统一回显 `Access-Control-Allow-Origin`，含 404 响应）
- ✅ **r6 已消除 CDN 依赖**（SDK 内嵌，现场访问不了 jsdelivr 也能识别）
- ✅ mock 问题的根因在 A 侧 `api.js` 的开关，与 C 无关，C 不动

---

## 给 B（后端）

### 一句话：C 不经过你

```
浏览器(A) ──直连──> WorkBuddy 云 LLM（C 的识别链路，免密钥， publishableKey 只是公开标识）
浏览器(A) ──确认卡提交──> B 的 submitRecord（你收到的是用户确认后的最终数据）
```

**C 的识别链路不调用 B 的任何接口**。你与 C 的交接面只有一个：A 确认卡提交上来的入库记录。

### 入库字段口径（与接口草案 v1.1 对齐）

| 字段 | 类型 | 注意 |
|---|---|---|
| `accuracy` | `0~1` 小数，**可为 null** | null = 截图上读不到正确率，**不是 0** |
| `duration_minutes` | 整数分钟，可为 null | 模型输出已本地取整 |
| `modules[].correct_count` | 整数，**可为 null** | 申论等无答对数的模块就是 null |
| `warnings` | 字符串数组 | **提示性**的，不作为拒绝入库的理由 |
| `user_id` | 字符串 | C 侧透传，默认 `demo_zhang` |
| `schema_version` | 固定 `"1.1"` | 收到不是 1.1 的可以告警 |

- `warnings` 码表：`SCREENSHOT_BLURRY / DURATION_MISSING / DURATION_TOO_SHORT / DURATION_TOO_LONG / ACCURACY_TOO_LOW / MODULE_MISMATCH / DUPLICATE_RECORD(本期不触发) / UNRECOGNIZED_APP / OLD_SCREENSHOT / CORRECT_COUNT_INVALID / NOT_A_STUDY_SCREENSHOT`
- 建议入库时保留 `warnings` 原样存一份，运营复盘用得到

---

## 给 D（素材）

### 话术素材（已定稿，别再改）

| 文件 | 内容 | 用途 |
|---|---|---|
| `phrases.json` | 12 条，low/normal/good/excellent 各 3 条 | **A 前端实际使用的话术库**（A 已确认定稿） |
| `encouragement.json` | 四档各 4 条带占位符版本 | C 演示页内部用，了解即可 |

话术规范：每条 8~24 字、主语「我」、无感叹号、无禁用词。占位符只有
`{accuracy} {duration_minutes} {total_questions} {module}` 四种，缺数据的话术会被自动过滤。

### seed 数据注意

- `correct_count` 允许 `null`（申论等无答对数场景），别全填成数字
- `accuracy` 允许 `null`，别默认 0
- 等级是**本地硬算**的：`excellent`(>0.8且≥30分) / `good`(0.6~0.8且≥20分) / `low`(<0.4或<10分) / `normal`(其余)，造数据时等级要和数字对得上

### 路演素材建议

- **主演示图用 `C-module-recognition/test/test12_粉笔_1031_判断推理.jpg`**：日期新（不挂黄条）、字段全、等级 good、还有 6 道错题可以带出错题本演示
- 避免用 8~10 月的旧截图：必挂 `OLD_SCREENSHOT` 黄条，评委看了会问
- 如果要演示「考砸了宠物怎么安慰」：用每日一练答题卡类截图（正确率低 → low 档话术）
- 识别结果有波动（同图两次数字可能不同），**路演前务必先跑一遍录屏兜底**

---

## 出问题找谁

| 现象 | 找谁 |
|---|---|
| 返回 null / 页面卡死超 25 秒 / JSON 不合法 | **C** |
| 数字和上次不一样、source_app 读不出、正确率 null | 不是 bug（模型特性），确认卡手改 |
| mock 不切换、确认卡不能编辑、缺口行不动 | **A** |
| 入库报错、字段对不上 | **B** 先看是不是按上面口径接的 |
| 话术文案想改 | 冻结了，路演后再说 |
