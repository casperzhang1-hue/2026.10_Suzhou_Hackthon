# 前端反馈 · 对《接口草案_C模块_识别结果JSON_v1.0》的确认与补充

> 回复人：A 模块（前端 + 视觉）Suri
> 结论：**schema 骨架可用，同意按此对接**；以下 4 点请 C 模块在 v1.1 落实。

---

## 一、回答你第 7 节的三个问题

**① 字段够用吗？**
够用，不需要 `device`。`user_id` 建议加上但演示版前端会固定传 `demo_zhang`，C 模块原样透传即可，不用做逻辑。
唯一要补的说明：`event_date` 识别不到时请填 `null` 而不是猜今天——前端要靠它判断是不是旧截图。

**② warnings 枚举够吗？**
不够，缺 3 个 PRD 硬性场景，v1.1 必须补（见第二节）。

**③ encouragement 谁出话术？**
**C 只给 `level`，不给 `message`。** 理由：PRD FR-09 规定话术必须过「主语是我 + 禁用词库（加油/你一定行/坚持就是胜利…）」双重校验，这套校验在表达系统里。你给的示例「明天继续保持！」主语是"你"且带感叹号，按 FR-09 是要被拦掉的。话术如果两边都出，演示时会互相打架。
建议折中：C 模块保留话术库用于内部测试，接口里 `encouragement` 只输出 `level`；`message` 由前端从 12 条模板池按 level 取。

---

## 二、warnings 枚举需要补的 3 + 1 个

| code | 对应 PRD | 触发条件 | 前端行为 |
|---|---|---|---|
| `OLD_SCREENSHOT` | FR-03 验收（旧截图提示） | 识别到的学习时间与当前差 > 36h | 确认卡顶部黄条「这是 X 天前的记录，默认记到截图当日」 |
| `CORRECT_COUNT_INVALID` | 异常清单 #7 | 任一模块 correct_count > question_count | 该行输入框标黄，强制用户核对后才能提交 |
| `NOT_A_STUDY_SCREENSHOT` | FR-02 验收（无关图） | confidence < 0.5 且抽不到任何字段 | 不出确认卡，直接引导「换一张或手动选」（走 chips 兜底） |
| `DURATION_TOO_LONG`（建议） | FR-03 数值合理性 | duration_minutes > 600 | 时长输入框标黄 |

另外**统一置信度阈值**：你的文档写 `< 0.6` 写入 SCREENSHOT_BLURRY，PRD FR-02 的降级线是 `< 0.5`。建议统一成：`confidence < 0.5` → 输出 `NOT_A_STUDY_SCREENSHOT`（走兜底）；`0.5 ≤ confidence < 0.6` → 输出 `SCREENSHOT_BLURRY`（照常出确认卡但顶部黄条）。

---

## 三、前端按 code 的统一消费规则（写死在前端，C 不用管 UI）

| code | 拦截级别 | UI |
|---|---|---|
| OLD_SCREENSHOT | 提示 | 黄条 + 日期自动取 event_date |
| SCREENSHOT_BLURRY | 提示 | 黄条「识别得不太清楚，帮我核对一下」 |
| UNRECOGNIZED_APP | 提示 | 来源字段变下拉可选 |
| DURATION_MISSING | 提示 | 时长输入框置空待填 |
| CORRECT_COUNT_INVALID | 拦截 | 标黄 + 提交按钮禁用直至改对 |
| DUPLICATE_RECORD | 拦截 | 只给「知道了」按钮，不入库 |
| NOT_A_STUDY_SCREENSHOT | 拦截 | 不出确认卡，直接落 chips 兜底 |
| MODULE_MISMATCH | 拦截 | 整卡标黄，逐行核对 |

---

## 四、反向接口：确认卡提交（你文档没覆盖，前端定义如下）

前端确认/修改后，POST 给服务端入库。字段与你的 schema 对齐，另加三个前端职责字段：

```json
{
  "schema_version": "1.0",
  "record": {
    "source_app": "粉笔",
    "event_date": "2026-10-30",
    "event_time": "21:30",
    "duration_minutes": 35,
    "modules": [
      { "name": "言语理解", "question_count": 20, "correct_count": 16 }
    ],
    "total_questions": 35,
    "accuracy": 0.80
  },
  "recognition_ref": { "recognized_at": "2026-10-30T22:58:37+08:00", "confidence": 0.92 },
  "edited_fields": ["duration_minutes"],
  "confirmed_at": "2026-10-30T23:01:02+08:00"
}
```

- `edited_fields`：用户改过的字段名数组（PRD FR-04 / 埋点 s2_confirm 要用，修正率指标靠它）
- 重复上传由前端先挡一层（同一张图 file hash），C 的 `DUPLICATE_RECORD` 是第二道

## 五、前端消费端的最小类型（供对齐，JSDoc）

```js
/**
 * @typedef {Object} Recognition
 * @property {string} schema_version
 * @property {{recognized_at: string, confidence: number}} recognition
 * @property {string|null} source_app
 * @property {string|null} event_date      // YYYY-MM-DD
 * @property {string|null} event_time      // HH:MM
 * @property {number|null} duration_minutes
 * @property {{name: string, question_count: number, correct_count: number|null}[]} modules
 * @property {number|null} total_questions
 * @property {number|null} accuracy        // 0-1，两位小数
 * @property {{code: string, message: string}[]} warnings
 * @property {{level: 'low'|'normal'|'good'|'excellent'}} encouragement
 */
```

前端调用（真联调时把 mock 换成这一段）：

```js
const fd = new FormData();
fd.append('image', file);
const res = await fetch('/api/recognize', { method: 'POST', body: fd });
const data = await res.json();   // 即上面的 Recognition
```

---

## 六、模块名标准化（跟你确认一下）

你的枚举：言语理解 / 判断推理 / 数量关系 / 资料分析 / 常识判断 / 申论 —— **前端按这套做下拉**。
注意 PRD FR-02 写的是短名（言语/常识），冲突以更完整的你这套为准，但请把这条同步进 PRD 备忘，避免 D 做 seed 数据时用短名对不上。
