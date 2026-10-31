/* 按《宠物对话约束清单》验三件事，都是在真浏览器里手打发问：

   1) 「今天学了多久」「我今天做了什么」这种问法要落到 data 的 today ——
      以前它们不带「多少」，整句落进 normal，它就去念图里那道题；
   2) 「这周还差几天」是**另一本账**，要报天数，不能拿今天的分钟数顶上；
   3) 「再学一会儿吗」和「今天还用学吗」问的是同一件事，答得像是对的，
      但重问一次必须换说法（逐字照抄会被出口挡下）。

   口径：全部走模型（0 兜底）、每句都有真数、同一件事重问不能一个字都不差。
*/
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
    if (m.method === 'Runtime.exceptionThrown') events.push(m);
  });
  const send = (method, params) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params: params || {} })); });
  return { send, events };
}
async function ev(send, expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
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

async function ask(send, text) {
  const inp = await ev(send, `(function(){
    var el=document.getElementById('petChatIn'); if(!el) return null;
    var r=el.getBoundingClientRect();
    var h=document.elementFromPoint(Math.round(r.left+r.width/2), Math.round(r.top+r.height/2));
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width),
             ok: !!(h && (el===h || el.contains(h))) };
  })()`);
  if (!inp || !inp.w) throw new Error('找不到输入框');
  if (!inp.ok) throw new Error('输入框被浮层挡住');
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
  const lines = await waitForReply(send, before);
  const pet = lines.filter((l) => l.who.includes('pet') && l.meta).pop() || {};
  return { q: text, pet: pet.text || '', meta: pet.meta || '' };
}

const bare = (s) => (s || '').replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, '');

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
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(900);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(2200);
  const opened = await ev(send, `(function(){var p=document.querySelector('.pchat');return !!(p&&p.classList.contains('on'));})()`);
  if (!opened) throw new Error('长按没有唤起面板');

  const ctx = await ev(send, `(function(){var e=document.getElementById('petCtx');return e?e.textContent:'';})()`);
  console.log('面板上的账：' + (ctx || '（空）'));

  const rounds = [];
  for (const q of ['今天学了多久', '我今天做了什么', '这周还差几天', '再学一会儿吗', '今天还用学吗']) {
    rounds.push(await ask(send, q));
  }

  console.log('');
  rounds.forEach((r) => {
    console.log('我　：' + r.q);
    console.log('团团：' + r.pet + '   《' + (r.meta || '') + '》\n');
  });

  const by = (q) => (rounds.find((r) => r.q === q) || {});
  const dur = by('今天学了多久').pet || '';
  const did = by('我今天做了什么').pet || '';
  const week = by('这周还差几天').pet || '';
  const a1 = by('再学一会儿吗').pet || '';
  const a2 = by('今天还用学吗').pet || '';

  const checks = {
    '问学了多久，答的是分钟数': /\d+\s*分钟/.test(dur),
    '问做了什么，答的也是分钟数': /\d+\s*分钟/.test(did),
    '问这周还差几天，答的是天数': /\d+\s*天/.test(week) && /\d+\s*分钟/.test(week) === false,
    '问该不该学，给了明确结论': /够|停|歇|再|别|睡|到这儿|明天/.test(a1 + a2),
    '同一件事重问，话不一样了': a1 && a2 && bare(a1) !== bare(a2),
    /* 判断类的 meta 是「按上面那行账算的」（前端给判断结果加的标注），
       不是兜底。兜底只有两种写法：「模型没接上」「刚才那句绕回去了」。 */
    '一句都没掉兜底': rounds.every((r) => !/没接上|绕回去了|嘴没连上/.test(r.meta || '')),
  };
  console.log('—— 判定 ——');
  Object.entries(checks).forEach(([k, v]) => console.log(k.padEnd(20, ' ') + ' : ' + (v ? '✓' : '✗')));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  if (shot.result?.data) {
    writeFileSync('shot_accounts.png', Buffer.from(shot.result.data, 'base64'));
    console.log('\n截图：tools/e2e/shot_accounts.png');
  }
  console.log('未捕获异常：' + events.length + ' 条');
  const bad = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
  ws.close();
  process.exit(bad.length || events.length ? 1 : 0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
