// C 模块识别结果 → 宠物信号 的桥接（演示版映射，先定死，之后和 D 对一版）
// 输入是 Recognition JSON，输出喂给 petStateOf / computeDailyState 的参数
export function recognitionToPetInput(rec) {
  const duration = rec?.duration_minutes ?? 0
  const accuracy = rec?.accuracy
  const total = rec?.total_questions ?? 0

  // completion：有正确率就用正确率，没有就按时长兜底
  const completion = (typeof accuracy === 'number' && accuracy !== null)
    ? accuracy
    : clamp(duration / 60, 0, 1)

  // overload 检测：>200 分钟或刷题量过大视为过载信号
  const overloaded = duration > 200 || (total > 80 && (accuracy ?? 1) < 0.55)

  return {
    minutes: duration,
    completion: clamp(completion, 0, 1.2),
    energy: overloaded ? 32 : (typeof accuracy === 'number' ? 55 + accuracy * 30 : 58),
    progress: 60,
    missedDays: 0,
  }
}

// level（C 的 encouragement.level）→ 仓鼠形态直映（演示兜底用）
export const LEVEL_TO_STATE = {
  excellent: 'vigour',
  good: 'steady',
  normal: 'tired',
  low: 'wilt',
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)) }
