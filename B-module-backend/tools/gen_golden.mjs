// 从 A 的原型 HTML 抽出 computeDailyState，生成 Python 版对拍用的 golden.json
// 用法：node tools/gen_golden.mjs <原型.html> > tests/golden.json
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const html = readFileSync(process.argv[2], 'utf8')
const grab = (name) => {
  const start = html.indexOf(`function ${name}(`)
  if (start < 0) throw new Error(`未找到 ${name}`)
  let depth = 0, i = html.indexOf('{', start)
  for (let j = i; j < html.length; j++) {
    if (html[j] === '{') depth++
    else if (html[j] === '}' && --depth === 0) return html.slice(start, j + 1)
  }
}
const src = ['clamp', 'r1', 'computeVitality', 'petStateOf', 'userStateOf'].map(grab).join('\n')
const ctx = vm.createContext({})
vm.runInContext(src + `
function core(inp){
  var minutes = Math.max(0, inp.minutes||0);
  var v = computeVitality(inp.prevVitality, inp.completion);
  return { completion: r1(inp.completion), netMinutes: Math.round(minutes),
    energy: Math.round(inp.energy), progress: Math.round(inp.progress),
    prevVitality: Math.round(inp.prevVitality), vitality: v,
    userState: userStateOf(inp.energy, inp.progress),
    petState: petStateOf(v, inp.energy, minutes, inp.missedDays||0) };
}`, ctx)

const base = { prevVitality: 70, completion: 0.8, energy: 70, progress: 68, minutes: 58, missedDays: 0 }
const cases = [
  ['正常', {}],
  ['断签1天', { completion: 0, minutes: 0, missedDays: 1, energy: 62, progress: 60 }],
  ['断签7天', { prevVitality: 40, completion: 0, minutes: 0, missedDays: 7, energy: 50, progress: 50 }],
  ['过载', { prevVitality: 75, completion: 1.2, energy: 31, progress: 58, minutes: 372 }],
  ['回归', { prevVitality: 25, completion: 0.93, energy: 70, progress: 68 }],
  ['新用户', { prevVitality: 50, completion: 0.6, energy: 60, progress: 50, minutes: 30 }],
  ['平台期', { energy: 70, progress: 30 }],
  ['崩溃前兆', { energy: 30, progress: 30, completion: 0.3, minutes: 10 }],
  ['完成度越界', { completion: 1.5, prevVitality: 100 }],
  ['活力地板', { prevVitality: 0, completion: 0 }],
  ['临界0.5', { prevVitality: 60, completion: 0.5 }],
  ['临界0.49', { prevVitality: 60, completion: 0.49 }],
  ['缺失minutes', { minutes: undefined, missedDays: undefined }],
]
const out = cases.map(([name, o]) => {
  const input = { ...base, ...o }
  Object.keys(input).forEach((k) => input[k] === undefined && delete input[k])
  return { name, input, expected: ctx.core(input) }
})
console.log(JSON.stringify(out, null, 2))
