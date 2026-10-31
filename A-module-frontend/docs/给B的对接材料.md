# A ⇄ B 对接材料（前端侧 · 2026-10-31 15:30）

> 负责人：曹苏睿（A）｜ 对象：B（后端）｜ 状态：**A 侧已改完并构建通过，等你起服务就能联**
>
> 一句话：A 的前端已经接好 `GET /api/today`，**缺口行现在只读你返回的数据，不再硬编码**。
> 你只要把服务起起来，A 这边零改动就能连上。

---

## 一、先说结论：你已经做对的，A 这边全部对得上

我逐字段读了你的 `B-module-backend/app/service.py`，和你现在的返回**完全一致**，不用改：

| A 前端读的字段 | 你 `today_view()` 返回的 | 结果 |
|---|---|---|
| `today.pet_state` → 仓鼠五态图 | `st["pet_state"]`（vigour/steady/tired/wilt/sleep） | ✅ 对上 |
| `today.vitality` | `st["vitality"]` | ✅ |
| `today.user_state` | `st["user_state"]` | ✅ |
| `today.phrase_level` | `PHRASE_LEVEL[st["pet_state"]]` | ✅ |
| `today.gap.owed` → 缺口行文案 | `gap_of()` | ✅ |

`gap_of()` 只数「时长 > 0」的天 —— 这个口径**正是我当初修 seed 的原因**，
你写对了，请**不要改成「有记录就算完成」**，否则 `owed` 变 0，路演那句「本周欠 2 次」就没了。

---

## 二、⚠️ 唯一的坑：端口不一致

| 出处 | 端口 |
|---|---|
| 你的 `README.md` | `--port 8000` |
| D 复评时实测（`合并后复评_1510.md` 第 35 行） | **8015** |

**A 侧的处理**：不做单一常量，改成**按顺序自动探测**：

```
http://127.0.0.1:8000 → 8015 → 8787
```

第一个通的就锁定，通关后界面顶部会显示「后端 http://127.0.0.1:xxxx 已连通」。
所以**你起在哪个端口 A 都能连上**，不需要你改代码。

如果你想固定，A 侧也支持 `.env` 里写 `VITE_API_BASE=http://127.0.0.1:你的端口`
（写了就只用它，不再探测）。

**建议**：路演当天定死一个端口写进 `.env`，别依赖探测——探测只是防你临时换端口。

---

## 三、另一个必须注意的：CORS 只放 5173

你的 `main.py`：

```python
allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"]
```

**A 起前端必须用 5173**：

```bash
cd A-module-frontend/app
npm install
npm run dev        # vite 默认 5173，别带 --port 改端口
```

改了端口就是跨域失败，现场排查很浪费时间。这一条我已经写进 A 的 README。

---

## 四、联调三步（你只需要做第 1 步）

**① 你起服务**

```bash
cd B-module-backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
HAMSTER_TODAY=2026-10-31 .venv/bin/python -m uvicorn app.main:app --port 8000
```

> `HAMSTER_TODAY=2026-10-31` 请务必带上 —— 你 main.py 第 14 行支持它，
> 路演回放不随日期漂移，这是 D 复评里明确验过的一格。

**② 我起前端**（npm run dev，5173）

**③ 一起看一眼**：前端顶部显示「已连通」，走一遍 上传 → 确认 → 今日屏，
今日屏缺口行应当显示 `本周 X/5，还欠 Y 次`，且 **Y 和你 `gap_of()` 算出来的一致**。

---

## 五、验收清单（照着打勾，5 分钟）

- [ ] `curl http://127.0.0.1:8000/api/today` 返回里**有 `gap` 字段**
- [ ] 改一条记录让 `owed` 从 0 变 1 → 前端缺口行文案跟着变（数字跟数据走，不是写死的）
- [ ] 前端顶部显示「后端 … 已连通」（绿色）
- [ ] 断掉你的服务 → 前端**不白屏**，缺口行显示上次数据 + 灰色「离线 · 上次同步」标记
- [ ] `POST /api/records` 后前端立刻刷新，`week_done` +1

---

## 六、A 侧为了联调做的改动（你不必改，仅供知悉）

| 文件 | 改了什么 |
|---|---|
| `app/src/api.js` | 后端地址改自动探测（不再写死我自己的 mock 8787）；加 1.5s 超时；失败回落缓存/演示数据并打 `offline` 标记；`/api/today` 缺 `gap` 时 `console.error` 显式报警 |
| `app/src/App.vue` | 进页面就调 `fetchToday()`；入库后立刻刷新；顶部加后端连通状态指示 |
| `app/src/components/TodayScreen.vue` | **删掉硬编码缺口行**，改读 `today.gap`；形态优先用你的 `pet_state`，其次才按话术档位回落；中文/英文枚举都兼容 |

**断网红线**：拉不到数据时**显示「—」或用上次缓存 + 灰色「离线」标记**，
绝不编一个「欠 2 次」——那等于换个地方穿帮。

---

## 七、我这边还没做的（不影响你）

- 记忆屏 / 出分日屏：Vue 工程里没有（原型里有），按 D 的判断不补，演示用原型单文件版
- `GET /api/memories` 已接好，拉不到就显示「还没有记忆」，不会编造

---

## 八、有问题找谁

| 问题 | 找谁 |
|---|---|
| 接口字段 / CORS / 端口 | A（曹苏睿）——本文档 |
| 状态引擎算法对拍 | `tests/test_parity_a.py`，B 自己跑 |
| 识别结果字段（warnings / accuracy） | C（Nina），见 `C-module-recognition/docs/` |
