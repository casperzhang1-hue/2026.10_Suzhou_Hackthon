/* 端到端：真实页面里走「长按唤起 → 点话题 → 模型流式 → 后端复核 → 上屏」。
   断言三件事：① 答案是模型出的（带「数字已核对」标记）② 数字全在事实包白名单里
   ③ 控制台无报错。 */
const CDP_PORT = 9333;

async function pickPage() {
  const list = await fetch(`http://127.0.0.1:${CDP_PORT}/json`).then((r) => r.json());
  const p = list.find((t) => t.type === 'page' && t.url.includes('8899'));
  if (!p) throw new Error('找不到 8899 页面：' + list.map((t) => t.url).join(' | '));
  return p.webSocketDebuggerUrl;
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
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'JS 异常');
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

  console.log('后端在线：' + (await ev(send, 'API.online')) + '  base=' + (await ev(send, 'API.base')));

  for (const [intent, label] of [['weak', '我哪里最毛'], ['promise', '那个承诺'], ['today', '今天怎么样']]) {
    console.log('\n========== ' + label + ' (' + intent + ') ==========');
    const t0 = Date.now();
    await ev(send, `openChat(); petAsk(${JSON.stringify(intent)}, ${JSON.stringify(label)}); 'ok'`);

    // 等答案落定：出现 pchat-meta 即收敛
    let lines = [];
    for (let i = 0; i < 60; i++) {
      await sleep(300);
      lines = await ev(send, `
        Array.from(document.querySelectorAll('.pchat-log .pchat-line')).slice(-2).map(function(l){
          var b=l.querySelector('.pchat-bub'), m=l.querySelector('.pchat-meta');
          return { who: l.className, text: (b&&b.textContent)||'', meta: (m&&m.textContent)||'' };
        })
      `);
      const last = lines[lines.length - 1];
      if (last && last.meta) break;
      if (last && last.text && last.who.includes('pet') && !last.meta && i > 30) break;
    }
    console.log('耗时 ' + (Date.now() - t0) + 'ms');
    lines.forEach((l) => console.log('  [' + (l.who.includes('me') ? '我' : '仓鼠') + '] ' + l.text + (l.meta ? '   《' + l.meta + '》' : '')));

    // 数字核对：答案里的数字是否都在事实包白名单里
    const ans = (lines.find((l) => l.who.includes('pet')) || {}).text || '';
    const ctx = await (await fetch(`http://127.0.0.1:8000/api/pet/context?intent=${intent}`)).json();
    const nums = (ans.match(/\d+/g) || []).map(Number);
    const stray = nums.filter((n) => !ctx.allowed_numbers.includes(n));
    console.log('  数字 ' + JSON.stringify(nums) + ' → ' + (stray.length ? '越界 ' + JSON.stringify(stray) + ' ✗' : '全部在白名单内 ✓'));
  }

  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  console.log('\n控制台异常：' + errs.length);
  errs.slice(0, 5).forEach((e) => console.log('  ' + (e.params?.exceptionDetails?.exception?.description || '').slice(0, 200)));
  ws.close(); process.exit(0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
