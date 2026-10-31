/**
 * 零依赖 mock 后端 —— B 的三个接口交付前，全链路靠它跑通。
 *
 * 启动：  node server.js
 * 端口：  8787
 * 接口：  POST /api/records      入库（确认卡提交）
 *         GET  /api/today        今日状态（含 gap 缺口行 —— RK-08 唯一防法）
 *         GET  /api/memories     记忆屏 3 条
 *         GET  /api/health       存活检查
 *
 * ⚠️ B 交付后，前端只需把 baseURL 从 http://127.0.0.1:8787 换成你的服务地址，
 *    前端业务代码一行不改。
 *
 * 运行依赖：Node 18+（用到全局 fetch 不需要，纯 node:http）
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const { computeDailyState, petStateToPhraseLevel, clamp } = require('./engine');

const PORT = process.env.PORT || 8787;
const DATA_DIR = path.join(__dirname, 'data');
const SEED_PATH = path.join(DATA_DIR, 'seed.json');
const RECORDS_PATH = path.join(DATA_DIR, 'records.json');

const seed = JSON.parse(fs.readFileSync(SEED_PATH, 'utf-8'));
if (!fs.existsSync(RECORDS_PATH)) fs.writeFileSync(RECORDS_PATH, '[]', 'utf-8');

const readRecords = () => JSON.parse(fs.readFileSync(RECORDS_PATH, 'utf-8'));
const writeRecords = (r) => fs.writeFileSync(RECORDS_PATH, JSON.stringify(r, null, 2), 'utf-8');

const today = () => new Date().toISOString().slice(0, 10);

/** 熬夜判定：结束时间跨过 0 点，或 22 点后开始且超过 90 分钟 */
function isLateNight(startTime, endTime, minutes) {
  if (!endTime) return false;
  const [eh] = endTime.split(':').map(Number);
  if (eh >= 0 && eh < 6) return true;                       // 结束在凌晨 0-6 点
  const [sh] = (startTime || '21:00').split(':').map(Number);
  return sh >= 22 && minutes > 90;                          // 22 点后开刷且超 90 分钟
}

/** 精力分：学得越多越累，熬夜重罚 —— 这是「过载」那一格的来源 */
function energyOf(minutes, late) {
  let e = 100 - minutes / 6;
  if (late) e -= 30;
  return Math.round(clamp(e, 0, 100));
}

/** 完成度：80 分钟算达标（1.0），上限 1.2 */
const completionOf = (minutes) => Math.min(1.2, minutes / 80);

/** 按 seed 逐日滚 vitality，得到「昨天」的活力值 */
function rollPrevVitality(uptoDate) {
  let v = 30; // 新用户起点
  const days = seed.days.filter((d) => d.date < uptoDate).sort((a, b) => a.date.localeCompare(b.date));
  for (const d of days) {
    const minutes = d.duration_minutes || 0;
    const late = isLateNight(d.start_time, d.end_time, minutes);
    const st = computeDailyState({
      minutes,
      completion: completionOf(minutes),
      energy: energyOf(minutes, late),
      progress: Math.round((d.accuracy || 0) * 100),
      prevVitality: v,
      missedDays: missedDaysBefore(d.date),
    });
    v = st.vitality;
  }
  return v;
}

/** 某天之前连续断签天数 */
function missedDaysBefore(date) {
  const sorted = seed.days.filter((d) => d.date < date).sort((a, b) => b.date.localeCompare(a.date));
  let missed = 0;
  for (const d of sorted) {
    if ((d.duration_minutes || 0) === 0) missed++;
    else break;
  }
  return missed;
}

/** 今日状态：优先用今天上传的记录，没有就用 seed 里最近一天 */
function buildToday() {
  const t = today();
  const records = readRecords();
  const todayRecs = records.filter((r) => (r.record && r.record.event_date) === t);

  let minutes = 0, accuracy = null, late = false, has = todayRecs.length > 0, startTime = null, endTime = null;

  if (has) {
    const last = todayRecs[todayRecs.length - 1].record;
    minutes = last.duration_minutes || 0;
    accuracy = last.accuracy;
    startTime = last.event_time;
    endTime = last.event_time;
    late = isLateNight(last.event_time, last.event_time, minutes);
  } else {
    // 没有今日记录：回落到 seed 最近一天（保证今日屏不空白）
    const past = seed.days.filter((d) => (d.duration_minutes || 0) > 0).sort((a, b) => b.date.localeCompare(a.date));
    const last = past[0];
    if (last) {
      minutes = last.duration_minutes; accuracy = last.accuracy;
      startTime = last.start_time; endTime = last.end_time;
      late = isLateNight(last.start_time, last.end_time, minutes);
    }
  }

  const prevVitality = rollPrevVitality(t);
  const state = computeDailyState({
    minutes,
    completion: completionOf(minutes),
    energy: energyOf(minutes, late),
    progress: Math.round((accuracy || 0) * 100),
    prevVitality,
    missedDays: missedDaysBefore(t),
  });

  // 缺口行：本周目标 5 次
  const weekStart = new Date(new Date(t).getTime() - 6 * 86400000).toISOString().slice(0, 10);
  const weekDone = new Set(
    seed.days.filter((d) => d.date >= weekStart && d.date <= t && (d.duration_minutes || 0) > 0).map((d) => d.date)
      .concat(todayRecs.length ? [t] : [])
  ).size;
  const target = (seed.gap && seed.gap.week_target) || 5;

  return {
    date: t,
    has_record: has,
    pet_state: state.petState,
    vitality: state.vitality,
    user_state: state.userState,
    phrase_level: petStateToPhraseLevel(state.petState),
    gap: { week_target: target, week_done: weekDone, owed: Math.max(0, target - weekDone) },
    detail: {
      duration_minutes: minutes,
      accuracy,
      energy: state.energy,
      progress: state.progress,
      completion: state.completion,
      late_night: late,
    },
  };
}

function buildMemories() {
  const t = today();
  return (seed.memories || []).map((m) => ({
    id: m.id,
    type: m.type,
    days_ago: m.days_ago,
    said_at: m.said_at,
    quote: m.quote,
    module: m.module || null,
    then_accuracy: m.then_accuracy ?? null,
    week_accuracy: m.week_accuracy ?? null,
    question: m.question || null,
    detail: m.detail || null,
  }));
}

function send(res, code, obj) {
  const body = JSON.stringify(obj, null, 2);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const p = url.pathname;

  if (req.method === 'OPTIONS') return send(res, 204, {});

  if (p === '/api/health') return send(res, 200, { ok: true, service: 'mock-server', today: today() });

  if (p === '/api/today') return send(res, 200, buildToday());

  if (p === '/api/memories') return send(res, 200, { items: buildMemories() });

  if (p === '/api/records' && req.method === 'POST') {
    let raw = '';
    req.on('data', (c) => (raw += c));
    req.on('end', () => {
      try {
        const payload = JSON.parse(raw);
        if (!payload.record) return send(res, 400, { ok: false, error: '缺 record 字段' });
        const records = readRecords();
        const rec = { id: 'r' + (records.length + 1), ...payload, server_received_at: new Date().toISOString() };
        records.push(rec);
        writeRecords(records);
        console.log('[入库] id=%s  edited_fields=%j', rec.id, payload.edited_fields);
        return send(res, 200, { ok: true, record_id: rec.id, today: buildToday() });
      } catch (e) {
        return send(res, 400, { ok: false, error: e.message });
      }
    });
    return;
  }

  // 调试用：看全部已入库记录
  if (p === '/api/records' && req.method === 'GET') return send(res, 200, { items: readRecords() });

  send(res, 404, { ok: false, error: 'not found: ' + p });
});

server.listen(PORT, () => {
  console.log('mock-server 已启动: http://127.0.0.1:' + PORT);
  console.log('  GET  /api/today      今日状态（含 gap 缺口行）');
  console.log('  GET  /api/memories   记忆屏 3 条');
  console.log('  POST /api/records    入库');
});
