/* 用户截图里那一幕：连点「今天怎么样」，回回都是同一句「数量关系那道题你算对了」；
   再问「我哪里最毛」，回的还是一模一样的一句。看着像卡带，其实是三件事叠在一起：

   1) 历史里喂了它自己上一句 → qwen-flash 整句照抄；
   2) 抄出来的那句又落库、又进下一轮历史 → 从第二轮起就是自己抄自己；
   3) 「今天怎么样」落在 normal 模式，事实包里没有主次，它就去念图里那道题。

   这个脚本只验一件事：**问不同的问题，必须回不同的话，而且答的是他问的那件事。 */
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

/* 点话题按钮 = 他点着说那句话，跟手打走同一条嘴 */
async function topic(send, intent) {
  const before = (await ev(send, LINES)).length;
  const hit = await ev(send, `(function(){
    var el=document.querySelector('.pchat-topic[data-intent="${intent}"]'); if(!el) return null;
    var r=el.getBoundingClientRect();
    var h=document.elementFromPoint(Math.round(r.left+r.width/2), Math.round(r.top+r.height/2));
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2),
             ok: !!(h && (el===h || el.contains(h))), hit: h ? String(h.className||h.tagName) : null };
  })()`);
  if (!hit || !hit.ok) throw new Error(`话题按钮 ${intent} 点不到：` + (hit && hit.hit));
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: hit.x, y: hit.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: hit.x, y: hit.y, button: 'left', clickCount: 1 });
  const lines = await waitForReply(send, before);
  const pet = lines.filter((l) => l.who.includes('pet') && l.meta).pop() || {};
  const me = lines.filter((l) => l.who.includes('me')).pop() || {};
  return { me: me.text, pet: pet.text, meta: pet.meta };
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

  const ctx = await ev(send, `(function(){var e=document.getElementById('petCtx');return e?e.textContent:'';})()`);
  console.log('面板上的账：' + (ctx || '（空）'));

  const rounds = [];
  rounds.push({ q: '今天怎么样', ...(await topic(send, 'today')) });
  rounds.push({ q: '今天怎么样（再点一次）', ...(await topic(send, 'today')) });
  rounds.push({ q: '我哪里最毛', ...(await topic(send, 'weak')) });
  rounds.push({ q: '我哪里最毛（再点一次）', ...(await topic(send, 'weak')) });

  console.log('');
  rounds.forEach((r) => {
    console.log('我　：' + r.q);
    console.log('团团：' + r.pet + '   《' + (r.meta || '') + '》\n');
  });

  /* 判定的口径：问的是两件不同的事，就该得到两句不同的话。
     同一件事问两遍，答得一样是正常的（事实就那些），不判。 */
  const today = rounds[0].pet || '';
  const weak = rounds[2].pet || '';
  const checks = {
    '问今天，答的是今天的分钟数': /\d+\s*分钟/.test(today),
    '问哪块最毛，答的是模块+正确率': /数量关系|资料分析|判断推理|常识判断|言语理解/.test(weak) && /\d+%?/.test(weak),
    '问不同的两件事，回的不是同一句': bare(today) !== bare(weak),
    '没有出现图里的那道题当答案': !/那道题你算对/.test(today + weak),
    '来源都标了模型': rounds.every((r) => /qwen/.test(r.meta || '')),
  };
  console.log('—— 判定 ——');
  Object.entries(checks).forEach(([k, v]) => console.log(k.padEnd(18, ' ') + ' : ' + (v ? '✓' : '✗')));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  if (shot.result?.data) {
    writeFileSync('shot_repeat.png', Buffer.from(shot.result.data, 'base64'));
    console.log('\n截图：tools/e2e/shot_repeat.png');
  }
  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  console.log('未捕获异常：' + errs.length + ' 条');
  const bad = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
  ws.close();
  process.exit(bad.length || errs.length ? 1 : 0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
