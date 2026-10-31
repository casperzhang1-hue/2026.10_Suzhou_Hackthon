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
/**
 * 后端地址候选：B 的 README 写 8000，D 复评时实测跑在 8015。
 * 现场端口不确定，这里按顺序探测，第一个通的就锁定 —— 免得路演前还在改常量。
 * 优先用 .env 的 VITE_API_BASE（给了就只用它，探测反而多余）。
 */
const ENV_BASE = import.meta.env.VITE_API_BASE
export const CANDIDATE_BASES = ENV_BASE
  ? [ENV_BASE]
  : ['http://127.0.0.1:8000', 'http://127.0.0.1:8015', 'http://127.0.0.1:8787']
export const API_BASE = CANDIDATE_BASES[0]

/** 后端探活超时：B 没起服务时快速回落，不拖慢演示（识别链路不受影响） */
const API_TIMEOUT_MS = 1500

/** 已探测到的可用后端地址（null = 还没探过） */
let resolvedBase = null
async function resolveBase() {
  if (resolvedBase) return resolvedBase
  for (const base of CANDIDATE_BASES) {
    try {
      const res = await fetchWithTimeout(base + '/api/today')
      if (res.ok) {
        resolvedBase = base
        if (base !== API_BASE) console.log('[后端] 已连接', base)
        return base
      }
    } catch (e) {
      /* 换下一个候选 */
    }
  }
  return null
}

/** 断网/后端未起时是否允许显示本地演示数据（界面会强制打「离线 · 演示数据」标记，不会冒充真数据） */
export const ALLOW_MOCK_WHEN_OFFLINE = import.meta.env.VITE_ALLOW_MOCK_OFFLINE !== '0'

/** 带超时的 fetch：AbortController，超时直接 reject，避免界面卡在等待态 */
function fetchWithTimeout(url, options = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS)
  return fetch(url, { ...options, signal: ctrl.signal }).finally(() => clearTimeout(timer))
}

/** 上次成功拉取的数据缓存（localStorage）：断网时用它兜底，而不是编一个数字 */
const CACHE_KEY = 'pet_today_cache_v1'
function cacheToday(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }))
  } catch (e) {
    /* 隐私模式下 localStorage 不可写，忽略 */
  }
}
function readCachedToday() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const { data } = JSON.parse(raw)
    return data && typeof data === 'object' ? data : null
  } catch (e) {
    return null
  }
}

/** 本地演示口径（仅在后端完全不可达、且无缓存时使用；界面会打「离线 · 演示数据」） */
const MOCK_TODAY = {
  date: new Date().toISOString().slice(0, 10),
  has_record: true,
  pet_state: 'tired',
  vitality: 62,
  user_state: '过载',
  phrase_level: 'low',
  gap: { week_target: 5, week_done: 3, owed: 2 },
  detail: { duration_minutes: 210, accuracy: 0.55, late_night: true },
}

export async function submitRecord(payload) {
  // 入库是真接口优先；失败不阻断演示（路演现场宁可少记一条，也不能卡在提交上）
  try {
    const base = (await resolveBase()) || API_BASE
    const res = await fetchWithTimeout(base + '/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const data = await res.json()
    return { ...data, persisted: true }
  } catch (e) {
    console.warn('[入库] 后端不可达，本次仅本地生效：', e.message, payload)
    return { ok: true, persisted: false }
  }
}

/**
 * 今日屏：今日状态 + 缺口行
 * @returns {Promise<{has_record:boolean, pet_state:string, vitality:number,
 *   user_state:string, phrase_level:string, gap:{week_target:number,week_done:number,owed:number}}>}
 */
export async function fetchToday() {
  // 真接口优先：自动探测 B 的端口（8000 / 8015 / 8787），B 一起服务就生效，不用改代码
  try {
    const base = await resolveBase()
    if (!base) throw new Error('后端未启动（已试 ' + CANDIDATE_BASES.join(' / ') + '）')
    const res = await fetchWithTimeout(base + '/api/today')
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const data = await res.json()
    // 契约自检：缺口行是 RK-08 的唯一防法，后端没给 gap 必须立刻暴露，不能静默
    if (!data || typeof data !== 'object') throw new Error('返回不是对象')
    if (!data.gap) console.error('[契约] /api/today 缺 gap 字段，缺口行无法显示：', data)
    cacheToday(data)
    return { ...data, offline: false, mock: false, base }
  } catch (e) {
    console.warn('[今日] 后端不可达：', e.message)
    // 回落 1：上次成功拉取的数据（最诚实，数字是真实发生过的）
    const cached = readCachedToday()
    if (cached) return { ...cached, offline: true, mock: false }
    // 回落 2：完全没有历史数据 —— 要么显示演示数据（打标记），要么返回 null 让界面显示「—」
    if (!ALLOW_MOCK_WHEN_OFFLINE) return null
    return { ...MOCK_TODAY, offline: true, mock: true }
  }
}

/**
 * 记忆屏：3 条「它记得的事」
 * 失败时返回空列表（界面显示「还没有记忆」），不编造「它记得你说过…」——那是最容易穿帮的地方
 */
export async function fetchMemories() {
  try {
    const base = (await resolveBase()) || API_BASE
    const res = await fetchWithTimeout(base + '/api/memories')
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const data = await res.json()
    return { ...data, offline: false }
  } catch (e) {
    console.warn('[记忆] 后端不可达：', e.message)
    return { items: [], offline: true }
  }
}
