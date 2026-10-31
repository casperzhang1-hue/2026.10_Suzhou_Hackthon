/* 真实手势验证：用 CDP 发真的鼠标事件，按住 #homePet 900ms 唤起面板，
   再点「我哪里最毛」，看是否走通模型链路。
   这一步不能靠 page 里调 openChat() 代替——按压力学、800ms 阈值、contextmenu 拦截都在事件层。 */
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
  if (r.result?.exceptionDetails) return { __err: r.result.exceptionDetails.exception?.description };
  return r.result?.result?.value;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const ws = new WebSocket(await pickPage());
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const { send, events } = rpc(ws);
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.reload', { ignoreCache: true });
  await sleep(3500);

  const box = await ev(send, `
    (function(){
      var el = document.querySelector('#homePet');
      if(!el) return null;
      var r = el.getBoundingClientRect();
      return { x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2), w: Math.round(r.width), h: Math.round(r.height) };
    })()
  `);
  if (!box || !box.w) throw new Error('找不到 #homePet');
  console.log('宠物位置：' + JSON.stringify(box));

  // 短按：不该唤起面板，只该冒一句话
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(120);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(400);
  const shortTap = await ev(send, `(function(){var p=document.querySelector('.pchat');return {open: !!(p && p.classList.contains('on')), bubble: (document.querySelector('.pet-bubble .txt')||{}).textContent || ''};})()`);
  console.log('短按 120ms → 面板开=' + shortTap.open + '  气泡=' + shortTap.bubble);

  // 长按 900ms：应该唤起面板并说「想问什么」
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(900);
  const during = await ev(send, `(function(){var p=document.querySelector('.pchat');return {open: !!(p && p.classList.contains('on')), bubble: (document.querySelector('.pet-bubble .txt')||{}).textContent || ''};})()`);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  console.log('长按 900ms → 面板开=' + during.open + '  气泡=' + during.bubble);
  if (!during.open) throw new Error('长按没有唤起对话面板');
  await sleep(700);   /* 等底部卡片弹出动画停稳，否则拿到的坐标是动画中途的位置 */

  // 点真实按钮（不是调函数）
  const btn = await ev(send, `
    (function(){
      var b = document.querySelector('.pchat-topic[data-intent="weak"]');
      if(!b) return null;
      var r = b.getBoundingClientRect();
      return { x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2) };
    })()
  `);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: btn.x, y: btn.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: btn.x, y: btn.y, button: 'left', clickCount: 1 });

  let lines = [];
  for (let i = 0; i < 40; i++) {
    await sleep(300);
    lines = await ev(send, `
      Array.from(document.querySelectorAll('.pchat-log .pchat-line')).map(function(l){
        var b=l.querySelector('.pchat-bub'), m=l.querySelector('.pchat-meta');
        return { who:l.className, text:(b&&b.textContent)||'', meta:(m&&m.textContent)||'' };
      })
    `);
    const last = lines[lines.length - 1];
    if (last && last.meta) break;
  }
  console.log('\n对话记录：');
  lines.forEach((l) => console.log('  [' + (l.who.includes('me') ? '我' : '仓鼠') + '] ' + l.text + (l.meta ? '   《' + l.meta + '》' : '')));

  const ans = (lines.filter((l) => l.who.includes('pet')).pop() || {});
  // meta 由后端给：走模型是「团团 · 模型名」，掉兜底是「模型没接上，它凭记忆说」
  console.log('\n结论：' + (ans.meta && ans.meta.includes('团团 ·') ? '长按 → 点话题 → 模型回答 ✓' : '未走模型链路 ✗「' + (ans.meta || '无 meta') + '」'));

  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  console.log('未捕获异常：' + errs.length);
  ws.close(); process.exit(0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
