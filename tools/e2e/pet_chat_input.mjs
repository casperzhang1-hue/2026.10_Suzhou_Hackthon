/* 手打对话验证：真实鼠标长按唤起面板 → 在输入框里输入（模拟中文输入法上屏）→ 回车发送。
   覆盖四个容易漏的点：
   1) 面板顶部的引擎状态是不是真的从 /api/pet/llm 拿到；
   2) 输入框能不能键入、回车能不能发出（IME 选词时回车不该发）；
   3) 逐字上屏结束后 meta 标的是不是「团团 · 模型名」；
   4) 全程有没有 console 异常。 */
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
  for (let i = 0; i < 60; i++) {
    await sleep(300);
    lines = await ev(send, LINES);
    if (!Array.isArray(lines)) continue;
    const last = lines[lines.length - 1];
    if (last && last.meta && lines.length > before) break;
  }
  return lines;
}

(async () => {
  const ws = new WebSocket(await pickPage());
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const { send, events } = rpc(ws);
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.reload', { ignoreCache: true });
  await sleep(4000);

  const box = await ev(send, `(function(){
    var el=document.querySelector('#homePet'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width) };
  })()`);
  if (!box || !box.w) throw new Error('找不到 #homePet');
  console.log('宠物位置 ' + JSON.stringify(box));

  // 长按 900ms 唤起面板
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(900);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(2400);
  const opened = await ev(send, `(function(){var p=document.querySelector('.pchat');return !!(p&&p.classList.contains('on'));})()`);
  console.log('长按 900ms → 面板开=' + opened);
  if (!opened) throw new Error('长按没有唤起面板');

  console.log('引擎状态：' + (await ev(send, `(document.getElementById('petEngine')||{}).textContent`)));

  // 点输入框聚焦（真实点击，验证没被其他浮层挡住）
  const inp = await ev(send, `(function(){
    var el=document.getElementById('petChatIn'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width), h:Math.round(r.height) };
  })()`);
  if (!inp || !inp.w) throw new Error('找不到输入框');
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: inp.x, y: inp.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: inp.x, y: inp.y, button: 'left', clickCount: 1 });
  await sleep(200);
  const focused = await ev(send, `document.activeElement && document.activeElement.id`);
  console.log('点输入框 → 焦点=' + focused);

  // 模拟中文输入法上屏（insertText 与真实输入法提交走同一个 path）
  const words = '我今天学不动了，感觉考不上了';
  await send('Input.insertText', { text: words });
  await sleep(200);
  const typed = await ev(send, `document.getElementById('petChatIn').value`);
  console.log('输入框内容：' + typed);
  if (typed !== words) throw new Error('输入框没吃到字：' + typed);

  const before = (await ev(send, LINES)).length;
  // 回车发送
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });

  const lines = await waitForReply(send, before);
  console.log('\n对话记录：');
  lines.forEach((l) => console.log('  [' + (l.who.includes('me') ? '我' : '团团') + '] ' + l.text + (l.meta ? '   《' + l.meta + '》' : '')));

  const ans = lines.filter((l) => l.who.includes('pet')).pop() || {};
  console.log('\n输入框发出去后：' + (ans.meta && ans.meta.includes('团团 ·') ? '模型回答 ✓' : '未走模型 · meta=' + ans.meta));
  console.log('发完是否清空：' + ((await ev(send, `document.getElementById('petChatIn').value`)) === '' ? '是 ✓' : '否 ✗'));

  // 再点一个话题，确认按钮路径也走同一张嘴
  const btn = await ev(send, `(function(){
    var b=document.querySelector('.pchat-topic[data-intent="promise"]'); if(!b) return null;
    var r=b.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2) };
  })()`);
  const before2 = (await ev(send, LINES)).length;
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: btn.x, y: btn.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: btn.x, y: btn.y, button: 'left', clickCount: 1 });
  const lines2 = await waitForReply(send, before2);
  const ans2 = lines2.filter((l) => l.who.includes('pet')).pop() || {};
  console.log('\n点「那个承诺」→ ' + ans2.text + '   《' + (ans2.meta || '') + '》');

  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  const warns = events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type !== 'log');
  console.log('\n未捕获异常：' + errs.length + ' 条；warn/error 日志：' + warns.length + ' 条');
  warns.slice(0, 4).forEach((w) => console.log('  ' + (w.params.args || []).map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 120)));
  ws.close(); process.exit(0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
