/* 「所以我今天就不用学习了吗」—— 用户截图里最戳人的那一幕。
   它的答法从「我帮你剥了颗瓜子搁在题本上」变成了「今天够了，你学了 82 分钟，过了 80 的线」。

   验四件事：
   1) 面板顶上新加的那行账（今天多少分钟 / 本周还差几天）真的显示出来了；
   2) 手打一句要主意的话，回来的回答里有结论、有数，meta 标的是「按上面那行账算的」；
   3) 它不再说「我听见了」这种空话，也不再复读他上一句；
   4) 全程 0 异常。 */
import { writeFileSync } from 'node:fs';

const CDP_PORT = 9333;

async function pickPage() {
  const list = await fetch(`http://127.0.0.1:${CDP_PORT}/json`).then((r) => r.json());
  return list.find((t) => t.type === 'page' && t.url.includes('8899')).webSocketDebuggerUrl;
}
function rpc(ws) {
  let id = 0; const pending = new Map(); const events = [];
  ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === 'Runtime.consoleAPICalled' || m.method === 'Runtime.exceptionThrown') events.push(m);
  });
  const send = (method, params) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params: params || {} })); });
  return { send, events };
}
async function ev(send, expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.error) return { __cdp: r.error.message };
  if (r.result?.exceptionDetails) return { __err: r.result.exceptionDetails.exception?.description };
  return r.result?.result?.value;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const LINES = `Array.from(document.querySelectorAll('.pchat-log .pchat-line')).map(function(l){
  var b=l.querySelector('.pchat-bub'), m=l.querySelector('.pchat-meta');
  return { who:l.className, text:(b&&b.textContent)||'', meta:(m&&m.textContent)||'' };
})`;

async function waitForReply(send, before) {
  let lines = [];
  for (let i = 0; i < 90; i++) {
    await sleep(400);
    lines = await ev(send, LINES);
    if (!Array.isArray(lines)) continue;
    const last = lines[lines.length - 1];
    if (last && last.meta && lines.length > before) break;
  }
  return lines;
}

async function say(send, text) {
  const inp = await ev(send, `(function(){
    var el=document.getElementById('petChatIn'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width) };
  })()`);
  if (!inp || !inp.w) throw new Error('找不到输入框');
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: inp.x, y: inp.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: inp.x, y: inp.y, button: 'left', clickCount: 1 });
  await sleep(150);
  await send('Input.insertText', { text });
  await sleep(150);
  const typed = await ev(send, `document.getElementById('petChatIn').value`);
  if (typed !== text) throw new Error('输入框没吃到字：' + typed);
  const before = (await ev(send, LINES)).length;
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  return await waitForReply(send, before);
}

(async () => {
  const ws = new WebSocket(await pickPage());
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const { send, events } = rpc(ws);
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.reload', { ignoreCache: true });
  await sleep(4500);

  const box = await ev(send, `(function(){
    var el=document.querySelector('#homePet'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width) };
  })()`);
  if (!box || !box.w) throw new Error('找不到 #homePet');

  /* 按之前先确认鼠标真的落在宠物身上。踩过坑：长按的落点飘到了「今天没学」，
     库里立刻多一条 58 分钟、0 题、没有时刻的记录——界面上完全看不出来，
     但宠物会拿着假数据跟他汇报，今日时长还会从 82 变成 140。 */
  const hit = await ev(send, `(function(){
    var el=document.querySelector('#homePet');
    var r=el.getBoundingClientRect();
    var h=document.elementFromPoint(Math.round(r.left+r.width/2), Math.round(r.top+r.height/2));
    return { ok: !!(h && (el===h || el.contains(h))), hit: h ? String(h.id || h.className || h.tagName) : null };
  })()`);
  if (!hit || !hit.ok) throw new Error('落点被挡住，拒绝点击（避免误触别的按钮）：' + (hit && hit.hit));
  console.log('落点校验：' + hit.hit);

  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(900);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(2200);
  const opened = await ev(send, `(function(){var p=document.querySelector('.pchat');return !!(p&&p.classList.contains('on'));})()`);
  if (!opened) throw new Error('长按没有唤起面板');

  const ctx = await ev(send, `(function(){var e=document.getElementById('petCtx');return e?e.textContent:'';})()`);
  console.log('面板上的账：' + (ctx || '（空）'));

  let lines = await say(send, '我不累啊');
  const a1 = lines.filter((l) => l.who.includes('pet')).pop() || {};
  console.log('\n我　：我不累啊');
  console.log('团团：' + a1.text + '   《' + (a1.meta || '') + '》');

  lines = await say(send, '所以我今天就不用学习了吗');
  const a2 = lines.filter((l) => l.who.includes('pet')).pop() || {};
  console.log('\n我　：所以我今天就不用学习了吗');
  console.log('团团：' + a2.text + '   《' + (a2.meta || '') + '》');

  lines = await say(send, '我是不是特别笨');
  const a3 = lines.filter((l) => l.who.includes('pet')).pop() || {};
  console.log('\n我　：我是不是特别笨');
  console.log('团团：' + a3.text + '   《' + (a3.meta || '') + '》');

  console.log('\n—— 判定 ——');
  console.log('账行有数          : ' + (/\d+\s*分钟/.test(ctx) ? '✓' : '✗ ' + ctx));
  console.log('回答里有结论      : ' + (/够|停|别|再|歇|明天|收工|可以/.test(a2.text || '') ? '✓' : '✗'));
  console.log('回答里有真数      : ' + (/\d/.test(a2.text || '') ? '✓' : '✗'));
  console.log('meta 标了依据     : ' + (/按上面那行账/.test(a2.meta || '') ? '✓' : '✗ ' + a2.meta));
  console.log('没说「我听见了」  : ' + (/我听见了|我听到了/.test((a1.text || '') + (a2.text || '')) ? '✗' : '✓'));
  console.log('没复读上一句      : ' + (/你刚说不累/.test(a2.text || '') ? '✗' : '✓'));
  console.log('难受那句不报数    : ' + (/\d/.test(a3.text || '') ? '✗ ' + a3.text : '✓'));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  if (shot.result?.data) {
    writeFileSync('shot_advice.png', Buffer.from(shot.result.data, 'base64'));
    console.log('\n截图：tools/e2e/shot_advice.png');
  }

  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  const warns = events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type !== 'log');
  console.log('\n未捕获异常：' + errs.length + ' 条；warn/error：' + warns.length + ' 条');
  warns.slice(0, 4).forEach((w) => console.log('  ' + (w.params.args || []).map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 120)));
  ws.close(); process.exit(0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
