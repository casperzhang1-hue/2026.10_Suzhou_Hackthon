# -*- coding: utf-8 -*-
"""
把 C 模块的真识别链路接进原型（保留原有全部交互，只加一层「真数据」入口）。

输入：仓鼠陪跑_原型_实拍皮肤版.html + img/hamster_*.webp + app/public/recognize.js
输出：
  1) 仓鼠陪跑_原型_接真数据版.html          —— 本地开发用（图片走 img/ 目录）
  2) 仓鼠陪跑_原型_接真数据_单文件版.html    —— 分享用（图片 base64 内嵌 + recognize.js 内联）

新增能力：
  - 上传真图 → window.recognizeScreenshot(file,'demo_zhang') → 确认卡（字段可点改）→ 仓鼠变形态
  - warnings 映射成确认卡顶部提示条；CORRECT_COUNT_INVALID 阻断确认
  - NOT_A_STUDY_SCREENSHOT → 兜底手填页（PRD FR-12）
  - 等待态分段文案（8s / 15s / 22s），对齐 C 实测 20s 窗口
原有演示样本（三张假截图）全部保留。
"""
import base64
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC = os.path.join(BASE, "仓鼠陪跑_原型_实拍皮肤版.html")
RECOG = os.path.join(ROOT, "app", "public", "recognize.js")
OUT_DEV = os.path.join(BASE, "仓鼠陪跑_原型_接真数据版.html")
OUT_ONE = os.path.join(BASE, "仓鼠陪跑_原型_接真数据_单文件版.html")

html = open(SRC, encoding="utf-8").read()
recog = open(RECOG, encoding="utf-8").read()

# ---------------------------------------------------------------- CSS
CSS_ANCHOR = "/* ---------- 原型总览 ---------- */"
CSS_ADD = """/* ---------- 真识别流程（C 模块联调） ---------- */
.realup{margin-top:14px}
.realup .btn-primary{width:100%}
.rec-warn{margin:0 0 8px;padding:9px 11px;border-radius:10px;font-size:12px;line-height:1.5;
  background:rgba(192,57,43,.10);border:1px solid rgba(192,57,43,.28);color:#C0392B}
.rec-warn.soft{background:rgba(217,160,91,.13);border-color:rgba(217,160,91,.35);color:#B07A3C}
.rec-warn b{display:block;margin-bottom:3px;font-size:12.5px}
.rec-warn+.rec-warn{margin-top:6px}
.fb-row{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12.5px;color:var(--ink2)}
.fb-row span{width:78px;flex:none}
.fb-row input{flex:1;min-width:0;background:rgba(255,255,255,.06);border:1px solid var(--line);
  color:var(--ink);border-radius:8px;padding:6px 9px;font-size:12.5px;font-family:inherit}
.fb-row input:focus{outline:none;border-color:var(--ink3)}
#btnConfirm[disabled]{opacity:.45;cursor:not-allowed}

/* ---------- 原型总览 ---------- */"""

# ---------------------------------------------------------------- HTML：上传入口
PICK_ANCHOR = '            <button class="link" data-preset="none" style="display:block;margin:0 auto">今天没学，也记一下</button>'
PICK_ADD = """            <div class="realup">
              <input type="file" id="realFile" accept="image/png,image/jpeg,image/webp" hidden />
              <button class="btn-primary" id="btnRealPick">从相册选一张 · 真识别</button>
              <p class="sub" style="margin-top:7px">上面三张是演示样本；点这里走 C 模块的真识别链路（约 5~6 秒）</p>
            </div>
""" + PICK_ANCHOR

# ---------------------------------------------------------------- HTML：警告条
ROWS_ANCHOR = '            <div class="rows" id="fieldRows"></div>'
ROWS_ADD = '            <div id="recWarn"></div>\n' + ROWS_ANCHOR

# ---------------------------------------------------------------- HTML：兜底手填页
FB_ANCHOR = '            <p class="tip" style="margin-top:10px">识别错了也不影响，它会取更保守的那个值。</p>\n          </div>'
FB_ADD = FB_ANCHOR + """
          <div class="step" data-step="fallback">
            <h3>这张图没认出学习数据</h3>
            <p class="sub" id="fbMsg">没有识别出任何字段。可以手填一次，它会照常记下。</p>
            <div class="fb-row"><span>来源 App</span><input id="fbApp" placeholder="粉笔 / 华图在线 / 腰果公考 / 其他" /></div>
            <div class="fb-row"><span>时长(分钟)</span><input id="fbMin" type="number" min="0" step="1" placeholder="35" /></div>
            <div class="fb-row"><span>题量</span><input id="fbTotal" type="number" min="0" step="1" placeholder="30" /></div>
            <div class="fb-row"><span>正确</span><input id="fbCorrect" type="number" min="0" step="1" placeholder="26" /></div>
            <button class="btn-primary" id="btnFbConfirm" style="width:100%;margin-top:6px">就这样记下</button>
            <button class="link" id="btnFbRetry" style="display:block;margin:10px auto 0">换一张图</button>
          </div>"""

# ---------------------------------------------------------------- JS
JS_ANCHOR = "$$('.shot').forEach(function(b){ b.onclick = function(){ pickPreset(b.dataset.preset); }; });"
JS_ADD = JS_ANCHOR + """

/* =========================================================
   4.5 真识别链路（C 模块 recognize.js · 接口 v1.1 r5）
   ========================================================= */
var MODULE_LIST = ['言语理解','判断推理','数量关系','资料分析','常识判断','申论'];

/* warning code → [标题, 说明]；block=1 表示阻断确认（PRD 异常清单 #7） */
var WARN_HINT = {
  OLD_SCREENSHOT:        ['这张图有点旧', '这次学习距今超过 36 小时，确认是不是本次的'],
  SCREENSHOT_BLURRY:     ['有点模糊', '部分字段可能不准，下面点一下就能改'],
  DURATION_MISSING:      ['没认出时长', '时长这一行麻烦手填一下'],
  DURATION_TOO_SHORT:    ['时长太短', '不到 5 分钟，可能不是一次完整练习'],
  DURATION_TOO_LONG:     ['时长超长', '超过 600 分钟，请核对一下截图'],
  ACCURACY_TOO_LOW:      ['正确率偏低', '它会记下，但不会催你'],
  MODULE_MISMATCH:       ['模块没对齐', '各模块题量之和与总题量不一致'],
  CORRECT_COUNT_INVALID: ['数字对不上', '有模块的正确数大于题量，请改一下再记', 1],
  UNRECOGNIZED_APP:      ['没认出 App', '来源 App 可以在下面改'],
  NOT_A_STUDY_SCREENSHOT:['没认出学习数据', '可以手填一次，照常记下']
};

function sumCorrectOf(rec){
  var s = 0, ok = false;
  (rec.modules || []).forEach(function(m){
    if(m && typeof m.correct_count === 'number'){ s += m.correct_count; ok = true; }
  });
  return ok ? s : null;
}

/* Recognition → 原型内部 payload（喂给 computeDailyState / applyPreset） */
function recToPayload(rec){
  var minutes = typeof rec.duration_minutes === 'number' ? rec.duration_minutes : 0;
  var acc = typeof rec.accuracy === 'number' ? rec.accuracy : null;
  var total = rec.total_questions || 0;
  var correct = sumCorrectOf(rec);
  if(correct === null && acc !== null && total) correct = Math.round(total * acc);
  var mods = (rec.modules || []).map(function(m){ return m && m.name; }).filter(Boolean);
  var pct = acc === null ? null : Math.round(acc * 100);
  /* 模块不全（截图只露出部分模块）时，逐模块加总的正确数会明显小于总题量对应的正确数。
     此时只显示正确率百分比，不显示「对 N 题」——否则会出现「28 题 · 81%」这种自相矛盾的展示。 */
  var sumQ = (rec.modules || []).reduce(function(s, m){
    return s + (m && typeof m.question_count === 'number' ? m.question_count : 0);
  }, 0);
  var partial = total > 0 && sumQ > 0 && sumQ !== total;
  return {
    minutes: minutes,
    total: total,
    correct: correct,
    accuracy: acc,
    partial: partial,
    source_app: rec.source_app || null,
    fields: [
      {k:'日期', v:(rec.event_date || '今天') + (rec.event_time ? ' ' + rec.event_time : '')},
      {k:'模块', v: mods.length ? mods.join(' · ') : '未识别'},
      {k:'题量', v: total ? total + ' 题' : '未识别'},
      {k:'正确', v: partial
        ? (pct === null ? '未识别' : pct + '%')
        : ((correct === null ? '未识别' : correct + ' 题') + (pct === null ? '' : ' · ' + pct + '%'))},
      {k:'时长', v: minutes ? minutes + ' 分钟' : '未识别'}
    ]
  };
}

/* 由「时长/题量/正确」反推完成度、精力、缺口和 toast —— 确认卡改过之后也走这里 */
function finalizePayload(p){
  if(!p) return p;
  var acc = p.accuracy;
  if(typeof acc !== 'number' && p.total > 0 && typeof p.correct === 'number') acc = p.correct / p.total;
  var overloaded = p.minutes > 200 || (p.total > 80 && typeof acc === 'number' && acc < 0.55);
  p.completion = clamp(typeof acc === 'number' ? acc : p.minutes / 60, 0, 1.2);
  p.energy = overloaded ? 32 : (typeof acc === 'number' ? 55 + acc * 30 : 58);
  p.progress = 60;
  p.gapDelta = p.minutes >= 45 ? -1 : (p.minutes === 0 ? 1 : 0);
  p.toast = p.minutes
    ? ('已记下 · ' + p.minutes + ' 分钟' + (p.total ? '，' + p.total + ' 题' : '') +
       (typeof p.correct === 'number' && !p.partial ? '，对 ' + p.correct : ''))
    : '今天是空的。它收下了。';
  return p;
}

function firstNum(s){ var m = String(s).match(/(\\d+)/); return m ? parseInt(m[1], 10) : null; }

/* 确认卡上改过的行回写进 payload */
function syncPayloadFromRows(base){
  if(!base) return null;
  var p = JSON.parse(JSON.stringify(base));
  $$('#fieldRows .row').forEach(function(row){
    var k = $('.k', row).textContent;
    var v = $('.v span', row).textContent;
    var n = firstNum(v);
    if(k === '题量' && n !== null) p.total = n;
    if(k === '时长' && n !== null) p.minutes = n;
    if(k === '正确' && n !== null) p.correct = n;
  });
  if(typeof p.total === 'number' && typeof p.correct === 'number' && p.total > 0){
    p.accuracy = p.correct / p.total;
  }
  return finalizePayload(p);
}

/* 真数据的确认卡：候选项按实际数值生成（演示样本仍走原来的 buildRows） */
function buildRowsReal(p){
  editedFields = {};
  var box = $('#fieldRows');
  box.innerHTML = '';
  function uniq(a){ return a.filter(function(x, i){ return a.indexOf(x) === i; }); }
  var alts = {
    '日期': uniq([p.fields[0].v, '今天 22:30', '昨天 23:10']),
    '模块': uniq([p.fields[1].v].concat(MODULE_LIST.slice(0, 4))),
    '题量': uniq([p.total, p.total - 2, p.total + 2, p.total + 5]).filter(function(x){ return x > 0; }).map(function(x){ return x + ' 题'; }),
    '正确': uniq([p.correct, p.correct - 2, p.correct + 2]).filter(function(x){ return typeof x === 'number' && x >= 0; }).map(function(x){ return x + ' 题'; }),
    '时长': uniq([p.minutes, p.minutes - 5, p.minutes + 5, p.minutes + 15]).filter(function(x){ return x > 0; }).map(function(x){ return x + ' 分钟'; })
  };
  p.fields.forEach(function(f, i){
    var row = document.createElement('div');
    row.className = 'row';
    row.dataset.i = i;
    row.innerHTML = '<div class="k">' + f.k + '</div><div class="v"><span>' + f.v + '</span><span class="dot"></span></div>';
    row.onclick = function(){
      var list = alts[f.k];
      if(!list || list.length < 2) return;
      editedFields[i] = true;
      row.classList.add('edited');
      var span = row.querySelector('.v span');
      var idx = list.indexOf(span.textContent);
      span.textContent = list[(idx + 1) % list.length];
    };
    box.appendChild(row);
  });
}

function renderWarn(rec){
  var box = $('#recWarn');
  box.innerHTML = '';
  var codes = (rec.warnings || []).map(function(w){ return w && w.code; }).filter(Boolean);
  var blocked = false;
  codes.forEach(function(c){
    var h = WARN_HINT[c];
    if(!h) return;
    if(h[2]) blocked = true;
    var d = document.createElement('div');
    d.className = 'rec-warn' + (h[2] ? '' : ' soft');
    d.innerHTML = '<b>' + h[0] + '</b>' + h[1];
    box.appendChild(d);
  });
  var btn = $('#btnConfirm');
  btn.disabled = blocked;
  btn.textContent = blocked ? '数字对不上，先改一下' : '没问题，记下';
}

/* ---- 主流程 ---- */
var currentPayload = null;   // 真数据 payload（null 表示当前是演示样本）
var realTimers = [];
function clearRealTimers(){ realTimers.forEach(clearTimeout); realTimers = []; }

function startRealRecognize(file){
  if(typeof window.recognizeScreenshot !== 'function'){
    showToast('recognize.js 没加载，先用上面的演示样本');
    return;
  }
  var url = URL.createObjectURL(file);
  var css = 'width:100%;height:100%;object-fit:cover;border-radius:10px';
  var img = document.createElement('img'); img.src = url; img.style.cssText = css;
  var oldScan = $('#scanBox').querySelector('.mini');
  if(oldScan) oldScan.replaceWith(img);
  $('#confirmThumb').innerHTML = '';
  var thumb = document.createElement('img'); thumb.src = url; thumb.style.cssText = css;
  $('#confirmThumb').appendChild(thumb);

  setStep('scan');
  $('#sheet').classList.add('up');
  $('#scanTxt').textContent = '在看你的截图…';
  $('#scanSub').textContent = '不用你填任何数字';
  clearRealTimers();
  realTimers = [
    setTimeout(function(){ $('#scanSub').textContent = '这张图信息有点多，我还在看…'; }, 8000),
    setTimeout(function(){ $('#scanSub').textContent = '马上就好，再等我一下…'; }, 15000),
    setTimeout(function(){ $('#scanSub').textContent = '网络有点慢，我还在努力识别…'; }, 22000)
  ];

  window.recognizeScreenshot(file, 'demo_zhang').then(function(rec){
    clearRealTimers();
    window.__lastRec = rec;
    if(rec && rec._elapsed_ms) console.log('[C 模块] 识别耗时 ' + rec._elapsed_ms + 'ms', rec);

    var codes = ((rec && rec.warnings) || []).map(function(w){ return w && w.code; });
    // 双条件：level 为空 或 带 NOT_A_STUDY_SCREENSHOT。
    // recognize.js 的 noData 分支只把 level 置空、不补警告，只按 code 判会漏，
    // 给用户弹出一张全空的确认卡（实测仓鼠照片就是这种情况）。
    var isNotStudy = (rec && rec.encouragement && rec.encouragement.level === '') ||
                     codes.indexOf('NOT_A_STUDY_SCREENSHOT') !== -1;
    if(isNotStudy){
      $('#fbMsg').textContent = '这张图里没找到学习数据，可以手填一次，照常记下。';
      setStep('fallback');
      return;
    }
    currentPayload = recToPayload(rec);
    buildRowsReal(currentPayload);
    renderWarn(rec);
    var t1 = $('.confirm-head .t1');
    if(t1) t1.textContent = '认出 ' + currentPayload.fields.filter(function(f){ return f.v !== '未识别'; }).length + ' 个字段';
    $('#scanTxt').textContent = '看完了';
    setStep('confirm');
  }).catch(function(e){
    clearRealTimers();
    showToast('识别异常：' + (e && e.message ? e.message : e));
    setStep('pick');
  });
}

$('#realFile').addEventListener('change', function(e){
  var f = e.target.files && e.target.files[0];
  if(f) startRealRecognize(f);
  e.target.value = '';
});
$('#btnRealPick').onclick = function(){ $('#realFile').click(); };
$('#btnFbRetry').onclick = function(){ $('#realFile').click(); };

/* 确认按钮：真数据读回改过的行，演示样本走原逻辑 */
$('#btnConfirm').onclick = function(){
  closeSheet();
  var p = currentPayload ? syncPayloadFromRows(currentPayload) : (PRESETS[currentPreset] || PRESETS.good);
  currentPayload = null;
  currentPreset = null;
  setTimeout(function(){ applyPreset(p); }, 220);
};

/* 兜底手填页提交（PRD FR-12） */
$('#btnFbConfirm').onclick = function(){
  var minutes = parseInt($('#fbMin').value, 10);
  var total = parseInt($('#fbTotal').value, 10);
  var correct = parseInt($('#fbCorrect').value, 10);
  if(isNaN(minutes)) minutes = 0;
  var payload = finalizePayload({
    minutes: minutes,
    total: isNaN(total) ? 0 : total,
    correct: isNaN(correct) ? null : correct,
    accuracy: (!isNaN(total) && total > 0 && !isNaN(correct)) ? correct / total : null,
    source_app: $('#fbApp').value || null
  });
  closeSheet();
  currentPayload = null;
  setTimeout(function(){ applyPreset(payload); }, 220);
};"""

PATCHES = [
    ("CSS", CSS_ANCHOR, CSS_ADD),
    ("上传入口", PICK_ANCHOR, PICK_ADD),
    ("警告条容器", ROWS_ANCHOR, ROWS_ADD),
    ("兜底页", FB_ANCHOR, FB_ADD),
    ("真识别 JS", JS_ANCHOR, JS_ADD),
]

for name, old, new in PATCHES:
    n = html.count(old)
    assert n == 1, "锚点「%s」命中 %d 次，应为 1 次" % (name, n)
    html = html.replace(old, new)
    print("patch ok:", name)

# recognize.js 内联（保证单文件也能真识别）
# 坑：recognize.js 的头部注释里写着用法 <script src="recognize.js"></script>，
# 内含 "</script"，HTML 解析器会在此提前闭合 script 元素，把后面的 JS 当成文本吐出来。
# 必须把 <script / </script 里的斜杠转义（在 JS 注释里，<\/script 无害）。
recog_safe = recog.replace("</script", "<\\/script").replace("<script", "<\\script")
assert "</script" not in recog_safe and "<script" not in recog_safe
assert "</body>" in html
html = html.replace("</body>", "<script>\n/* ===== C 模块 recognize.js v1.1-r5 内联 ===== */\n" + recog_safe + "\n</script>\n</body>")
print("patch ok: recognize.js 内联")

open(OUT_DEV, "w", encoding="utf-8").write(html)
print("written:", OUT_DEV, os.path.getsize(OUT_DEV) // 1024, "KB")

# ---------------- 单文件版：图片 base64 内嵌 ----------------
one = html
for name in ["01_yuanqi", "02_tashi", "03_pibei", "04_nianle", "05_xiumian"]:
    # 单文件版用 512：显示槽位 298px，512 已是 @1.7x，肉眼无差，体积省一半
    p = os.path.join(ROOT, "hamster-assets", "final", "hamster_%s_512.webp" % name)
    b64 = base64.b64encode(open(p, "rb").read()).decode("ascii")
    one = one.replace("img/hamster_%s.webp" % name, "data:image/webp;base64," + b64)

assert one.count("img/hamster") == 0, "仍有外链图片引用"
open(OUT_ONE, "w", encoding="utf-8").write(one)
print("written:", OUT_ONE, os.path.getsize(OUT_ONE) // 1024, "KB")

# ---------------- 自检 ----------------
# 1) 内联后不能出现未转义的 </script（否则 HTML 会提前闭合）
body_scripts = re.findall(r"<script>(.*?)</script>", one, re.S)
assert len(body_scripts) == 2, "script 块数量异常：%d" % len(body_scripts)
assert len(re.findall(r"<script", one)) == 2, "存在未转义的 <script"
print("check ok: script 块", len(body_scripts), "，无未转义标签")
# 2) 抽出主脚本交给 node --check（recognize.js 本体单独校验）
os.makedirs(os.path.join(BASE, "_tmpcheck"), exist_ok=True)
open(os.path.join(BASE, "_tmpcheck", "main.js"), "w", encoding="utf-8").write(body_scripts[0])
print("check ok: 已导出 main.js")
