// API 适配层 —— 全项目只有这里碰网络
// 真联调：index.html 加 <script src="recognize.js"></script> 后把 USE_MOCK 改成 false
import { SCENARIOS } from './mockData'

export const USE_MOCK = true
export const DEMO_USER_ID = 'demo_zhang'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// C 承诺 20s 内一定返回；25s 看门狗只是防御 SDK 卡死，正常路径永不触发
const WATCHDOG_MS = 25000

/** 契约自检（仅开发期 console，不做阻断）：v1.1 字段齐全 + encouragement 只有 level + accuracy 在 [0,1] */
function audit(r) {
  if (!r || typeof r !== 'object') return console.error('[契约] 返回值不是对象', r)
  const must = ['schema_version', 'user_id', 'recognition', 'source_app', 'event_date', 'event_time',
    'duration_minutes', 'modules', 'total_questions', 'accuracy', 'warnings', 'encouragement']
  const missing = must.filter((k) => !(k in r))
  if (missing.length) console.error('[契约] 缺字段:', missing.join(', '))
  if (r.schema_version !== '1.1') console.warn('[契约] schema_version =', r.schema_version)
  const keys = Object.keys(r.encouragement || {})
  if (keys.length !== 1 || keys[0] !== 'level') console.error('[契约] encouragement 应只含 level，实际:', keys)
  if (r.accuracy != null && !(r.accuracy >= 0 && r.accuracy <= 1)) console.error('[契约] accuracy 越界:', r.accuracy)
  if (r.duration_minutes != null && !Number.isInteger(r.duration_minutes)) {
    console.error('[契约] duration_minutes 应为整数（r3 已修）:', r.duration_minutes)
  }
  console.log('[识别] _elapsed_ms =', r._elapsed_ms)
}

/** 识别失败 / 超时时的兜底标准对象，保证等待态永远不卡死 */
function fallbackResult(reason) {
  return {
    schema_version: '1.1',
    user_id: DEMO_USER_ID,
    recognition: { recognized_at: new Date().toISOString(), confidence: 0 },
    source_app: null, event_date: null, event_time: null, duration_minutes: null,
    modules: [], total_questions: null, accuracy: null,
    warnings: [{ code: 'NOT_A_STUDY_SCREENSHOT', message: reason }],
    encouragement: { level: '' },
  }
}

/**
 * 上传截图 → 识别结果（recognize.js 契约：永远 resolve 标准对象，不抛异常）
 * @param {File} file
 * @param {string} [scenarioKey] 仅 mock 模式：指定演示场景
 * @returns {Promise<Recognition>}
 */
export async function recognize(file, scenarioKey) {
  if (USE_MOCK) {
    // 对齐 C 实测耗时（平均 5.6s，慢图到 11s）：mock 也走 4~6s，等待态按真实节奏打磨
    await sleep(4000 + Math.random() * 2000)
    const found = SCENARIOS.find((s) => s.key === scenarioKey) || SCENARIOS[0]
    return JSON.parse(JSON.stringify(found.data))
  }
  // 兜底 1：recognize.js 没加载成功
  if (typeof window === 'undefined' || typeof window.recognizeScreenshot !== 'function') {
    console.error('[识别] window.recognizeScreenshot 未定义，检查 <script src="/recognize.js">')
    return fallbackResult('recognize.js 未加载')
  }
  // 兜底 2：C 内部异常（契约上不该发生）
  let res
  try {
    res = await window.recognizeScreenshot(file, DEMO_USER_ID)
  } catch (e) {
    console.error('[识别] recognizeScreenshot 抛出异常:', e)
    return fallbackResult('识别异常：' + e.message)
  }
  // 兜底 3：25 秒看门狗（正常 5.4~5.7s，永不触发）
  const watchdog = sleep(WATCHDOG_MS).then(() => null)
  const winner = await Promise.race([Promise.resolve(res), watchdog])
  if (winner === null) {
    console.error('[识别] 超过 ' + WATCHDOG_MS + 'ms 未返回')
    return fallbackResult('识别超时')
  }
  audit(winner)
  return winner
}

/**
 * 确认卡提交 → 入库（反向接口，前端定义）
 * @param {{record: object, recognition_ref: object, edited_fields: string[], confirmed_at: string}} payload
 */
export async function submitRecord(payload) {
  if (USE_MOCK) {
    await sleep(500)
    console.log('[mock] 入库 payload：', payload)
    return { ok: true }
  }
  const res = await fetch('/api/records', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error('入库失败')
  return res.json()
}
