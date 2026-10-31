# 三接口契约 · B 照这个实现

> A 侧已定稿，字段不再变。**B 交付后前端只改 `API_BASE` 一个常量，业务代码一行不动。**
> 参考实现见 `../mock-server/server.js`（零依赖，可直接抄逻辑）

---

## ① `POST /api/records` —— 入库（确认卡提交）

**请求体**（示例见 `records.request.example.json`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `record.event_date` | string `YYYY-MM-DD` | ✅ | 学习日期 |
| `record.event_time` | string `HH:mm` | | 开始时间，用于熬夜判定 |
| `record.duration_minutes` | int | ✅ | **整数**（r3 已修小数穿帮） |
| `record.source_app` | string \| null | | 粉笔 / 华图在线 / 腰果公考 / 学习强国 |
| `record.modules[]` | array | | `[{name, question_count, correct_count}]`，申论的 correct_count 本来就是 null |
| `record.total_questions` | int \| null | | |
| `record.accuracy` | float `[0,1]` \| null | | **0~1 不是百分制**（r4 已归一） |
| `recognition_ref.schema_version` | string | ✅ | 固定 `"1.1"` |
| `recognition_ref.recognized_at` | ISO string | | |
| `recognition_ref.confidence` | float | | |
| **`edited_fields`** | string[] | ✅ | 用户在确认卡改过哪些字段。**PRD 15.1 要求逐字段记录，s2 修正率指标靠它** |
| `confirmed_at` | ISO string | ✅ | |
| `user_id` | string | ✅ | 演示用 `demo_zhang` |

**响应**：`{ "ok": true, "record_id": "r1" }`

---

## ② `GET /api/today` —— 今日状态

**响应**（示例见 `today.response.example.json`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | string | `YYYY-MM-DD` |
| `has_record` | boolean | 今天有没有上传过 |
| `pet_state` | enum | `vigour` / `steady` / `tired` / `wilt` / `sleep` |
| `vitality` | int 0–100 | 非对称活力值 |
| `user_state` | enum | `稳` / `平台期` / `过载` / `崩溃前兆` |
| `phrase_level` | enum | `excellent` / `good` / `normal` / `low`（对应 phrases.json 的四个 key） |
| **`gap`** | object | ⚠️ **不能省** —— `{week_target, week_done, owed}` |

> **RK-08 是全场最高风险项（16 分）**，应对手段就是「今日屏必须出现缺口行」。
> `gap.owed` 为 0 时缺口行消失，防法失效。**seed 数据要保证演示当天 `owed ≥ 1`。**

**`pet_state` 判定**（`mock-server/engine.js`，直接复用别重写）：

```
missedDays >= 7                          → sleep   休眠
minutes >= 200 && energy < 45 && v >= 52 → tired   疲惫（学太猛，劝停）★最值钱
v >= 78                                  → vigour  元气
v >= 55                                  → steady  踏实
v >= 30                                  → wilt    蔫了
else                                     → sleep
```

**非对称活力值**（任务卡 5.3，方向不可改）：

```
completion < 0.5 → v = 0.75*prev + 0.25*(c*100)   恶化慢，断一天只是蔫一点
completion >= 0.5 → v = 0.60*prev + 0.40*(c*100)  回暖快，回来第一天就涨
```

---

## ③ `GET /api/memories` —— 记忆屏

**响应**：`{ "items": [...] }`（示例见 `memories.response.example.json`）

| 字段 | 说明 |
|---|---|
| `days_ago` | 距今天数。**必须和 seed 严丝合缝**——评委最爱抓「你这数据是编的吧」 |
| `quote` | 用户当时说的话 |
| `module` / `then_accuracy` / `week_accuracy` | 对账三件套：当时 73% → 这周 48% |
| `question` | 结尾问句，把评价权交回用户（「你当时少算了什么？」） |

---

## ④ C 的识别结果（已定稿，仅供参照）

`recognition.response.example.json` —— C 模块 r4 的输出，A 已全量接入。
11 个 warning code 见 `../4_接口契约/接口草案_C模块_识别结果JSON_v1.1_r4.md`。

---

## 已验证的两个关键场景（mock-server 实测）

| 场景 | 输入 | 输出 |
|---|---|---|
| 常规好图 | 115 分钟 / 81% / 20:30 | `vigour` + `excellent` + `稳` |
| **熬夜（最值钱那格）** | 210 分钟 / 22:40 开始 | **`tired` + `过载` + `low`** → 仓鼠说「今天别学了」 |
