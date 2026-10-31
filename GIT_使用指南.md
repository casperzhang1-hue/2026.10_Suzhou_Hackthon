# Git 使用指南（9 小时冲刺版）

> 原则：**能照抄、不思考、出了错 1 分钟内回得来。**
> 仓库：`https://github.com/casperzhang1-hue/2026.10_Suzhou_Hackthon`

---

## 一、第一次上手（每人只做一次，5 分钟）

```bash
# 1. 克隆
git clone https://github.com/casperzhang1-hue/2026.10_Suzhou_Hackthon.git
cd 2026.10_Suzhou_Hackthon

# 2. 报上名号（提交记录会显示你是谁）
git config user.name "你的名字"
git config user.email "你的邮箱"

# 3. 验证
git status
```

> 第一次推送时浏览器/终端会要你登录 GitHub——用你的账号授权即可。

---

## 二、日常动作：只会这三条就够了

每完成**一个小功能**（比如：确认卡加了一个字段、话术改了一条、seed 补了一天的数据）：

```bash
git add .                              # 收集你改的文件
git commit -m "B: 完成 POST /api/records 入库接口"
git pull --rebase                      # 拉一下别人的进度
git push                               # 推上去
```

**提交信息格式**：`人名缩写: 干了什么`，例如：

- `A: 确认卡支持 accuracy 为空时显示 —`
- `C: r4 prompt 增加申论 correct_count=null 说明`
- `B: today 接口补 gap 缺口行`
- `D: seed 45 天版，承诺句落 D5`

**频率要求：至少每 40 分钟 commit 一次。** commit 不需要完美，它是存档点，不是作品。

---

## 三、为什么不用分支（这是故意的）

9 小时 + 4 个人，**合并冲突比代码 bug 更耗时间**。我们的防冲突手段是**目录隔离**：

| 人 | 只能改 |
|---|---|
| A | `02_frontend_A/` |
| C | `03_ai_C/` |
| B | `04_backend_B/` |
| D | `00_docs/`、`05_seed_D/` |

目录不重叠 → 大家都推 main 也不会冲突 → 不需要 merge、不需要 PR、不需要 branch。

**例外**：A 要临时试一个大的界面重构？开个分支：

```bash
git switch -c a/experiment     # 开实验分支
# ...随便改，改坏了删掉重来
git switch main                # 回主线，主线毫发无损
git branch -D a/experiment     # 不要了就删
```

---

## 四、回退手册（背下来前三条）

### 场景 1：改坏了文件，还没 commit

```bash
git restore 文件名          # 单个文件回到上次 commit 的样子
git restore .               # 整个目录全回去（慎用，会丢掉所有未提交修改）
```

### 场景 2：commit 了，还没 push，反悔了

```bash
git reset --soft HEAD~1     # 撤销这次 commit，改动还留在手里重新改
git reset --hard HEAD~1     # 彻底扔掉这次 commit（改动也没了）
```

### 场景 3：改乱了，想回到某个"存档点"（tag）

```bash
git tag                     # 看所有存档点
git reset --hard g3-pass    # 整个仓库回到 G3 通过那一刻
```

### 场景 4：已经 push 出去了才发现有问题

```bash
git revert HEAD             # 生成一个"反向提交"抵消上一笔，历史保留，最安全
git push
```

❌ **永远不要** `git push --force`——会把别人的提交抹掉。4 个人的仓库，force push 等于清空别人的工作。

### 场景 5：手滑删了文件 / 整个目录

```bash
git checkout -- .           # 工作区被删的文件全部从 git 里恢复
# 只要 commit 过的东西，永远找得回来——这就是我们用 git 的原因
```

---

## 五、Tag 存档点纪律（D 负责打，关键节点必打）

| 时机 | 命令 | 意义 |
|---|---|---|
| 现在（初始归档） | `git tag v0-baseline` | 一切的开端 |
| G2 真链路通过 | `git tag g2-pass` | 真截图→宠物变 |
| G3 五步动线通 | `git tag g3-pass` | **最重要**，16:00 后任何改坏都能回到这 |
| 18:00 冻结 | `git tag g4-frozen` | 之后只许改文案 |
| 路演物料齐 | `git tag final` | 上台版本 |

```bash
git tag g3-pass             # 打 tag
git push --tags             # tag 也要推，不然只有本地有
```

---

## 六、三条禁令

1. ❌ **不要 force push**（`--force` / `-f`）
2. ❌ **不要动别人的目录**（想改就当面说，让人家自己改）
3. ❌ **不要提交密钥和大文件**（API key、node_modules、>10MB 的文件）——已经写进 `.gitignore`，别绕过它

---

## 七、出事了找谁

- push 冲突 / 卡住 → 直接在群里喊，别自己琢磨超过 10 分钟
- `git status` 看不懂 → 截图发群里
- 最坏情况：仓库炸了 → 本地任何一份 clone 都是完整备份，重建即可，**只要 push 过的东西永远不会丢**
