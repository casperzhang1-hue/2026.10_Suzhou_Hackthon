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
| `pet_longpress.mjs` | 真实鼠标事件：短按 120ms 不出面板、长按 900ms 出面板、点话题按钮得回答 | 短按只冒话术；长按出面板；点按钮后出现模型回答 |
| `pet_offline.mjs` | 切 CDP 离线后点话题 | 落到兜底话术，**一个数字都没有**，0 异常 |
| `pet_chat_input.mjs` | 长按唤起 → 点输入框 → 模拟中文输入法上屏 → 回车发送 → 再点一个话题 | 引擎状态显示「团团 在线 · qwen-flash」；两次都得到模型回答且 meta 带模型名；输入框发完清空；0 异常 |
| `pet_see_image.mjs` | 传真图（`DOM.setFileInputFiles`）→ 确认入库 → 它看完图说话 → 追问「你怎么知道」 | 面板出现「这张我看了，判断推理 15 题对 9 题，23 分钟」《看图 · gpt-4o-mini》；追问回答出处是「你刚给我看的那张图」；0 异常 |

## 踩过的坑

- **面板会盖住上传 sheet 的确认按钮**：`.pchat` 是 fixed 覆盖层，面板开着点确认，
  鼠标事件落在 `.pchat-mask` 上，`POST /api/records` 根本没发出去，界面上却看不出来。
  脚本里先收起面板再上传——`pet_see_image.mjs` 注释里写了这事。
- **点按钮前先问 `elementFromPoint` 落点**：否则点偏了会顺手触发别的按钮
  （实测点偏到「今天没学」，库里立刻多出一条 58 分钟的记录）。
- **开面板要长按 900ms，不是单击**：单击只让它冒一句话。

```bash
cd tools/e2e
node pet_longpress.mjs
node pet_offline.mjs
node pet_chat_input.mjs
```

## 为什么要留这几个脚本

`pet_longpress.mjs` 抓出过一个真 bug：面板挂在 `#phWrap`（带 `transform`，会新建层叠上下文）里，
`z-index:80` 被困住，底部 `.dock`(z60) 反而盖住整个面板，**按钮根本点不动**。
「复核不过就回退」这类故障注入改成后端单测了（`tests/test_pet_persona.py::test_接口_两次都说错话就退回兜底`），
因为闸现在在后端，从前端注入已经测不到它。

两个 bug 都是"看着对、实际不能用"的类型，只有真实事件 + 故障注入才能撞见。
改动宠物交互或模型链路后，三个脚本都跑一遍，再跑一次 pytest。
