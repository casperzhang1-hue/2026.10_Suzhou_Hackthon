/**
 * 状态引擎 —— 从 A 的原型原样移植（prototype/仓鼠陪跑_原型_接真数据版.html 761-805 行）
 *
 * ⚠️ B 注意：直接复用这个文件，不要重写。
 *    重写会导致「前端一套算法、后端一套算法」，现场两套结果不一致。
 *
 * 硬要求：纯函数，同样输入永远同样输出（任务卡：否则现场回放就翻车）
 */

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function r1(v) { return Math.round(v * 10) / 10; }

/** 非对称活力值：表现差只掉 25%，表现好立刻涨 40%（任务卡 5.3，方向不可改） */
function computeVitality(prev, completion) {
  var c = clamp(completion, 0, 1.2);
  var next = (c < 0.5)
    ? 0.75 * prev + 0.25 * (c * 100)   // 恶化慢：断一天只是蔫一点
    : 0.60 * prev + 0.40 * (c * 100);  // 回暖快：回来第一天就涨
  return Math.floor(clamp(next, 0, 100));
}

/** 宠物五态（仓鼠） */
function petStateOf(v, energy, minutes, missedDays) {
  if (missedDays >= 7) return 'sleep';
  if (minutes >= 200 && energy < 45 && v >= 52) return 'tired'; // 学太猛，反而是劝停
  if (v >= 78) return 'vigour';
  if (v >= 55) return 'steady';
  if (v >= 30) return 'wilt';
  return 'sleep';
}

/** 用户四态（给机器决策用，和宠物形态故意错位） */
function userStateOf(energy, progress) {
  if (energy < 40 && progress < 45) return '崩溃前兆';
  if (energy < 40 && progress >= 45) return '过载';   // 最值钱的一格
  if (energy >= 40 && progress < 45) return '平台期';
  return '稳';
}

/**
 * @param {{minutes:number, completion:number, energy:number, progress:number,
 *          prevVitality:number, missedDays:number}} inp
 */
function computeDailyState(inp) {
  var minutes = Math.max(0, inp.minutes || 0);
  var completion = inp.completion;
  var v = computeVitality(inp.prevVitality || 50, completion);
  var pet = petStateOf(v, inp.energy || 50, minutes, inp.missedDays || 0);
  return {
    completion: r1(completion),
    netMinutes: Math.round(minutes),
    energy: Math.round(inp.energy || 0),
    progress: Math.round(inp.progress || 0),
    prevVitality: Math.round(inp.prevVitality || 0),
    vitality: v,
    userState: userStateOf(inp.energy || 0, inp.progress || 0),
    petState: pet,
  };
}

/** 宠物五态 → C 的话术档位（phrases.json 的四个 key） */
function petStateToPhraseLevel(petState) {
  return { vigour: 'excellent', steady: 'good', tired: 'low', wilt: 'low', sleep: 'low' }[petState] || 'normal';
}

module.exports = {
  clamp, r1, computeVitality, petStateOf, userStateOf, computeDailyState, petStateToPhraseLevel,
};
