# C 模块 · 学习截图识别接口 v1.1

> 版本：v1.1　时间：2026-10-31 09:35　负责人：C 模块
> 依据：A 模块《接口确认_v1.1_前端答复C模块》10 题答复 + 追加 4 条
> 状态：**C 侧已全部实现并自测通过**，等 A 联调

---

## 一、v1.0 → v1.1 变更清单

| # | 变更 | v1.0 | v1.1 | 来源 |
|---|---|---|---|---|
| 1 | `encouragement` | `{level, message}` | **只输出 `{level}`，不再有 message** | Q1 |
| 2 | `schema_version` | `"1.0"` | **`"1.1"`** | 追加-4 |
| 3 | 新增 `user_id` | 无 | **顶层字段，C 原样透传** | Q5 |
| 4 | 异常码命名 | `UNRECOGNIZED_IMAGE` | **`NOT_A_STUDY_SCREENSHOT`** | 上一轮 |
| 5 | `correct_count` | 必填数字 | **允许 `null`** | Q4 |
| 6 | `accuracy` 算法 | 模型自算 | **本地重算：只用有正确数的模块；全缺则 `null`** | Q4 |
| 7 | 置信度 | 单档 0.6 | **两档：`<0.5` 非学习截图；`0.5~0.6` 模糊** | Q7 |
| 8 | 新增异常码 | — | **`OLD_SCREENSHOT` / `CORRECT_COUNT_INVALID` / `DURATION_TOO_LONG`** | Q6/Q8 |
| 9 | `DUPLICATE_RECORD` | 枚举中存在 | **保留字段，本期不触发**（去重在前端做） | Q6 |
| 10 | 交付形态 | html 页面 | **单文件 `recognize.js`，可 `<script>` 引入** | Q2 |
| 11 | 异常行为 | 抛异常 / 返回 null | **任何情况都返回标准对象，绝不抛异常** | 追加-1 |

---

## 二、调用方式

A 只需引一个文件，无需后端：

```html
<script src="recognize.js"></script>
```

```js
// file 为 <input type="file"> 取到的 File 对象
// userId 演示期固定传 "demo_zhang"，C 不做任何逻辑，原样塞进返回 JSON
const result = await window.recognizeScreenshot(file, "demo_zhang");
```

**契约保证（A 的等待态不会卡死）**：

- 永远 `resolve`，**不 `reject`、不 `throw`**
- 永远返回结构完整的标准对象，**不会是 `null` / `undefined`**
- 内置 **20 秒超时（单次调用，不重试）**——详见第五节第 5 条的实测依据
- 返回体带 `_elapsed_ms` 字段（本次耗时毫秒），**非契约字段**，可直接忽略或删掉

> ⚠️ **稳定性声明（v1.1-r4 补充，请 A 务必看一眼）**
> 识别结果是**概率输出，不是确定性输出**：同一张截图不同次调用，字段值可能不同
> （实测 test5 两轮分别为「正确率 `null` / normal」与「正确率 0.81 / excellent」；
> test7 两轮题量 97 → 130）。
> 因此「跑批 10/10」的口径是**每次都返回合法 JSON、不抛异常、等级落在四档之内**，
> **不等于**「每次都识别出相同的数字」。
> 结论：**确认卡的字段必须允许用户手改**，路演演示必须有录屏兜底。

> ⏱ **等待态建议按 20~25 秒设计**。多轮实测（10 张真实学习截图 × 数轮）：
> 最快约 **2.4s** / 平均 **5.4 ~ 6.9s** / 最慢 **10.8 ~ 14.3s**，全部一次成功。
> 模型响应存在波动，请按区间理解，不要引用单点值；个别慢图仍可能走到 20 秒窗口上限。

---

## 三、返回结构

```json
{
  "schema_version": "1.1",
  "user_id": "demo_zhang",
  "recognition": {
    "recognized_at": "2026-10-31T09:30:12+08:00",
    "confidence": 0.93
  },
  "source_app": "粉笔",
  "event_date": "2026-10-31",
  "event_time": "21:30",
  "duration_minutes": 17,
  "modules": [
    { "name": "资料分析", "question_count": 20, "correct_count": 19 }
  ],
  "total_questions": 20,
  "accuracy": 0.95,
  "warnings": [],
  "encouragement": { "level": "normal" },
  "_elapsed_ms": 3210
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定 `"1.1"` |
| `user_id` | string | 调用方传入，原样透传 |
| `recognition.recognized_at` | string | ISO8601 **带本地时区**（如 `+08:00`） |
| `recognition.confidence` | number | 0~1，模型自评把握度 |
| `source_app` | string \| null | 粉笔 / 华图在线 / 腰果公考 / 学习强国；认不出为 `null` |
| `event_date` | string \| null | `YYYY-MM-DD` |
| `event_time` | string \| null | `HH:MM` 24小时制 |
| `duration_minutes` | number \| null | 学习时长（分钟） |
| `modules[]` | array | 无数据时为 `[]` |
| `modules[].name` | string | 言语理解 / 判断推理 / 数量关系 / 资料分析 / 常识判断 / 申论 |
| `modules[].question_count` | number \| null | 题量 |
| `modules[].correct_count` | number \| **null** | 正确数，**申论等无正确数的模块为 `null`** |
| `total_questions` | number \| null | 各模块题量之和 |
| `accuracy` | number \| null | 0~1 两位小数；**全部模块无正确数时为 `null`（不填 0）** |
| `warnings[]` | array | `{code, message}[]`，无异常为 `[]` |
| `encouragement` | object | **只含 `level`**，识别失败时为 `{"level": ""}` |
| `encouragement.level` | string | `low`/`normal`/`good`/`excellent`，失败时 `""` |
| `_elapsed_ms` | number | 调试用耗时，**非契约字段** |

---

## 四、warnings 枚举（10 个）

| code | 触发条件 | 是否本期触发 |
|---|---|---|
| `NOT_A_STUDY_SCREENSHOT` | 非学习截图，或 `confidence < 0.5` | ✅ |
| `SCREENSHOT_BLURRY` | `0.5 ≤ confidence < 0.6`，或 confidence ≥0.5 但抽不到任何字段 | ✅ |
| `DURATION_MISSING` | 未识别到学习时长 | ✅ |
| `DURATION_TOO_SHORT` | 时长 < 5 分钟 | ✅ |
| `DURATION_TOO_LONG` | 时长 > 600 分钟 | ✅ |
| `ACCURACY_TOO_LOW` | 正确率 < 0.4 | ✅ |
| `MODULE_MISMATCH` | 各模块题量之和 ≠ `total_questions` | ✅ |
| `CORRECT_COUNT_INVALID` | 某模块 `correct_count > question_count` | ✅ |
| `UNRECOGNIZED_APP` | 认不出 App，但图里确实有学习数据 | ✅ |
| `OLD_SCREENSHOT` | 学习时刻距今 > 36 小时 | ✅ |
| `DUPLICATE_RECORD` | — | ❌ **预留字段，本期永不触发**（无状态单次调用感知不到重复，去重在前端 file hash 做） |

> **`message` 的约定**（按 Q6）：C 填初始中文文案，**仅供调试可读**。前端按 `code` 覆盖成自己的文案，**`code` 是唯一契约**。

---

## 五、等级判定（C 本地算，不信任模型返回值）

| level | 条件 |
|---|---|
| `excellent` | `accuracy > 0.8` **且** `duration_minutes ≥ 30` |
| `good` | `0.6 ≤ accuracy ≤ 0.8` **且** `duration_minutes ≥ 20` |
| `low` | `accuracy < 0.4` **或** `duration_minutes < 10` |
| `normal` | 以上都不满足 |
| `""` | 识别失败，或 accuracy 与 duration 均为 null |

> 例：95% + 17 分钟 → **`normal`**（不是 excellent）。这条已写死在本地，模型即使返回 excellent 也会被纠正。

---

## 六、边界规则

**1. accuracy 计算（Q4）**

- 只用 `correct_count` 非 null 的模块参与计算
- 公式：`Σ正确数 / Σ题量`，保留两位
- **所有模块都无正确数 → `accuracy = null`**（不填 0，避免误触 `ACCURACY_TOO_LOW`）
- 顺带提醒 D：申论通常没有正确数，seed 数据注意这点

**2. OLD_SCREENSHOT 的 36 小时（Q8）**

- `event_time` 有值 → 按 `event_date + event_time` 拼时刻比较
- `event_time` 为 null → 按 `event_date` **当天 12:00** 算
- `event_date` 为 null → **静默跳过，不报**

**3. 置信度两档（Q7）**

| confidence | 结果 |
|---|---|
| `< 0.5` | `NOT_A_STUDY_SCREENSHOT`，**warnings 只保留这一个**（不追加数据类噪音） |
| `0.5 ~ 0.6` | `SCREENSHOT_BLURRY`，照常出确认卡 |
| `≥ 0.5` 但关键字段全 null | 归 `SCREENSHOT_BLURRY`，照常出确认卡，**C 不做特殊分支** |

**4. 不合规图片（追加-3）**

收到非图片格式 / 超过 10MB / 空文件时，**返回标准对象 + `NOT_A_STUDY_SCREENSHOT`**，不抛异常、不崩。

**5. 超时与重试（追加-2，10:09 跑批后修订）**

- 内置 **20 秒超时，单次调用，不重试**（`TIMEOUT_MS = 20000`、`MAX_RETRIES = 0`）
- 超时 → 返回标准对象 + `NOT_A_STUDY_SCREENSHOT`，message 里写明原因，**不抛异常**

**为什么从「15 秒 + 重试 1 次」改成「20 秒不重试」**：

原方案经 10 张真实截图跑批验证后发现会**误杀正常学习图**：

| 场景 | 原方案表现 | 说明 |
|---|---|---|
| test7（模块数据完整的模考报告页） | 两次均超时，20 秒后兜底成 `NOT_A_STUDY_SCREENSHOT` | 该图放宽到 35 秒后**仅用 5.2 秒即正确识别** |

根因：`auto` 为路由模型，后端响应时间波动大（5~10 秒+）。10 秒窗口遇慢响应即掐断，
重试大概率仍路由到慢节点、收效低，且会把最坏耗时从 15 秒翻倍到 30 秒。
改为单次 20 秒窗口后，多轮跑批（10 张 × 数轮）全部一次成功、零重试。

**实测耗时（多轮区间，10 张真实学习截图）**：最快约 2.4s / 平均 5.4 ~ 6.9s / 最慢 10.8 ~ 14.3s。
请 A 据此把等待态从 15 秒调整为 **20~25 秒**。

---

## 七、示例

### 7.1 正常学习截图

```json
{
  "schema_version": "1.1",
  "user_id": "demo_zhang",
  "recognition": { "recognized_at": "2026-10-31T09:30:12+08:00", "confidence": 0.93 },
  "source_app": "粉笔",
  "event_date": "2026-10-31",
  "event_time": "21:30",
  "duration_minutes": 17,
  "modules": [{ "name": "资料分析", "question_count": 20, "correct_count": 19 }],
  "total_questions": 20,
  "accuracy": 0.95,
  "warnings": [],
  "encouragement": { "level": "normal" }
}
```

### 7.2 非学习图片（猫/风景）

```json
{
  "schema_version": "1.1",
  "user_id": "demo_zhang",
  "recognition": { "recognized_at": "2026-10-31T09:31:00+08:00", "confidence": 0.05 },
  "source_app": null,
  "event_date": null,
  "event_time": null,
  "duration_minutes": null,
  "modules": [],
  "total_questions": null,
  "accuracy": null,
  "warnings": [
    { "code": "NOT_A_STUDY_SCREENSHOT", "message": "这张图片没有识别到学习数据" }
  ],
  "encouragement": { "level": "" }
}
```

### 7.3 服务异常 / 超时

```json
{
  "schema_version": "1.1",
  "user_id": "demo_zhang",
  "recognition": { "recognized_at": "2026-10-31T09:32:00+08:00", "confidence": 0 },
  "source_app": null,
  "event_date": null,
  "event_time": null,
  "duration_minutes": null,
  "modules": [],
  "total_questions": null,
  "accuracy": null,
  "warnings": [
    { "code": "NOT_A_STUDY_SCREENSHOT", "message": "识别失败：识别超时（超过20秒）。" }
  ],
  "encouragement": { "level": "" }
}
```

> 注意：**异常也是标准对象**，A 不需要写 `try/catch` 之外的分支，按 `warnings[].code` 判断即可。

---

## 八、回答 A 追加的 4 件事

| # | A 的问题 | C 的处理 |
|---|---|---|
| 1 | `NOT_A_STUDY_SCREENSHOT` 返回形态 | **仍返回标准对象**，`warnings` 带该 code。不抛异常、不返回 null、无 HTTP 状态码概念（浏览器内直调）。✅ 已实现 |
| 2 | 耗时与超时 | **已跑批实测并修订**：`TIMEOUT_MS = 20000`、`MAX_RETRIES = 0`（原 15s+1 次重试会误杀正常图，见第五节第 5 条）。实测（多轮区间）：最快约 2.4s / 平均 5.4 ~ 6.9s / 最慢 10.8 ~ 14.3s。**等待态请按 20~25 秒设计** |
| 3 | 不合规图片行为 | 格式不符 / 超 10MB / 空文件 → 返回标准对象 + `NOT_A_STUDY_SCREENSHOT`，不崩 ✅ |
| 4 | `schema_version` | 已写 `"1.1"` ✅ |

---

## 九、安全说明（回应 Q2 条件 2）

`recognize.js` 里只有 `publishableKey`（`wbpk_` 前缀），这是 **WorkBuddy 云服务的公开标识，本身无任何权限**，设计上就是放在前端的。

- 真正的密钥由平台托管，**不在代码里、不在仓库里**
- 因此 **`recognize.js` 可以安全提交公开仓库、部署到 Vercel**
- 如果后续换成需要私密 Key 的方案，我会单独给你一份走环境变量的版本

---

## 十、`accuracy` 本地重算规则（10:09 修订，重要）

C 会对模型返回的 `accuracy` 做本地校验，**但不是无条件覆盖**。三态规则：

| 条件 | `accuracy` 取值 |
|---|---|
| 所有模块都缺 `correct_count` | `null`（不填 0，避免误触 `ACCURACY_TOO_LOW`） |
| `total_questions` 为 `null`，**或**模块题量之和 **==** `total_questions` | **本地重算**：`sum(correct_count) / sum(question_count)`，纠正模型算术错误 |
| 模块题量之和 **!=** `total_questions`（截图只露出部分模块） | **保留模型返回的 `accuracy`**；模型也没给才用残缺模块兜底 |

**为什么 `total_questions` 为 `null` 时也本地重算**：此时 `total_questions` 会用模块题量之和回填，
正确率必须来自同一套数据，否则确认卡会出现「总题量 40、正确率 90%，但逐模块行加起来只有 50%」
的自相矛盾（A 在验收第二版中提出的 P2，已采纳）。

**为什么不全量本地重算**：实测发现截图常只露出部分模块（test5 只露出「政治理论」），
此时用残缺模块重算会算偏——该图页面明写「答对 109/135 ≈ 81%」，全量重算却输出 70%，
**把正确值改错了**。而模型更可能读到页面上的总答对数，故模块不全时以模型值为准。

修复效果：test5 `70% → 81%`（等级随之由 `good` 修正为 `excellent`）、
test10 `54% → 56%`（75/135）、test7 `72% → 75%`（97/130）。

> 模块不全时仍会照常输出 `MODULE_MISMATCH` 警告，A 可按该 code 提示用户补充完整截图。

---

## 十一、`duration_minutes` 取整（10:25 新增）

`duration_minutes` **保证是整数分钟**。模型偶尔把截图上的「8 分 47 秒」误读成小数 `8.47`
（把秒当成小数位），若不处理，确认卡会显示「学习时长 8.47 分钟」，明显穿帮。

C 侧统一做**四舍五入取整**，误差在 1 分钟内，对鼓励等级判定（阈值 10 / 20 / 30 分钟）基本无影响。

---

## 十二、跑批验收结果（10 张真实学习截图，多轮）

| 指标 | 结果 |
|---|---|
| 学习截图识别成功 | **10 / 10**（任务卡要求 ≥5/6，超额达标） |
| 非学习图误拒 | 0 |
| 失败 / 异常 | 0 |
| 耗时（多轮区间） | 平均 **5.4 ~ 6.9s**；最快约 2.4s；最慢 **10.8 ~ 14.3s** |
| 重试触发次数 | 0（全部一次成功） |

> `auto` 为路由模型，响应时间本身有波动，**路演材料引用耗时请写区间，不要写单点值**。

---

## 十三、待确认（全部关闭）

1. ~~实际识别耗时~~ → **已关闭**，跑批实测完成，见第五节第 5 条
2. ~~`encouragement` 是否扁平化~~ → **已关闭**，A 回复：保持 `{level}`，不扁平化
3. ~~话术是否需要数据变量~~ → **已关闭**，A 回复：纯文本定稿，不要变量

---

## 附：交付物清单

| 文件 | 用途 | 给谁 |
|---|---|---|
| `recognize.js` | 识别能力本体，A 直接引入 | **A** |
| `phrases.json` | 12 条话术终稿（每档 3 条，8–24 字，主语「我」，无感叹号） | **A**（已按你的意见定稿） |
| `index.html` | C 模块自己的演示页（内部仍展示话术，不影响接口） | C 自留 |
| `encouragement.json` | C 演示页用的 16 条话术库（内部用） | C 自留 |
| `batch-test.js` | 跑批验收脚本（Node），可复跑验证 | C 自留 |

---

## 变更记录

| 版本 | 时间 | 变更 |
|---|---|---|
| v1.1 | 09:32 | 初版，合并 A 的 10 题答复 |
| v1.1-r1 | 09:46 | `phrases.json` 更新为 A 终稿；SDK 锁定版本 |
| **v1.1-r2** | **10:13** | ① 超时 15s+1 次重试 → **20s 单次不重试**（跑批发现会误杀正常图，附实测依据）；② `accuracy` 本地重算改为三态规则（模块不全时保留模型值）；③ 补充跑批验收结果 |
| **v1.1-r3** | **10:26** | ① **`accuracy` 边界补齐**（A 的 P2）：`total_questions` 为 `null` 时也本地重算，保证总题量与正确率同源，确认卡不自相矛盾；② **新增 `duration_minutes` 取整**，修掉模型把「8分47秒」误读成 `8.47` 的穿帮；③ 耗时口径统一为多轮区间（原注释残留旧轮次数据，已与实测对齐） |

| **v1.1-r4** | **11:26** | ① **P1 修复（A 提出）**：契约自洽——`encouragement.level == ""` 时**必定**带 `NOT_A_STUDY_SCREENSHOT` warning（原 `noData` 分支只置空 level、不置 warning，前端只认 code 的分支会漏判）；② 新增 **`accuracy` 百分制归一**防御（模型偶尔把 `0.75` 写成 `75`，前端会显示 7500% 且被误判 excellent）；③ 耗时口径并入最新一轮跑批（最慢 14.3s） |

> **r3 / r4 均未改动任何接口字段、结构或调用方式**，A 只需覆盖 `recognize.js` 一个文件，无需改前端代码。
