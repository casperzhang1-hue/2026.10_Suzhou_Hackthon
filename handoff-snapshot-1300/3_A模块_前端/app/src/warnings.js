// warnings code → 前端消费规则（写死在前端，C 不用管 UI）
// code 是唯一契约；C 返回的 message 仅作调试，前端统一用这里的文案
export const WARNING_RULES = {
  OLD_SCREENSHOT: {
    level: 'hint',
    text: '这是几天前的记录，默认记到截图当日',
  },
  SCREENSHOT_BLURRY: {
    level: 'hint',
    text: '识别得不太清楚，帮我核对一下',
  },
  UNRECOGNIZED_APP: {
    level: 'hint',
    text: '这个 App 我还在学，帮我标一下来源',
  },
  DURATION_MISSING: {
    level: 'hint',
    text: '没认出学习时长，手动填一下',
  },
  DURATION_TOO_SHORT: {
    level: 'hint',
    text: '时长有点短，帮我确认下',
  },
  DURATION_TOO_LONG: {
    level: 'hint',
    text: '超过 10 小时了，帮我确认下时长',
  },
  ACCURACY_TOO_LOW: {
    level: 'hint',
    text: '正确率有点低，确认数字没问题就提交',
  },
  // —— 以下为拦截级 ——
  CORRECT_COUNT_INVALID: {
    level: 'block',
    text: '正确数比题量还多，改对才能提交',
  },
  // 注意：MODULE_MISMATCH 是「正常现象」不是错误（C 联调说明第六节）：
  // 截图只露出部分模块时必然对不上，r3 已保证 accuracy 与逐模块行同源。
  // 设成 block 会导致这类截图无法提交——只有 CORRECT_COUNT_INVALID 才拦。
  MODULE_MISMATCH: {
    level: 'hint',
    text: '只看出部分模块，正确率按整张算',
  },
  DUPLICATE_RECORD: {
    level: 'block',
    text: '这张已经记过了',
  },
  NOT_A_STUDY_SCREENSHOT: {
    level: 'block',
    text: '这张看不出来是学习截图，换一张或手动选',
  },
}

export function getWarnings(recognition) {
  return (recognition?.warnings || []).map((w) => ({
    code: w.code,
    ...(WARNING_RULES[w.code] || { level: 'hint', text: w.message || '需要核对' }),
  }))
}

export function hasBlockWarning(recognition) {
  return getWarnings(recognition).some((w) => w.level === 'block')
}

/**
 * 是否「非学习图片」→ 走兜底手填页（FR-12）
 *
 * 注意：不能只认 NOT_A_STUDY_SCREENSHOT。recognize.js 第 501 行有个 noData 分支——
 * accuracy 和 duration_minutes 都是 null 时，它把 encouragement.level 置为 ""，
 * 但**不会**补 NOT_A_STUDY_SCREENSHOT 警告（实测：仓鼠照片返回 level="" +
 * warnings=[SCREENSHOT_BLURRY, DURATION_MISSING]）。
 * 只按 code 判会漏掉这类图，给用户弹出一张全空的确认卡。所以两个条件取并集。
 */
export function isNotStudyResult(recognition) {
  const levelEmpty = recognition?.encouragement?.level === ''
  const flagged = (recognition?.warnings || []).some((w) => w.code === 'NOT_A_STUDY_SCREENSHOT')
  return levelEmpty || flagged
}
