// 12 条话术终稿 —— FR-09：主语含「我」、无感叹号、无禁用词（加油/你一定行/坚持就是胜利…）
// 基于 C 模块 phrases.json 草稿（10/12 直接采用），修订 2 条：
//   low[2]  原句引导拖延（"错题先放着"）→ 改为记录动作
//   excellent[1] 原句说教且带"你"（"我建议你加点难度"）→ 改为第一人称
export const PHRASES = {
  low: [
    '我看这次正确率偏低，先歇会儿再看',
    '这次题量不多，我陪你慢慢补上',
    '错题我先记下来，明天接着看',
  ],
  normal: [
    '我看今天节奏挺稳，做完就是进度',
    '这次没有中断，我陪你接着往下走',
    '正确率中规中矩，我看基础还在',
  ],
  good: [
    '我看这次节奏很稳，不慌不乱',
    '正确率在线，我看着挺放心',
    '这次手感不错，我看方向是对的',
  ],
  excellent: [
    '正确率和时长都漂亮，我看着高兴',
    '这次发挥很稳，我要给自己记一功',
    '三项数据都好，我陪你试更高的题',
  ],
}

export function getPhrase(level) {
  const pool = PHRASES[level] || PHRASES.normal
  return pool[Math.floor(Math.random() * pool.length)]
}
