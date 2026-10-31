# 监督小宠 · C 模块联调说明（v1.1-r3）

> 发件：C 模块（学习截图识别）
> 收件：A 模块（前端／Suri）
> 时间：2026-10-31 10:37
> 状态：**接口侧已完成，10 张真实截图跑批 10/10 通过，可直接进联调**

---

## 一、30 秒看懂

一个函数搞定：

```js
const result = await window.recognizeScreenshot(file, "demo_zhang");
```

- **永远 resolve，不 reject、不 throw、不返回 null** —— 你不需要写兜底分支
- 返回值永远是结构完整的 JSON 对象，按 `warnings[].code` 判断成功/异常即可
- 耗时：平均 5.4~5.7s，最慢 11.6s（实测 10 张），**等待态按 20~25 秒设计**

---

## 二、包里有什么

| 文件 | 你要不要动 | 说明 |
|---|---|---|
| `recognize.js` | ✅ **覆盖** `app/public/recognize.js` | 识别能力本体，唯一需要替换的文件 |
| `phrases.json` | 已定稿，供复核 | 12 条话术终稿（每档 3 条） |
| `接口草案_C模块_识别结果JSON_v1.1.md` | 查阅 | 完整接口定义、字段、枚举 |
| `batch-test.js` | 可选 | Node 跑批脚本，你想自己复跑验收时用 |
| `README_联调说明.md` | 本文件 | 接入 + 验证清单 |

**SDK 不用你管**：`recognize.js` 会自己动态注入 WorkBuddy Cloud SDK（已锁定版本
`0.1.4-dev.ca27990.202610161713`，不用 `@dev` 浮动标签，路演当天不会被上游变更打中）。

---

## 三、三步接入

### 第 1 步：放文件

把 `recognize.js` 覆盖到 `app/public/recognize.js`（Vite 原样伺服，不打包）。

### 第 2 步：引入

在你的 `index.html` 里加一行：

```html
<script src="/recognize.js"></script>
```

### 第 3 步：调用

```js
// file 是 <input type="file"> 拿到的 File 对象
const result = await window.recognizeScreenshot(file, "demo_zhang");

// 判断是否识别成功
const isStudyShot = !result.warnings.some(w => w.code === "NOT_A_STUDY_SCREENSHOT");

if (!isStudyShot) {
  // 非学习图片：显示友好提示，不要出确认卡
  showToast("这张图片暂时没有识别到学习数据，请上传学习记录或刷题截图。");
  return;
}

// 正常学习截图：出确认卡
renderConfirmCard(result);
```

> `userId` 演示期固定传 `"demo_zhang"`，C 原样透传不做任何逻辑。

---

## 四、联调验证清单（勾完就算通）

| # | 验证项 | 期望结果 |
|---|---|---|
| 1 | 传一张**正常学习截图** | 返回对象，`schema_version === "1.1"`，`encouragement` 只有 `level` |
| 2 | 传一张**非学习图**（猫/风景/聊天） | 返回对象 + `NOT_A_STUDY_SCREENSHOT`，**页面友好提示不白屏** |
| 3 | 传**超大图**（>10MB）或**非图片格式** | 返回标准对象 + `NOT_A_STUDY_SCREENSHOT`，不崩 |
| 4 | **断网**后点识别 | 返回标准对象，提示"云服务初始化失败/识别失败"，不卡死等待态 |
| 5 | 看 `_elapsed_ms` | 落在 2.5s ~ 11.6s 区间，平均 5.4~5.7s |
| 6 | 模块不全的截图 | `accuracy` 与逐模块行一致，确认卡**不自相矛盾** |
| 7 | 学习时长显示 | 一定是**整数分钟**（不会出现 8.47 这种小数） |

第 2、3、4 项是重点——**任何情况都不能白屏或卡死**。

---

## 五、本次 r3 改了什么（相对你工程里的 r2）

**接口字段、结构、调用方式一个字没动**，你前端代码不用改，只需覆盖 `recognize.js`。

| # | 改动 | 来源 |
|---|---|---|
| 1 | **accuracy 边界补齐**：`total_questions` 为 `null` 时也本地重算 | 你的 P2 建议，已采纳 |
| 2 | **duration_minutes 取整**：修掉模型把「8分47秒」误读成 `8.47` 的穿帮 | C 跑批新发现 |
| 3 | **耗时口径统一为区间**：平均 5.4~5.7s / 最慢 10~11.6s | 你指出的口径不一致 |

### 改动 1 说明

原来 `total_questions` 为 `null` 时，总题量会用模块和回填，但 accuracy 走另一分支保留模型值，
导致确认卡出现「总题量 40、正确率 90%，但逐模块行加起来才 50%」的自相矛盾。

现在改成：

```js
} else if (declared === null || sumQuestions === declared) {
```

**总题量与正确率永远来自同一套数据**，确认卡不会打架。

### 改动 2 说明

实测发现模型偶尔把截图上的「8 分 47 秒」读成小数 `8.47`（把秒当小数位），
确认卡显示「学习时长 8.47 分钟」明显穿帮。已在 C 侧四舍五入取整，
误差 1 分钟内，对鼓励等级阈值（10 / 20 / 30 分钟）无影响。

---

## 六、已知边界（不是 bug，别当 bug 报）

| 现象 | 原因 | 处理建议 |
|---|---|---|
| `source_app` 为 `null` | 部分截图来自拼多多小程序、带小红书水印，**本身就没有 App 标识** | 显示「未知来源」或留空，不要强制填 |
| `MODULE_MISMATCH` 警告 | 截图只露出部分模块，模块题量和 ≠ 总题量 | 正常现象，可提示用户"补充完整截图" |
| `OLD_SCREENSHOT` 警告 | 截图学习时间距今 > 36 小时 | 正常。**路演请用当天的截图**，否则一直黄条 |
| `DURATION_TOO_SHORT` | 截图本身显示「用时 0 秒」（App 计时异常） | 忠实于截图数据，不是识别错误 |
| `accuracy` 为 `null` | 该次学习无正确数（多为申论） | 不出正确率展示，不要显示 0% |

---

## 七、接口速查

### 返回结构

```json
{
  "schema_version": "1.1",
  "user_id": "demo_zhang",
  "recognition": { "recognized_at": "2026-10-31T10:30:00+08:00", "confidence": 0.93 },
  "source_app": "粉笔",
  "event_date": "2026-10-30",
  "event_time": "21:30",
  "duration_minutes": 17,
  "modules": [
    { "name": "资料分析", "question_count": 20, "correct_count": 19 }
  ],
  "total_questions": 20,
  "accuracy": 0.95,
  "warnings": [],
  "encouragement": { "level": "normal" },
  "_elapsed_ms": 5446
}
```

> `_elapsed_ms` 是**调试字段，非契约**，可忽略或删掉。

### 鼓励等级枚举

`low` / `normal` / `good` / `excellent`，非学习图片时为**空串 `""`**。

话术由前端从 `phrases.json` 按 level 取，C 只给 level。

### warnings 异常码

| code | 含义 |
|---|---|
| `NOT_A_STUDY_SCREENSHOT` | 非学习图片 / 识别失败 / 不合规图片（**走兜底，不出确认卡**） |
| `SCREENSHOT_BLURRY` | 置信度 0.5~0.6，照常出确认卡，顶部黄条 |
| `OLD_SCREENSHOT` | 学习时间距今 > 36 小时 |
| `DURATION_TOO_SHORT` | 时长 < 5 分钟 |
| `DURATION_TOO_LONG` | 时长 > 600 分钟 |
| `DURATION_MISSING` | 未识别到学习时长 |
| `ACCURACY_TOO_LOW` | 正确率 < 0.4 |
| `MODULE_MISMATCH` | 模块题量之和 ≠ 总题量 |
| `CORRECT_COUNT_INVALID` | 某模块正确数 > 题量 |
| `UNRECOGNIZED_APP` | 未识别到来源 App |
| `DUPLICATE_RECORD` | 预留字段，**本期永不触发**（去重在你前端做） |

---

## 八、出问题怎么办

| 现象 | 先查 |
|---|---|
| 报 `recognizeScreenshot is not a function` | `recognize.js` 没加载成功，检查 `<script src="/recognize.js">` 路径 |
| 一直卡在等待态 | 检查是否断网；C 承诺永远 resolve，20 秒内一定返回 |
| 返回 `NOT_A_STUDY_SCREENSHOT` 但明明是学习图 | 大概率是超时或图片糊，换一张清晰截图重试；把 `_elapsed_ms` 发我 |
| 确认卡数据自相矛盾 | 把 `modules` / `total_questions` / `accuracy` 三项发我，我核对 |

**联系方式**：直接群里 @ 我，附上报错截图 + 那张测试图，我这边有完整跑批环境，能立刻复现。

---

## 九、时间与下一步

| 时间 | 事项 |
|---|---|
| 现在 | 你覆盖 `recognize.js`，提前看这份说明 |
| 11:30 | 切 `USE_MOCK = false`，用真实学习截图跑通「上传 → 识别 → 确认卡 → 仓鼠变化」 |
| 12:30 前 | 全链路跑通 |

**C 侧已完成**：10 张真实学习截图 10/10 出合法 JSON（任务卡要求 ≥5/6），
超时与正确率两个真问题已修复，识别侧可结项，随时配合联调。
