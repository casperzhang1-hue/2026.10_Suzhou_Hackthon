# 宠物对话 · 端到端验证脚本

这些脚本用 **CDP 驱动真实 Chrome**（不是 curl 模拟），因为它们要抓的问题只在真实事件层才出现——
比如对话面板被 `.dock` 盖住导致按钮点不动，直接调 `openChat()` 是测不出来的。

## 前置

```bash
# 1. 起服务
python start_fullstack.py

# 2. 起一个带调试端口的 Chrome，打开演示页
#    Windows 示例（注意 --no-proxy-server，本机有系统代理会让 CDN 走不通）
"C:/Program Files/Google/Chrome/Application/chrome.exe" \
  --remote-debugging-port=9333 \
  --no-proxy-server \
  --user-data-dir=/tmp/cdp-pet \
  http://127.0.0.1:8899/index.html
```

脚本默认连 `http://127.0.0.1:9333`，找 URL 含 `8899` 的页面。

## 四个脚本

| 脚本 | 验什么 | 期望 |
|---|---|---|
| `pet_model_chat.mjs` | 三个话题走模型链路，答案里的数字是否都在事实包白名单内 | 三个话题都标 `模型 · 数字已核对`；越界数字为空；0 异常 |
| `pet_longpress.mjs` | 真实鼠标事件：短按 120ms 不出面板、长按 900ms 出面板、点话题按钮得回答 | 短按只冒话术；长按出面板；点按钮后出现模型回答 |
| `pet_offline.mjs` | 切 CDP 离线后点话题 | 落到兜底话术，**一个数字都没有**，0 异常 |
| `pet_guard_fallback.mjs` | 注入 `verify → ok=false`，看前端是否丢弃模型回答并回退模板 | 最终显示 `来自 SQLite · …`，日志有 `[pet] 数字复核不通过` |
| `pet_chat_input.mjs` | 长按唤起 → 点输入框 → 模拟中文输入法上屏 → 回车发送 → 再点一个话题 | 引擎状态显示「团团 在线 · qwen-flash」；两次都得到模型回答且 meta 带模型名；输入框发完清空；0 异常 |

```bash
cd tools/e2e
node pet_model_chat.mjs
node pet_longpress.mjs
node pet_offline.mjs
node pet_guard_fallback.mjs
node pet_chat_input.mjs
```

## 为什么要留这几个脚本

`pet_longpress.mjs` 抓出过一个真 bug：面板挂在 `#phWrap`（带 `transform`，会新建层叠上下文）里，
`z-index:80` 被困住，底部 `.dock`(z60) 反而盖住整个面板，**按钮根本点不动**。
`pet_guard_fallback.mjs` 抓出第二个：复核不通过时只 `drop()` 流式气泡不重画，界面直接空白。

两个都是"看着对、实际不能用"的类型，只有真实事件 + 故障注入才能撞见。
改动宠物交互或模型链路后，建议四个都跑一遍。
