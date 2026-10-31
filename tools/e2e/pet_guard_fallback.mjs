/* 故障注入：/api/pet/verify 一律返回 ok=false，验证前端是否回退模板嘴。 */
const CDP_PORT=9333;
const list=await fetch(`http://127.0.0.1:${CDP_PORT}/json`).then(r=>r.json());
const page=list.find(t=>t.type==='page'&&t.url.includes('8899'));
const ws=new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r,j)=>{ws.addEventListener('open',r);ws.addEventListener('error',j);});
let id=0;const pend=new Map();const logs=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);
  if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);return;}
  if(m.method==='Runtime.consoleAPICalled'){const t=(m.params.args||[]).map(a=>a.value??a.description??'').join(' ');if(t)logs.push(m.params.type+': '+t);}
});
const send=(method,params)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method,params:params||{}}));});
const ev=async (snd,x)=>{const r=await snd('Runtime.evaluate',{expression:x,awaitPromise:true,returnByValue:true});
  if(r.error){ console.log('  [CDP错误] '+JSON.stringify(r.error)); return {__cdp:r.error.message}; }
  if(r.result?.exceptionDetails) return {__err:r.result.exceptionDetails.exception?.description};
  return r.result?.result?.value;};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await send('Runtime.enable'); await send('Page.enable');

// 必须重载：上一次注入若没恢复，window.fetch 会自引用成环，页面直接卡死
await send('Page.reload', { ignoreCache: true });
await sleep(3500);
console.log('页面已重载：' + JSON.stringify(await ev(send, 'typeof openChat')));

await ev(send, `openChat(); 'ok'`);
await sleep(300);

const injected = await ev(send, `
(function(){
  window.__origFetch = window.fetch.bind(window);
  window.fetch = function(u, o){
    if(String(u).indexOf('/api/pet/verify') >= 0){
      return Promise.resolve(new Response(JSON.stringify({ok:false, reason:'注入故障：模拟模型说错话'}),
        {status:200, headers:{'Content-Type':'application/json'}}));
    }
    return window.__origFetch.call(window, u, o);
  };
  return 'injected';
})()
`);
console.log('注入结果：' + JSON.stringify(injected));

const started = await ev(send, `petAsk('promise','那个承诺'); 'started'`);
console.log('发起提问：' + JSON.stringify(started));

let lines=[];
for(let i=0;i<40;i++){
  await sleep(300);
  const got=await ev(send, `Array.from(document.querySelectorAll('.pchat-log .pchat-line')).map(function(l){var b=l.querySelector('.pchat-bub'),m=l.querySelector('.pchat-meta');return {who:l.className,text:(b&&b.textContent)||'',meta:(m&&m.textContent)||''};})`);
  if(got && got.__err){ console.log('eval错误 '+got.__err.slice(0,100)); break; }
  if(Array.isArray(got)) lines=got;
  const last=lines[lines.length-1];
  if(last && last.meta) break;
}
lines.forEach(l=>console.log('  ['+(l.who.includes('me')?'我':'仓鼠')+'] '+l.text+(l.meta?'   《'+l.meta+'》':'')));
const last=lines[lines.length-1]||{};
console.log('\n是否回退模板：'+((last.meta||'').includes('SQLite')?'✓ 回退成功（模型回答被丢弃）':'✗ 需要复查'));
console.log('日志：');
logs.filter(l=>l.indexOf('pet')>=0).forEach(l=>console.log('  '+l.slice(0,150)));
await ev(send, `window.fetch = window.__origFetch; 'restored'`);
ws.close();process.exit(0);
