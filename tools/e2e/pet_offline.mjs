/* 降级验证：把页面切成离线，点话题应落到 PET_FALLBACK，且一个数字都不许出现。
   顺带验证「模板嘴」那一层仍然可用（离线时它只能给兜底话术）。 */
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
  await send('Runtime.enable'); await send('Network.enable');

  // 先刷新让 SDK 进入已加载状态（模拟现场：网先通、后来断）
  await send('Page.reload', { ignoreCache: true });
  await sleep(3500);
  await ev(send, `openChat(); 'ok'`);

  console.log('切到离线…');
  await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });

  await ev(send, `petAsk('weak', '我哪里最毛'); 'ok'`);
  let lines = [];
  for (let i = 0; i < 20; i++) {
    await sleep(300);
    lines = await ev(send, `
      Array.from(document.querySelectorAll('.pchat-log .pchat-line')).slice(-2).map(function(l){
        var b=l.querySelector('.pchat-bub'), m=l.querySelector('.pchat-meta');
        return { who:l.className, text:(b&&b.textContent)||'', meta:(m&&m.textContent)||'' };
      })
    `);
    const last = lines[lines.length - 1];
    if (last && last.who.includes('pet') && last.text && !last.who.includes('typing')) break;
  }
  lines.forEach((l) => console.log('  [' + (l.who.includes('me') ? '我' : '仓鼠') + '] ' + l.text + (l.meta ? '   《' + l.meta + '》' : '')));

  const ans = (lines.find((l) => l.who.includes('pet')) || {}).text || '';
  const nums = ans.match(/\d+/g) || [];
  console.log('兜底话术里的数字：' + (nums.length ? JSON.stringify(nums) + ' ✗ 不该有' : '无 ✓'));

  await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  console.log('未捕获异常：' + errs.length);
  ws.close(); process.exit(0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
