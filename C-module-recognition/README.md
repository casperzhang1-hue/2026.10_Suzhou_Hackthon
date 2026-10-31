# C 模块 · AI 学习截图识别（supervise-pet · C）

> 上传一张学习截图 → 云端多模态大模型识别 → 输出标准 JSON（学习数据 + 异常警告 + 鼓励等级）
> 负责人：Nina ｜ 接口版本：**v1.1-r5**（2026-10-31 12:10）｜ 状态：**验收通过，联调中**

---

## 一、这个模块做什么

| 输入 | 输出 |
|---|---|
| 一张学习截图（PNG/JPG/WEBP，≤10MB） | 标准 JSON：`source_app` / `event_date` / `event_time` / `duration_minutes` / `modules[]` / `total_questions` / `accuracy` / `warnings[]` / `encouragement.level` |

- **能识别**：粉笔、华图在线、腰果公考等考公学习 App 的练习报告 / 模考报告 / 每日一练截图
- **会拒绝**：风景照、自拍、无关图片（返回 `NOT_A_STUDY_SCREENSHOT`，前端走兜底手填页）
- **不训练、不微调**：直接调云端多模态大模型，零模型工程

## 二、文件清单

| 文件 | 作用 |
|---|---|
| **`recognize.js`** | ⭐ 核心交付物。单文件自包含，无打包、无依赖。前端 `<script>` 引入即用 |
| `index.html` | C 侧演示页（引入 recognize.js，独立可跑） |
| `encouragement.json` | 演示页内部话术库（四档等级 × 4 条） |
| `phrases.json` | 鼓励话术（A 定稿 12 条，前端用） |
| `batch-test.js` | 跑批测试脚本（Node 环境，验证任务卡硬指标） |
| `docs/接口草案_C模块_识别结果JSON_v1.1.md` | **A⇄C 接口契约（单一事实源）**，含字段表、异常码表、稳定性声明、变更记录 |

## 三、快速开始

### 3.1 前端接入（A 模块用，3 行代码）

```html
<script src="recognize.js"></script>
<script>
  // file 来自 <input type="file"> 或拖拽；userId 演示期固定 "demo_zhang"
  const result = await window.recognizeScreenshot(file, "demo_zhang");
  // result 永远是完整标准对象：不抛异常、不是 null
</script>
```

### 3.2 本地跑演示页

不能直接双击 `index.html`（`file://` 协议会拦截 `fetch` 话术库）。起一个静态服务：

```bash
cd C-module-recognition
python -m http.server 8000
# 浏览器访问 http://localhost:8000
```

### 3.3 跑批测试（验证识别质量）

```bash
node batch-test.js "你的截图目录"
```

输出每张图的等级 / 来源 / 时长 / 题量 / 正确率 / 警告 / 耗时 + 汇总。

**最新一轮实测（11 张真实学习截图，2026-10-31 12:10）**：
`11/11 出合法 JSON，失败 0，平均 6.9s（最快 2.4s / 最慢 12s）` —— 任务卡要求 6 张至少 5 张，已超额达标。

## 四、核心设计决策（改代码前必看）

1. **等级是本地硬算的，不信任模型返回的 level**
   模型曾把「95% 正确率 + 17 分钟」误判成 excellent。本地 `calcLevel()` 按固定阈值算：
   `excellent`(正确率>0.8 且时长≥30分) / `good`(0.6~0.8 且≥20分) / `low`(<0.4 或<10分) / `normal`(其余)

2. **话术完全在前端，接口只传 level**
   `encouragement` 只有 `{level}` 一个字段，不输出 message。话术从 `phrases.json` 取，A 可预审整句。

3. **永不抛异常，永不返回 null**
   任何失败（超时 / 断网 / 非学习图 / 格式不符）都返回结构完整的标准对象 + 相应 warning，
   前端的等待态永远不会被卡死。20 秒超时、不重试（重试对偶发慢响应收效低且翻倍最坏耗时）。

4. **识别结果是概率输出，不是确定性输出**
   同一张图两次调用可能读出不同数字（实测：某张图两轮分别为「正确率 null / normal」
   与「81% / excellent」）。**所以：确认卡字段必须允许用户手改，演示必须有录屏兜底。**

5. **密钥安全**
   前端只有 `publishableKey`（公开标识、无权限），真实密钥由 WorkBuddy 云平台托管，
   本仓库中不含任何私密密钥。

## 五、已知边界（不是 bug，别乱报）

| 现象 | 说明 |
|---|---|
| 旧截图挂 `OLD_SCREENSHOT` 黄条 | 设计如此：学习记录距今 >36 小时就提示。**演示必须用当天/昨天的新截图** |
| 正确率为 `null` | 截图上没写正确率，或没读到。确认卡应显示「—」，**不能显示 0%** |
| `UNRECOGNIZED_APP` | 截图页面本身没有 App 名（如小程序答题卡），忠实于数据 |
| `DURATION_TOO_SHORT` | 截图本身显示用时 0~4 分钟，忠实于数据 |
| >10MB 图返回 `NOT_A_STUDY_SCREENSHOT` | 建议前端按 `file.size` 前置拦截，提示「图片太大」更贴切 |
| 耗时波动 2~14s | `auto` 是路由模型，响应本身有波动。**材料引用耗时写区间，不写单点值** |

## 六、文档与版本约定

1. **接口契约单一事实源**：`docs/接口草案_C模块_识别结果JSON_v1.1.md`
   ——字段含义、异常码、等级规则、耗时口径、稳定性声明全部以它为准
2. **改动必记变更记录**：任何 `recognize.js` 改动，同步在接口文档的「变更记录」表加一行
   （版本号 / 时间 / 改了什么 / 为什么）
3. **A 侧升级只需覆盖一个文件**：把新版 `recognize.js` 覆盖 `app/public/recognize.js`，
   前端代码零改动（接口字段、结构、调用方式不变）
4. **版本号规则**：`v1.1-rN`，rN 递增；字段/结构变更升主版本，逻辑修复升 rN

## 七、版本历史（摘）

| 版本 | 改了什么 |
|---|---|
| v1.1-r1 | SDK 锁定具体版本（防上游 breaking change）；话术定稿 |
| v1.1-r2 | 超时 15s+重试 → **20s 单次不重试**（跑批发现误杀正常图） |
| v1.1-r3 | accuracy 三态同源；duration 取整（修「8分47秒」读成 8.47） |
| v1.1-r4 | 契约自洽（level="" 必带 NOT_A_STUDY_SCREENSHOT）；accuracy 百分制归一 |
| **v1.1-r5** | Prompt 修耗时 mm:ss 误读（01:44→104 分钟）、修显眼百分比漏读 |

完整变更记录见接口文档末表。

## 八、验收状态

- ✅ A 模块 v1.1 验收通过（接口 10 题全部对齐）
- ✅ 跑批验收 10/10 合法 JSON、非学习图正确拒绝、0 失败
- ✅ 云服务链路（免密钥 publishableKey）验证通过
- ⏳ 11:30 起与 A 前端真链路联调中
