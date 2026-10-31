/* 传图 → 它真的看一眼：真实鼠标 + 真实文件选择，不是 curl 模拟。

   验的是这次被当面戳穿的那件事：
   「连我上传的图片做了什么都不知道」——现在它得说得出图上的科目/题量/对错/时长，
   而且屏幕上的那一句必须带来源标签（看图 · 模型名）。

   流程：长按唤起面板 → 点「传今天的截图」→ 给 #realFile 塞真图 →
        等确认卡 → 点确认 → 入库 → 看它有没有说出图里的东西。 */
const CDP_PORT = 9333;
const IMAGE = process.argv[2] || 'C:/Users/11619/WorkBuddy/2026-10-31-18-29-38/repo/C-module-recognition/test/test12_粉笔_1031_判断推理.jpg';

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

async function longPressPet(send) {
  const pos = await ev(send, `(function(){
    var el=document.querySelector('#homePet'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2) };
  })()`);
  if (!pos) return false;
  await send('Input.dispatchMouseEvent', { type:'mousePressed', x:pos.x, y:pos.y, button:'left', clickCount:1 });
  await sleep(900);
  await send('Input.dispatchMouseEvent', { type:'mouseReleased', x:pos.x, y:pos.y, button:'left', clickCount:1 });
  return true;
}

async function click(send, sel) {
  const pos = await ev(send, `(function(){
    var el=document.querySelector(${JSON.stringify(sel)});
    if(!el) return null;
    var r=el.getBoundingClientRect();
    if(!r.width) return { hidden:true };
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2) };
  })()`);
  if (!pos || pos.hidden) return false;
  const hit = await ev(send, `(function(){
    var el=document.querySelector(${JSON.stringify(sel)});
    var r=el.getBoundingClientRect();
    var h=document.elementFromPoint(Math.round(r.left+r.width/2), Math.round(r.top+r.height/2));
    return h ? (h.id || h.className || h.tagName) : null;
  })()`);
  if (!hit || !String(hit).includes(sel.replace('#', ''))) {
    console.log('  ⚠ 落点被挡住：' + sel + ' ← ' + hit);
    return false;
  }
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: pos.x, y: pos.y, button: 'left', clickCount: 1 });
  await sleep(60);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: pos.x, y: pos.y, button: 'left', clickCount: 1 });
  return true;
}

(async () => {
  const ws = new WebSocket(await pickPage());
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const { send, events } = rpc(ws);
  await send('Runtime.enable'); await send('Page.enable'); await send('DOM.enable');
  await send('Page.reload', { ignoreCache: true });
  await sleep(4500);

  console.log('新代码在位：petLookAtImage=' + (await ev(send, `typeof petLookAtImage`)) +
              '  compressImage=' + (await ev(send, `typeof compressImage`)));

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
  console.log('面板开=' + (await ev(send, `(function(){var p=document.querySelector('.pchat');return !!(p&&p.classList.contains('on'));})()`)));

  /* 面板是 fixed 覆盖层，会压住上传 sheet 的确认按钮。
     实测：面板开着点确认，鼠标事件落在 .pchat-mask 上，POST /api/records 根本没发出去。
     所以先收起面板，等它看完图，再开面板读对话。 */
  await click(send, '#petChatClose');
  await sleep(700);
  console.log('面板已收起=' + (await ev(send, `(function(){var p=document.querySelector('.pchat');return !p||!p.classList.contains('on');})()`)));

  // 上传入口
  const opened = await click(send, '#btnUpload');
  if (!opened) console.log('（没找到「传今天的截图」按钮，可能当前是疲惫态）');
  await sleep(800);

  // 给隐藏的 file input 塞真图
  const doc = await send('DOM.getDocument', { depth: -1 });
  const node = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: '#realFile' });
  if (!node.result?.nodeId) throw new Error('找不到 #realFile');
  await send('DOM.setFileInputFiles', { nodeId: node.result.nodeId, files: [IMAGE] });
  console.log('已选图：' + IMAGE);

  // 等确认卡出现（识别要几秒到二十几秒）
  let confirmed = false;
  for (let i = 0; i < 90; i++) {
    await sleep(500);
    const step = await ev(send, `(function(){
      var s=document.querySelector('#sheet');
      var b=document.querySelector('#btnConfirm');
      var r=b?b.getBoundingClientRect():null;
      return { up:!!(s&&s.classList.contains('up')), confirm:!!(r&&r.width),
               txt:(document.querySelector('#scanTxt')||{}).textContent };
    })()`);
    if (step && step.confirm) { confirmed = true; break; }
    if (i % 10 === 9) console.log('  等识别… ' + JSON.stringify(step));
  }
  console.log('识别完成、确认卡可见=' + confirmed);
  if (!confirmed) throw new Error('没有等到确认卡，识别可能失败');

  const probe = await ev(send, `(function(){
    var b=document.querySelector('#btnConfirm');
    if(!b) return null;
    b.scrollIntoView({block:'center'});
    var r=b.getBoundingClientRect();
    var hit=document.elementFromPoint(Math.round(r.left+r.width/2), Math.round(r.top+r.height/2));
    return { rect:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],
             vw:innerWidth, vh:innerHeight,
             hit: hit ? (hit.id||hit.className||hit.tagName) : null };
  })()`);
  console.log('确认按钮：' + JSON.stringify(probe));
  const before = (await ev(send, LINES)).length;
  await click(send, '#btnConfirm');
  console.log('已点确认，等它看完图说话…');

  /* 看图要等视觉模型（实测 7-13 秒）。确认完立刻把面板重新打开，
     它的那句话是边等边长的，盯着 meta 出现「看图」就算成。 */
  await sleep(600);
  await click(send, '#homePet');
  await sleep(1500);
  let lines = [];
  let seenOk = false;
  for (let i = 0; i < 70; i++) {
    await sleep(600);
    lines = await ev(send, LINES);
    if (!Array.isArray(lines)) continue;
    if (lines.some((l) => /看图|没看清|刚看过/.test(l.meta || ''))) { seenOk = true; break; }
  }
  console.log('（等到了"看图"那句=' + seenOk + '）');

  console.log('\n面板里的对话：');
  (lines || []).forEach((l) => console.log('  [' + (l.who.includes('me') ? '我' : '团团') + '] ' + l.text + (l.meta ? '   《' + l.meta + '》' : '')));

  const seen = (lines || []).filter((l) => /看图|没看清|刚看过/.test(l.meta || '')).pop() || {};
  console.log('\n看图那句话：' + (seen.text || '(没有)'));
  console.log('来源标签：' + (seen.meta || '(无)'));

  // 记录是否入库、有没有把同一张图记两遍
  const health = await ev(send, `fetch('http://127.0.0.1:8000/api/health').then(r=>r.json())`);
  console.log('库内记录数：' + (health && health.records));

  /* ---- 接着追问「你怎么知道」，这是这次翻车的原话 ---- */
  async function panelOpen() {
    return await ev(send, `(function(){var p=document.querySelector('.pchat');return !!(p&&p.classList.contains('on'));})()`);
  }
  if (!(await panelOpen())) { await longPressPet(send); await sleep(1800); }
  if (!(await panelOpen())) { await longPressPet(send); await sleep(1800); }
  console.log('\n追问前面板开=' + (await panelOpen()));

  const inp2 = await ev(send, `(function(){
    var el=document.getElementById('petChatIn'); if(!el) return null;
    var r=el.getBoundingClientRect();
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), w:Math.round(r.width) };
  })()`);
  await send('Input.dispatchMouseEvent', { type:'mousePressed', x:inp2.x, y:inp2.y, button:'left', clickCount:1 });
  await send('Input.dispatchMouseEvent', { type:'mouseReleased', x:inp2.x, y:inp2.y, button:'left', clickCount:1 });
  await sleep(200);
  const q = process.argv[3] || '你怎么知道我做了这么长时间';
  await send('Input.insertText', { text: q });
  await sleep(200);
  const beforeQ = (await ev(send, LINES)).length;
  await send('Input.dispatchKeyEvent', { type:'keyDown', key:'Enter', code:'Enter', windowsVirtualKeyCode:13, nativeVirtualKeyCode:13 });
  await send('Input.dispatchKeyEvent', { type:'keyUp', key:'Enter', code:'Enter', windowsVirtualKeyCode:13, nativeVirtualKeyCode:13 });

  let linesQ = [];
  for (let i = 0; i < 60; i++) {
    await sleep(500);
    linesQ = await ev(send, LINES);
    if (!Array.isArray(linesQ)) continue;
    const last = linesQ[linesQ.length - 1];
    if (linesQ.length > beforeQ + 1 && last && last.meta) break;
  }
  console.log('\n追问「' + q + '」之后的完整对话：');
  (linesQ || []).forEach((l) => console.log('  [' + (l.who.includes('me') ? '我' : '团团') + '] ' + l.text + (l.meta ? '   《' + l.meta + '》' : '')));

  const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown');
  const warns = events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type !== 'log');
  console.log('\n未捕获异常：' + errs.length + ' 条；warn/error 日志：' + warns.length + ' 条');
  warns.slice(0, 5).forEach((w) => console.log('  ' + (w.params.args || []).map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 140)));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  if (shot.result?.data) {
    const fs = await import('node:fs');
    fs.writeFileSync('C:/Users/11619/WorkBuddy/2026-10-31-18-29-38/repo/tools/e2e/shot_see_image.png', Buffer.from(shot.result.data, 'base64'));
    console.log('截图：tools/e2e/shot_see_image.png');
  }
  ws.close(); process.exit(0);
})().catch((e) => { console.error('失败：' + e.message); process.exit(1); });
