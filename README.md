# 监督小宠 · 2026.10 苏州黑客松

> AI 学习监督助手：拍一张学习截图 → AI 识别学习数据 → 宠物养成式鼓励反馈
> 定位一句话：**卖督学，用陪伴交付（仓鼠五态），靠记忆锁住。别人用规则督你，我们用关系督你。**

**往下滚就是完整的部署与演示手册**：环境准备 → 启动 → 自检 → 3 分钟演示剧本 → 翻车预案，每一条命令都实测过。

## 模块地图

| 模块 | 职责 | 入口 |
|---|---|---|
| A · 前端 | 上传 → 确认卡 → 今日屏 / 记忆屏 / 出分日屏，宠物五态 | [`A-module-frontend/`](A-module-frontend/) |
| B · 后端与状态引擎 | FastAPI + SQLite，`/api/records` `/api/today` `/api/memories`，宠物对话（**315 个测试通过**） | [`B-module-backend/`](B-module-backend/) |
| C · AI 学习截图识别 | 识别截图中的学习数据，输出标准 JSON + 鼓励等级（v1.1-r6，SDK 已内嵌） | [`C-module-recognition/`](C-module-recognition/) |
| D · 数据与素材 | seed.json（45 天）、路演逐字稿、pitch.pdf | [`D-module-materials/`](D-module-materials/) |

- 需求与验收 → [`docs/考公陪跑Agent_PRD_v1.1.md`](docs/考公陪跑Agent_PRD_v1.1.md)
- 它说话的规矩 → [`docs/宠物对话约束清单.md`](docs/宠物对话约束清单.md)（11 类问题 + 19 条禁令，每条都有测试断言）
- 架构与接口 → [`FULLSTACK_DEMO.md`](FULLSTACK_DEMO.md)
- 同一份手册的独立文件 → [`使用手册.md`](使用手册.md)

> seed 数据唯一源：`D-module-materials/seed.json`。B 的库用 `D-module-materials/tools/seed_to_backend.py` 生成（格式不同，不能直接拷）。

---

> 面向"刚拿到这个仓库的人"。照着做，10 分钟内能跑起来，照着第 4 节演，3 分钟讲完。
> 手册里每一条命令都在 Windows 11 / Python 3.13 上实测过；没实测的会明确标"未验证"。

---

## 0. 一分钟看懂它是什么

**一句话**：拍一张学习截图 → AI 读出今天学了多久、对了几题 → 一只叫团团的仓鼠用记住的旧事陪你说话。

三个能当场演示的点：

| 点 | 凭什么说它是真的 |
|---|---|
| 数据真进库 | 右上角徽章从 `44 条记录` 变成 `45 条`，SQLite 文件就在 `B-module-backend/data/hamster.db` |
| 它真记得 | 首页主动开口"41 天前你说「资料分析我一定能拿下」"——这句话在 `memories` 表里，不是写死的文案 |
| 它不撒谎 | 把后端停掉再问它，它只说"账本连不上，弱项我不敢瞎说"，**一个数字都不编** |

---

## 1. 环境准备

只需要 **Python 3.10 及以上**（开发用 3.13）。前端是纯静态页，不用 Node、不用打包。

```bash
python --version        # 3.10+ 即可
```

### 1.1 装依赖（第一次必做）

仓库里没有虚拟环境（`.venv` 不入库），所以 clone 下来要先装：

```bash
cd B-module-backend
python -m venv .venv                          # 建一个虚拟环境（可选但推荐）
.venv\Scripts\python.exe -m pip install -r requirements.txt    # Windows
# .venv/bin/python -m pip install -r requirements.txt           # macOS / Linux
```

> 装完会在 `B-module-backend/.venv/` 下。一键脚本会自动找它，找不到就用系统 Python。
> 依赖只有 6 个（fastapi / httpx / pydantic / pytest / starlette / uvicorn），装不上多半是网络问题，
> 换个源重试：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 1.2 配大模型（可选，但演示效果差很多）

不配也能跑——它会落回"模板嘴"，答得朴素但不崩、不编数（见第 5.1 节）。
要它真开口说话，复制一份配置：

```bash
cd B-module-backend
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

然后编辑 `.env`，填三行：

```ini
PET_LLM_BASE_URL=https://api.openai-next.com/v1
PET_LLM_MODEL=qwen-flash
PET_LLM_API_KEY=sk-你的key
```

只要服务商兼容 OpenAI 的 `/v1/chat/completions` 都能填（Ollama / vLLM / LM Studio / 中转站均可，
`.env.example` 里有各家写法）。**`.env` 已在 .gitignore 里，不会误提交。**

---

## 2. 启动

### 2.1 一键启动（推荐）

```bash
python start_fullstack.py
```

它会同时起两个服务并自动打开浏览器：

| 服务 | 地址 | 说明 |
|---|---|---|
| 后端 API | <http://127.0.0.1:8000> | FastAPI + SQLite |
| 前端页面 | <http://127.0.0.1:8899/index.html> | 演示主页面 |

按 `Ctrl+C` 一次关掉两个。加 `--no-open` 则只起服务不弹浏览器。

脚本会把"今天"钉死成 **2026-10-31**（`HAMSTER_TODAY`），路演回放不会因为系统日期变了就对不上。

### 2.2 手动启动（等价，便于排查）

```bash
# 终端 1 —— 后端
cd B-module-backend
HAMSTER_TODAY=2026-10-31 .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2 —— 前端
cd A-module-frontend
python -m http.server 8899 --bind 127.0.0.1
```

Windows 的 cmd 里没有 `HAMSTER_TODAY=xxx` 这种写法，改用：

```bat
set HAMSTER_TODAY=2026-10-31 && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

### 2.3 第一次启动会发生什么

数据库是空的（`hamster.db` 不入库），**后端启动时会自己导入种子数据**，不用手动初始化。
实测空库启动后的结果：

```
44 条记录 / 3 条记忆 / 累计 2549 分钟 / 2026-09-17 ~ 2026-10-30
```

想回到干净状态：删掉 `B-module-backend/data/hamster.db`（连同 `-shm` / `-wal`），重启即重新导入。

---

## 3. 确认它真的起来了

按顺序自检，三步：

```bash
# ① 后端活着吗
curl http://127.0.0.1:8000/api/health
# 期望看到 "records":44

# ② 前端活着吗
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8899/index.html
# 期望 200

# ③ 回归测试（改过代码才需要跑）
cd B-module-backend && .venv\Scripts\python.exe -m pytest -q
# 期望 315 passed
```

页面上再看一眼：**右上角徽章显示 `SQLite 已连接 · 44 条记录`** —— 这条亮了，全栈就通了。
徽章若显示"离线演示数据"，说明后端没连上，页面会用本地数据兜底（不白屏），按第 5 节排查。

---

## 4. 演示剧本

### 4.1 标准版（3 分钟，讲清主链路）

| 步 | 操作 | 嘴里说什么 | 屏幕上会发生什么 |
|---|---|---|---|
| 1 | 打开首页 | "它已经知道我这周做到哪了——5 天目标还欠 2 次，今天还没记" | 宠物"踏实"态，面板显示 `本周 3/5 天 · 还欠 2 次`；今天那栏是空的 |
| 2 | 点「传今天的截图」，选 `C-module-recognition/test/test12_粉笔_1031_判断推理.jpg` | "拍一张截图，它自己读——不用手填" | C 模块真识别，约 3–8 秒后出确认卡：判断推理 / 15 题 / 对 9 题 / 23 分 51 秒 |
| 3 | 点「没问题，记下」 | "一条记录进库，缺口当场就变了" | 本周 3/5 → **4/5，还欠 1 次**；右上角徽章 44→45 |
| 4 | 打开 <http://127.0.0.1:8000/api/health> 或 `/api/stats` | "数据是真在 SQLite 里，不是前端假装的" | 看到 `records:45`、五个模块正确率、7 天趋势 |
| 5 | 戳一下宠物 | "它还会理我" | 弹一下、说一句；连戳 3 下摸头；连戳 6 下转身 + "再戳我要生气了。" |

### 4.2 宠物版（30 秒，建议单拎出来演——这段别人抄不走）

1. 首页它**主动开口**："41 天前你说「资料分析我一定能拿下」，那时候 73%，这周 48%。"
   （数据真在 `memories` 表里，不是写死的文案）
   ——若这次没开口，是今天的开口配额用过了；按第 5.5 节删库重来即可重现
2. **长按**宠物 800ms 弹出「跟它说两句」（短按只冒一句话，不出面板）
3. 点「我哪里最毛」→ 它答"数量关系最弱，历史累计正确率才 52%。资料分析你也得留神，这周只有 48% 了。"
4. 数字后面标 `模型 · 数字已核对`；评委追问时开 `/api/pet/context?intent=weak` 给他看事实包
5. **绝杀**：把后端停掉（Ctrl+C）再点一次话题 → 它说"账本连不上，弱项我不敢瞎说。"
   ——断网时一个数字都不编，这是设计出来的

### 4.3 追问预案（评委大概率会问的三句）

| 他问 | 你会看到 | 该怎么接 |
|---|---|---|
| "它怎么知道我学了多久？" | "你刚给我看的那张图，上面写着 23 分钟呢" | 这是 `provenance` 模式：所有数字必须指得出出处，指不出就不许说 |
| "我到底叫什么来着？" | "林一呀，我记着呢"（前提是演示中说过"我叫林一"） | 名字存在 `memories`，没存过就老实说不知道，**不编** |
| "我们刚才说了什么？" | "你刚才说模考崩了，我回你别急，我在这儿呢" | 这是 `recap` 模式：复述最近两轮，连问三遍会换个说法，不会原句重播 |

想证明它不复读，**连问三遍**同一个问题：三句三种说法，数字一个没错、句子一句不重。

### 4.4 演示前的小准备

- **先自己跑一遍**：第一次调模型有冷启动延迟，正式演之前先问一句预热。
- **把截图放在桌面**：选文件窗口里能一秒找到，别当场翻目录。
- **准备一张离线兜底的说法**：万一现场没网，直接走第 4.2 步第 5 条，把"它不撒谎"演成卖点而不是事故。

---

## 5. 翻车预案

### 5.1 模型连不上（最常见）

**现象**：它答得朴素、句子短，`source` 是 `fallback`。
**实测结论**：不会崩、不会报 500、不会编数字。接口照样返回 `ok:true`。
**处理**：继续演。观众察觉不到切换，只会觉得"它这次答得简洁了点"。模型调用有 6s / 14s 两级超时自动降级。

### 5.2 端口被占用

**现象**：启动时报 `Address already in use` 或 `error while attempting to bind`。
**处理**：

```bash
netstat -ano | findstr :8000        # 找到占用者的 PID（最后一列）
taskkill /PID <那个PID> /F
```

不想杀进程就换端口：`start_fullstack.py` 里的 `PORT_API` / `PORT_WEB` 改掉即可（第 21–22 行）。

### 5.3 页面显示"离线演示数据"

说明前端没连上后端。按顺序查：

1. 后端还活着吗 —— 开 <http://127.0.0.1:8000/api/health>
2. 是不是 8000 端口错了 —— 起后端时的 `--port` 要和前端脚本里的一致
3. 代理环境 —— 本机若有 `http_proxy`，curl 测接口要加 `--noproxy '*'`，浏览器也可能被代理拦

### 5.4 日期不对，首页显示"今天还没记录"

演示数据的时间轴钉在 **2026-10-31**。不设 `HAMSTER_TODAY` 就会取系统当天，数据对不上。
一键脚本已经处理好了；手动启动记得带上那个环境变量。

### 5.5 数据被玩坏了

删库重来：

```bash
del B-module-backend\data\hamster.db B-module-backend\data\hamster.db-shm B-module-backend\data\hamster.db-wal
python start_fullstack.py
```

---

## 6. 给别人看（局域网 / 别的电脑）

默认只监听 `127.0.0.1`，别人访问不到。要让同伴的电脑也能开：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m http.server 8899 --bind 0.0.0.0
```

---

## 7. 目录说明

| 目录 | 是什么 |
|---|---|
| `A-module-frontend/` | 前端原型（纯静态，`index.html` 是入口，真读 `/api/today`、真写 `/api/records`） |
| `B-module-backend/` | FastAPI 后端 + SQLite + 状态引擎 + 宠物对话（`app/`）、测试（`tests/`） |
| `C-module-recognition/` | 学习截图识别（`recognize.js`，纯前端跑，识别结果 JSON 接口 v1.1） |
| `D-module-materials/` | 素材：种子数据、路演稿、pitch.pdf |
| `docs/` | PRD、验收清单、**宠物对话约束清单** |
| `start_fullstack.py` | 一键启动脚本 |

想改它说话的方式，看 `docs/宠物对话约束清单.md`——那是唯一的事实源，11 类问题、19 条禁令，
每一条都有对应的测试断言（改完跑 `pytest` 就知道有没有破坏约定）。

---

## 8. 接口速查

| 接口 | 作用 |
|---|---|
| `GET /api/health` | 健康检查：记录数、天数、总分钟（自检和给评委看都用它） |
| `GET /api/today` | 今日状态：是否记录、分钟、正确率、本周进度、五模块 |
| `POST /api/records` | 写一条记录 |
| `GET /api/stats` | 聚合：五模块正确率 + 7 天趋势 |
| `GET /api/memories` | 它记住的事 |
| `POST /api/pet/say` | 跟它说话（返回 `facts.mode` 和 `guard.reason`，排查全靠这两个） |
| `GET /api/pet/context?intent=weak` | 看它答这句话时手上有什么事实包 |

觉得它答错了，先看 `POST /api/pet/say` 返回的 `facts.mode`——立刻能分清是**判错了类**
（要改分类判定）还是**判对了但被闸打回**（`guard.reason` 会说明是哪一条）。
