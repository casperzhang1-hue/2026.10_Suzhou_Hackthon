import os, shutil, re

BASE = r'D:/workbuddy1/2026-10-31-08-28-48'
SRC_HTML = r'C:/Users/Lenovo/Downloads/仓鼠陪跑_原型与Demo.html'
OUT_DIR = os.path.join(BASE, 'prototype')
IMG_DIR = os.path.join(OUT_DIR, 'img')
os.makedirs(IMG_DIR, exist_ok=True)

# 1) 拷五态图
final = os.path.join(BASE, 'hamster-assets', 'final')
for n in ['01_yuanqi', '02_tashi', '03_pibei', '04_nianle', '05_xiumian']:
    shutil.copyfile(os.path.join(final, f'hamster_{n}_1024.webp'), os.path.join(IMG_DIR, f'hamster_{n}.webp'))

html = open(SRC_HTML, encoding='utf-8').read()
patched = 0

def rep(old, new, label):
    global html, patched
    assert old in html, 'NOT FOUND: ' + label
    html = html.replace(old, new, 1)
    patched += 1

# 2) CSS：实拍照片堆叠层
rep(
    "/* ---------- 原型总览 ---------- */",
    """/* ---------- 宠物：实拍照片皮肤 ---------- */
.pet-photo{position:relative;width:100%;height:100%;transform-origin:50% 100%}
.pet-photo img{
  position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:50% 100%;
  opacity:0;transition:opacity .5s cubic-bezier(.22,1,.36,1);pointer-events:none;will-change:opacity;
}
.pet-photo img.on{opacity:1}

/* 实拍皮肤：状态微动效（对齐 PRD 动效表：呼吸/摇晃/偶尔抖动/静止） */
.pet-photo[data-state="vigour"]{animation:phBreathe 2s ease-in-out infinite}
.pet-photo[data-state="steady"]{animation:phBreathe 3.2s ease-in-out infinite}
.pet-photo[data-state="tired"]{animation:phSway 4.5s ease-in-out infinite}
.pet-photo[data-state="wilt"]{animation:phTremble 6.5s ease-in-out infinite}
.pet-photo[data-state="sleep"]{animation:none}
@keyframes phBreathe{50%{transform:scale(1.015,1.03)}}
@keyframes phSway{50%{transform:rotate(-1.4deg) translateY(2px)}}
@keyframes phTremble{0%,86%,100%{transform:none}90%{transform:rotate(-1.8deg)}94%{transform:rotate(1.2deg)}}

/* 元气态：金色星光点缀（呼应 FR-08） */
.pet-photo[data-state="vigour"]::after{
  content:'';position:absolute;left:14%;top:15%;width:5px;height:5px;border-radius:50%;
  background:#E0B27C;pointer-events:none;opacity:.9;
  box-shadow:30px 22px 0 -1px #E0B27C, 14px 48px 0 -2px #E0B27C;
  animation:phTwinkle 2.6s ease-in-out infinite;
}
@keyframes phTwinkle{0%,100%{opacity:.12}50%{opacity:.9}}

/* ---------- 原型总览 ---------- */""",
    'css insert')

# 3) 皮肤开关 + 图片映射（放在 petMarkup 之前）
rep(
    "function petMarkup(o){",
    """/* ====== 宠物皮肤 ======
   photo = 实拍五态照片（本项目定稿方向）
   svg   = 原参数化插画（可插值、可微调）
   用法：?pet=svg 切回插画版，右下角按钮也能切
   ========================================================= */
window.PET_MODE = (new URLSearchParams(location.search).get('pet') === 'svg') ? 'svg' : 'photo';

var PHOTO_SRC = {
  vigour: 'img/hamster_01_yuanqi.webp',
  steady: 'img/hamster_02_tashi.webp',
  tired:  'img/hamster_03_pibei.webp',
  wilt:   'img/hamster_04_nianle.webp',
  sleep:  'img/hamster_05_xiumian.webp'
};

function petMarkup(o){""",
    'pet mode const')

# 4) petMarkup 照片分支
rep(
    """  o = o || {};
  var back = !!o.back;
  /* 全部实色填充，不用 url(#渐变)——克隆/隐藏容器里引用解析不可靠 */""",
    """  o = o || {};
  var back = !!o.back;

  if (window.PET_MODE === 'photo') {
    var keys = ['vigour','steady','tired','wilt','sleep'];
    var init = o.state || 'steady';
    return '<div class="pet pet-photo">' + keys.map(function(k){
      return '<img src="' + PHOTO_SRC[k] + '" alt="" data-k="' + k + '"' + (k === init ? ' class="on"' : '') + '>';
    }).join('') + '</div>';
  }

  /* 全部实色填充，不用 url(#渐变)——克隆/隐藏容器里引用解析不可靠 */""",
    'petMarkup branch')

# 5) applyPet 支持照片层
rep(
    """function applyPet(svg, state){
  if(!svg) return;
  var p = PET[state] || PET.steady;
  svg.dataset.state = state;""",
    """function applyPet(svg, state){
  if(!svg) return;
  svg.dataset.state = state;

  /* 实拍皮肤：切 .on 直接换图，交叉淡入靠 CSS transition，不做整只缩放 */
  if (svg.classList && svg.classList.contains('pet-photo')) {
    var k = (state === 'stay') ? 'steady' : state;
    Array.prototype.forEach.call(svg.querySelectorAll('img'), function(im){
      im.classList.toggle('on', im.getAttribute('data-k') === k);
    });
    return;
  }

  var p = PET[state] || PET.steady;""",
    'applyPet branch')

# 6) 调用点：'svg' 选择器 → '.pet'
rep("applyPet($('svg', homePet), APP.state);", "applyPet($('.pet', homePet), APP.state);", 'home call')
rep("applyPet(rp.querySelector('svg'), 'stay');", "applyPet(rp.querySelector('.pet'), 'stay');", 'result call')
rep("applyPet(devPet.querySelector('svg'), r.petState);", "applyPet(devPet.querySelector('.pet'), r.petState);", 'dev call')
rep("applyPet(devPet.querySelector('svg'), 'stay');", "applyPet(devPet.querySelector('.pet'), 'stay');", 'dev stay call')

# 7) dock 加皮肤切换按钮
rep(
    """  <div class="sep"></div>
  <span>← → 切屏</span>""",
    """  <div class="sep"></div>
  <button id="btnSkin">皮肤：实拍</button>
  <span>← → 切屏</span>""",
    'dock button')

rep(
    """/* dock 快捷 */""",
    """/* dock 快捷 */
var skinBtn = document.getElementById('btnSkin');
if (skinBtn) {
  skinBtn.textContent = '皮肤：' + (window.PET_MODE === 'photo' ? '实拍' : '插画');
  skinBtn.onclick = function(){
    var u = new URL(location.href);
    u.searchParams.set('pet', window.PET_MODE === 'photo' ? 'svg' : 'photo');
    location.href = u.toString();
  };
}
""",
    'dock js')

# 8) 标题标记版本
rep("高保真原型 &amp; Demo · v1.1", "高保真原型 &amp; Demo · v1.2 实拍皮肤", 'title')

out = os.path.join(OUT_DIR, '仓鼠陪跑_原型_实拍皮肤版.html')
open(out, 'w', encoding='utf-8').write(html)
print('patched', patched, 'edits ->', out, len(html), 'chars')

# 9) 抽出内联 script 做语法校验
m = re.search(r'<script>(.*)</script>', html, re.S)
open(os.path.join(OUT_DIR, '_check.js'), 'w', encoding='utf-8').write(m.group(1))
print('script extracted', len(m.group(1)), 'chars')
