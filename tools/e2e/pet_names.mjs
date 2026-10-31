/* 名字这类问题的真机回归：用户截图里
   「团团我叫什么」→「你叫我团团时，我耳朵尖尖的」
   「你应该叫我什么」→「你叫我团团就行啦」
   两问的是**他**的名字，答的都是它自己的名字。

   这个脚本按真实路径走两遍：
   ① 还没告诉它名字 → 它必须认「不知道」，不许把「团团」当他的名字；
   ② 告诉它「我叫林一」→ 再问一次，它得叫出「林一」。

   顺带验三类同样容易「答得流利但答非所问」的问法：你是谁 / 你能干什么 / 你喜欢我吗。 */
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

/* 手打一句，走跟真人一样的路：点输入框 → insertText → 回车 */
async function say(send, text) {
  const before = (await ev(send, LINES)).length;
  const inp = await ev(send, `(function(){
    var el=document.getElementById('petChatIn'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width) };
  })()`);
  if (!inp || !inp.w) throw new Error('找不到输入框');
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: inp.x, y: inp.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: inp.x, y: inp.y, button: 'left', clickCount: 1 });
  await sleep(150);
  await ev(send, `(function(){var e=document.getElementById('petChatIn'); e.value=''; e.focus();})()`);
  await send('Input.insertText', { text });
  await sleep(200);
  const typed = await ev(send, `document.getElementById('petChatIn').value`);
  if (typed !== text) throw new Error('输入框没吃到字：' + typed);
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  const lines = await waitForReply(send, before);
  const pet = lines.filter((l) => l.who.includes('pet') && l.meta).pop() || {};
  return { q: text, a: pet.text || '', meta: pet.meta || '' };
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
  const ok = await ev(send, `(function(){
    var el=document.querySelector('#homePet'); var r=el.getBoundingClientRect();
    var h=document.elementFromPoint(Math.round(r.left+r.width/2), Math.round(r.top+r.height/2));
    return !!(h && (el===h || el.contains(h)));
  })()`);
  if (!ok) throw new Error('落点被挡住，拒绝点击');
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(900);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(2200);
  const opened = await ev(send, `(function(){var p=document.querySelector('.pchat');return !!(p&&p.classList.contains('on'));})()`);
  if (!opened) throw new Error('长按没有唤起面板');

  /* 先把库里的名字清掉，保证第一轮是「它还不知道」的状态。
     演示库里可能已经存过名字，不清的话第一问就答「林一」，验不到「不知道」这条。
     注意必须在 Node 侧直连 8000：页面在 8899，相对的 /api 打到的是静态服务器，404。 */
  const API = 'http://127.0.0.1:8000';
  const mem = await fetch(`${API}/api/memories`).then((r) => r.json());
  const nameIds = (mem.items || []).filter((m) => m.type === 'name').map((m) => m.id);
  for (const id of nameIds) {
    await fetch(`${API}/api/memories/${id}`, { method: 'DELETE' });
  }
  if (nameIds.length) console.log('先清掉 ' + nameIds.length + ' 条旧名字记忆');

  const rounds = [];
  rounds.push(await say(send, '团团我叫什么'));
  rounds.push(await say(send, '你应该叫我什么'));
  rounds.push(await say(send, '你是谁'));
  rounds.push(await say(send, '你能干什么'));
  rounds.push(await say(send, '你喜欢我吗'));
  rounds.push(await say(send, '我叫林一'));
  rounds.push(await say(send, '你应该叫我什么'));

  console.log('');
  rounds.forEach((r) => {
    console.log('我　：' + r.q);
    console.log('团团：' + r.a + '   《' + (r.meta || '') + '》\n');
  });

  const [a1, a2, , cap, rel, , a4] = rounds.map((r) => r.a || '');
  const checks = {
    '不知道名字时，不编也不把「团团」当他的名字': !/你叫我?团团/.test(a1 + a2) && /不知道|没告诉|告诉我|叫什么/.test(a1),
    '问「你是谁」答的是自己的名字': /团团/.test(rounds[2].a || '') && /我叫|我是/.test(rounds[2].a || ''),
    '问「你能干什么」答的是能力': /截图|图片|记录|记住|账|陪你/.test(cap),
    '问「你喜欢我吗」正面答了': /喜欢|陪|在乎|不走/.test(rel),
    '报了名字之后叫得出来': /林一/.test(a4),
    '来源都标了模型': rounds.every((r) => /qwen/.test(r.meta || '')),
  };
  console.log('—— 判定 ——');
  Object.entries(checks).forEach(([k, v]) => console.log(k.padEnd(28, ' ') + ' : ' + (v ? '✓' : '✗')));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  if (shot.result?.data) {
    writeFileSync('shot_names.png', Buffer.from(shot.result.data, 'base64'));
    console.log('\n截图：tools/e2e/shot_names.png');
  }
  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  console.log('未捕获异常：' + errs.length + ' 条');
  const bad = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
  ws.close();
  process.exit(bad.length || errs.length ? 1 : 0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
