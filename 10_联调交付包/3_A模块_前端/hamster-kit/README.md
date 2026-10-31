# 仓鼠五态素材包 v1.0

透明背景 WebP + 纯 CSS 动效，整目录丢进 GitHub，用 jsDelivr CDN 全团队统一调用。

> 五张图合计 231 KB，解锁件 4 张 246 KB。图片是 512×512 真透明 WebP，显示 240px 时约等于 @2.1x。
> **不要用 JPEG**（没有透明通道），**不要用 GIF**（1-bit alpha 毛边 + 256 色糊）。

---

## 一、目录结构

```
hamster-kit/
├─ hamster.css          五态切图 + 微动效（核心，必须引）
├─ hamster.js           可选封装：C 模块 level → 状态
├─ index.html           本地预览页（切态 / 深浅背景 / 生成 CDN 链接）
├─ README.md
└─ img/
   ├─ hamster_01_yuanqi.webp    元气
   ├─ hamster_02_tashi.webp     踏实
   ├─ hamster_03_pibei.webp     疲惫
   ├─ hamster_04_nianle.webp    蔫了
   ├─ hamster_05_xiumian.webp   休眠
   └─ unlock/                   羁绊解锁件（帽子 ×2 / 围巾 ×2）
```

---

## 二、三步传到 GitHub

```bash
# 1. 建仓库（GitHub 网页上建，名字随便，比如 hamster-assets），然后：
cd hamster-kit
git init
git add -A
git commit -m "仓鼠五态素材包 v1.0"

# 2. 关联并推送
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git branch -M main
git push -u origin main

# 3. 打 tag 锁版本（重要：CDN 引用锁 tag，之后更新图片不会突然变了）
git tag v1.0.0
git push origin v1.0.0
```

> 仓库必须是 **public**，jsDelivr 才能访问。

---

## 三、怎么引用

把下面三段里的 `<user>` `<repo>` `<tag>` 换成你的（预览页 `index.html` 里填仓库名会自动生成）：

```html
<!-- ① 引 CSS：图片用相对路径，CDN 会自动解析到同目录的 img/ -->
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/gh/<user>/<repo>@v1.0.0/hamster-kit/hamster.css">

<!-- ② 放一个 div，改 data-state 就切态 -->
<div class="hamster" data-state="yuanqi" style="--hamster-size:240px"></div>

<!-- ③ 可选：引脚本，用 C 模块的识别结果直接切态 -->
<script src="https://cdn.jsdelivr.net/gh/<user>/<repo>@v1.0.0/hamster-kit/hamster.js"></script>
<script>
  HamsterKit.setFromRecord(document.querySelector('.hamster'), rec);
</script>
```

**不用 JS 也完全能跑**：`el.dataset.state = 'pibei'` 一行就切。

---

## 四、五态对照

| 态 | `data-state` | 视觉 | CSS 动效 | C 模块 `encouragement.level` |
|---|---|---|---|---|
| 元气 | `yuanqi` | 眼睛亮、双爪抬起、帽檐正 | 呼吸 2s + 金色星光 | `excellent` |
| 踏实 | `tashi` | 安静端坐、眼神平和 | 呼吸 3.2s | `good` |
| 疲惫 | `pibei` | 颊囊塞满瓜子、帽子歪、地上有壳 | 缓慢摇晃 4.5s | `normal` |
| 蔫了 | `nianle` | 眼睛下垂、降饱和、帽檐压低 | 每 6.5s 抖一下 | `low` |
| 休眠 | `xiumian` | 蜷成毛球、只露帽尖 | 静止 | 今天没学 / 非学习图 |

五张图**同一画布、底部对齐**，切态不会跳位——这条比画得好看更重要。

---

## 五、可调变量

```css
.hamster {
  --hamster-size: 240px;                        /* 显示尺寸 */
  --hamster-spark: #ffd479;                     /* 元气态星光颜色 */
  --hamster-glow: 0 8px 24px rgba(0,0,0,.12);   /* 投影，改 0 0 就是纯透明 */
}
```

额外给了一个识别等待态：`<div class="hamster waiting">`（呼吸 + 眨眼），上传后等 C 模块返回时用。

系统开了「减少动态效果」时所有动画自动停止（`prefers-reduced-motion`）。

---

## 六、JS API（可选）

```js
HamsterKit.STATES                 // ['yuanqi','tashi','pibei','nianle','xiumian']
HamsterKit.set(el, 'pibei')       // 直接设态，返回实际生效的态
HamsterKit.fromLevel('good')      // → 'tashi'（level → 态）
HamsterKit.fromRecord(rec)        // C 的识别结果 JSON → 态（level 缺失会按时长+正确率兜底推断）
HamsterKit.setFromRecord(el, rec) // 一步到位
HamsterKit.preload(baseUrl)       // 预加载五张图（CSS 已预载，双保险）
```

`fromLevel` 映射：`excellent→元气`、`good→踏实`、`normal→疲惫`、`low→蔫了`，空值/非学习图 → 休眠。

---

## 七、注意事项

1. **图片路径是相对的**，所以 `hamster.css` 和 `img/` 必须在同一层（CDN 上也是）。别只复制 CSS 不复制 img。
2. **验证透明通道**：打开 `index.html`，点「背景：深色」，五张边缘没有白边残渣才是真透明。
3. **更新素材后要打新 tag** 并改引用里的版本号，否则 CDN 会有最长 7 天缓存。
4. WebP 兼容 Chrome / Edge / Safari 14+ / Firefox，老浏览器要 PNG 的话从 `hamster-assets/final/` 取 512 PNG 版本替换即可（CSS 里改扩展名）。
