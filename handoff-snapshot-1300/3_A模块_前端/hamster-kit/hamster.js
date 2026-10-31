/* =============================================================
   监督小宠 · 仓鼠五态 配套脚本  v1.0
   -------------------------------------------------------------
   纯 CSS 已经能用（改 data-state 即可），本文件只是省事封装：
     HamsterKit.set(el, 'yuanqi')          // 直接设态
     HamsterKit.fromLevel('good')          // C 模块 encouragement.level → 态
     HamsterKit.fromRecord(rec)            // C 的识别结果 JSON → 态
     HamsterKit.setFromRecord(el, rec)     // 一步到位
   ============================================================= */
(function (root) {
  'use strict';

  var STATES = ['yuanqi', 'tashi', 'pibei', 'nianle', 'xiumian'];

  var LABEL = {
    yuanqi: '元气',
    tashi: '踏实',
    pibei: '疲惫',
    nianle: '蔫了',
    xiumian: '休眠'
  };

  /* C 模块 encouragement.level → 五态
     excellent 优秀 / good 良好 / normal 一般 / low 低落 / "" 非学习图或空 */
  var LEVEL_MAP = {
    excellent: 'yuanqi',
    good: 'tashi',
    normal: 'pibei',
    low: 'nianle'
  };

  function normalize(state) {
    if (!state) return 'xiumian';
    var s = String(state);
    return STATES.indexOf(s) !== -1 ? s : (LEVEL_MAP[s] || 'xiumian');
  }

  function set(el, state) {
    if (!el) return null;
    var s = normalize(state);
    el.setAttribute('data-state', s);
    return s;
  }

  function fromLevel(level) {
    // 非学习图 / 今天还没学 → 休眠态
    if (!level) return 'xiumian';
    return LEVEL_MAP[level] || 'xiumian';
  }

  /* 识别结果 JSON 兜底推断：接口没给 level 时，按时长和正确率自己判 */
  function inferLevel(rec) {
    if (!rec) return '';
    var lv = rec.encouragement && rec.encouragement.level;
    if (lv) return lv;
    var acc = rec.accuracy;
    var min = rec.duration_minutes;
    if (acc === null || acc === undefined || !min) return 'normal';
    if (acc >= 0.85 && min >= 30) return 'excellent';
    if (acc >= 0.7) return 'good';
    if (acc < 0.6) return 'low';
    return 'normal';
  }

  function fromRecord(rec) {
    return fromLevel(inferLevel(rec));
  }

  function setFromRecord(el, rec) {
    return set(el, fromRecord(rec));
  }

  /* 提前把五张图拉进缓存（CSS 已用 ::after 预载，这里是双保险） */
  function preload(base) {
    var dir = base || '';
    if (dir && dir.slice(-1) !== '/') dir += '/';
    STATES.forEach(function (s, i) {
      var n = ['01_yuanqi', '02_tashi', '03_pibei', '04_nianle', '05_xiumian'][i];
      var im = new Image();
      im.src = dir + 'img/hamster_' + n + '.webp';
    });
  }

  var HamsterKit = {
    STATES: STATES,
    LABEL: LABEL,
    LEVEL_MAP: LEVEL_MAP,
    set: set,
    fromLevel: fromLevel,
    inferLevel: inferLevel,
    fromRecord: fromRecord,
    setFromRecord: setFromRecord,
    preload: preload
  };

  root.HamsterKit = HamsterKit;
  if (typeof module !== 'undefined' && module.exports) module.exports = HamsterKit;
})(typeof window !== 'undefined' ? window : this);
