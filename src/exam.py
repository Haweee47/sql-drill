# -*- coding: utf-8 -*-
"""시험 모드 — 실제 환경 재현.

  · 6문항. 문항마다 제한 시간이 따로 있다. 기본 배분 합계 = 90분
  · 남는 30분은 연장 풀. 모자란 문항에 5분 단위로 꺼내 쓴다
    (90 + 30 = 최대 120분. 실제 시험과 같은 구조)
  · 타이머는 지금 열어 둔 문항만 돌아간다. 넘겼다 돌아올 수 있다
  · 시간이 다 된 문항은 잠긴다. 그때 저장돼 있던 답안으로 채점된다
  · 실행(Run)은 되지만 채점 결과는 시험이 끝나야 보인다
    → 맞았는지 모르는 채로 넘겨야 하므로 스스로 검산하게 된다
"""
import random

TARGET_MIN = 90        # 문항 제한시간 합계
RESERVE_MIN = 30       # 연장 풀 (90 + 30 = 120분)
STEP_MIN = 5           # 한 번에 꺼내 쓰는 단위
N_Q = 6


def pick_six(tasks, seed=None):
    """난이도를 섞어 6문항을 고른다. 실제 시험도 쉬운 것만 나오지 않는다."""
    rnd = random.Random(seed)
    by = {}
    for t in tasks:
        by.setdefault(t["level"], []).append(t["id"])
    for v in by.values():
        rnd.shuffle(v)
    out = by.get("쉬움", [])[:1] + by.get("보통", [])[:2] + by.get("어려움", [])[:3]
    rest = [t["id"] for t in tasks if t["id"] not in out]
    rnd.shuffle(rest)
    return sorted((out + rest)[:N_Q])


def budgets(tasks, ids, total=TARGET_MIN):
    """문항별 제한 시간(초). 문제의 난이도(minutes)에 비례해 total 분을 나눈다."""
    sel = [next(t for t in tasks if t["id"] == i) for i in ids]
    raw = [max(3, int(t.get("minutes") or 8)) for t in sel]
    s = float(sum(raw)) or 1.0
    mins = [max(3, int(round(r / s * total))) for r in raw]
    diff = total - sum(mins)
    i = 0
    while diff != 0 and i < 2000:            # 합계를 total 분에 정확히 맞춘다
        k = i % len(mins)
        step = 1 if diff > 0 else -1
        if mins[k] + step >= 3:
            mins[k] += step
            diff -= step
        i += 1
    return {ids[k]: mins[k] * 60 for k in range(len(ids))}


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SQL 시험</title>
<style>
:root{--bg:#F7F7F5;--panel:#fff;--fg:#1B1F23;--muted:#6B7280;--line:#E3E3DF;
      --accent:#1B64DA;--ok:#0F7B4F;--bad:#C0392B;--warn:#B5742E;--code:#F3F4F6}
@media(prefers-color-scheme:dark){:root{--bg:#15181B;--panel:#1C2024;--fg:#E8EAEC;
      --muted:#99A1A9;--line:#2C3237;--accent:#6AA3F5;--ok:#4CC38A;--bad:#E57373;
      --warn:#D9A062;--code:#23282D;color-scheme:dark}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);overflow:hidden;
     font:14px/1.6 "Malgun Gothic",system-ui,sans-serif;
     display:grid;grid-template-rows:auto 1fr}
@media(max-width:900px){body{overflow:auto;height:auto}}

#top{display:flex;align-items:center;gap:9px;padding:8px 14px;background:var(--panel);
     border-bottom:1px solid var(--line);flex-wrap:wrap}
#top .ttl{font-weight:700;font-size:14px;white-space:nowrap}
.tabs{display:flex;gap:4px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:none;color:var(--fg);border-radius:7px;
     padding:4px 9px;cursor:pointer;font:inherit;font-size:12.5px;line-height:1.4;
     display:flex;gap:5px;align-items:baseline}
.tab:hover{background:var(--code)}
.tab.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.tab .t{font-size:10.5px;opacity:.75;font-variant-numeric:tabular-nums}
.tab.dot::before{content:"\\25CF";color:var(--ok);font-size:8px;position:relative;top:-3px}
.tab.on.dot::before{color:#fff}
.tab.dead{opacity:.45;text-decoration:line-through}
#qclock{margin-left:auto;font-variant-numeric:tabular-nums;font-weight:700;font-size:19px;
        white-space:nowrap}
#qclock.warn{color:var(--warn)}#qclock.over{color:var(--bad)}
#gclock{font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums;
        white-space:nowrap;text-align:right;line-height:1.3}
#bext{border:1px solid var(--warn);background:none;color:var(--warn);border-radius:7px;
      padding:5px 9px;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
#bext[disabled]{opacity:.3;cursor:default}
#end{border:0;background:var(--bad);color:#fff;border-radius:8px;padding:6px 14px;
     font:inherit;font-weight:700;cursor:pointer}

#main{display:grid;grid-template-columns:400px 1fr;min-height:0}
@media(max-width:900px){#main{grid-template-columns:1fr}}
#prob{border-right:1px solid var(--line);overflow-y:auto;padding:14px 16px 40px;min-width:0}
#prob h2{font-size:16px;margin:0 0 4px}
.lvl{font-size:11.5px;color:var(--muted);margin:0 0 9px}
.prompt{background:var(--panel);border:1px solid var(--line);border-radius:9px;
        padding:11px 13px;white-space:pre-wrap;word-break:keep-all;font-size:13.2px}
.spec{font-size:12.3px;color:var(--muted);margin:8px 0 0;word-break:break-all}
.spec code{background:var(--code);padding:2px 5px;border-radius:4px;color:var(--fg)}
.sec{margin-top:16px}.sec h3{font-size:11.5px;margin:0 0 6px;color:var(--muted)}
.ltable{border-collapse:collapse;margin:0 0 9px;font-size:12px}
.ltable th,.ltable td{border:1px solid var(--line);padding:2px 8px;white-space:nowrap}
.ltable th{background:var(--code);font-size:11.5px}
.tname{font-family:Consolas,monospace;font-weight:700;font-size:12.5px;margin:8px 0 3px}
.tnote{font-size:11.5px;color:var(--muted)}.tnote ul{margin:3px 0 0;padding-left:15px}
.arrow{color:var(--muted);margin:2px 0 5px;font-size:12px}

#work{display:flex;flex-direction:column;padding:14px 16px;gap:9px;min-width:0;overflow:hidden}
@media(max-width:900px){#work{height:78vh}}
textarea{flex:1 1 58%;min-height:200px;resize:none;background:var(--panel);color:var(--fg);
         border:1px solid var(--line);border-radius:9px;padding:12px;
         font:13.5px/1.6 Consolas,"D2Coding",monospace;tab-size:2}
textarea:focus{outline:2px solid var(--accent);outline-offset:-1px}
textarea[readonly]{opacity:.55}
.bar{display:flex;gap:8px;align-items:center;flex:0 0 auto;flex-wrap:wrap}
button.go{border:0;border-radius:8px;padding:9px 17px;font:inherit;font-weight:700;cursor:pointer}
button.go[disabled]{opacity:.4;cursor:default}
.run{background:var(--code);color:var(--fg);border:1px solid var(--line)!important}
.save{background:var(--accent);color:#fff}
.next{background:none;color:var(--muted);border:1px solid var(--line)!important}
select{background:var(--panel);color:var(--fg);border:1px solid var(--line);
       border-radius:8px;padding:7px 9px;font:inherit;font-size:12.5px}
.hint{color:var(--muted);font-size:11.7px;margin-left:auto;text-align:right}
#out{flex:1 1 42%;min-height:170px;overflow:auto;background:var(--panel);
     border:1px solid var(--line);border-radius:9px;padding:12px;font-size:12.5px}
table{border-collapse:collapse;font-size:12.3px;font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--line);padding:3px 9px;white-space:nowrap}
th{background:var(--code);font-size:11.5px;color:var(--muted)}
.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}
.warnt{color:var(--warn);font-weight:700}
.msg{margin:3px 0}

#cover{position:fixed;inset:0;background:var(--bg);z-index:50;overflow:auto;
       display:flex;align-items:center;justify-content:center;padding:30px}
#cover .box{max-width:680px;width:100%}
#cover h1{font-size:23px;margin:0 0 10px}
#cover p{color:var(--muted);margin:0 0 8px}
#cover ul{color:var(--muted);font-size:13.5px;padding-left:19px;margin:0}
#cover li{margin-bottom:6px}
#cover a{color:var(--accent)}
.rtab{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.3px}
.rtab th,.rtab td{border:0;border-bottom:1px solid var(--line);padding:7px 9px;
                  text-align:left;white-space:normal}
.rtab th{color:var(--muted);font-size:12px}
.score{font-size:31px;font-weight:700;margin:4px 0 2px}
#start{border:0;background:var(--accent);color:#fff;border-radius:8px;padding:9px 22px;
       font:inherit;font-weight:700;cursor:pointer}
#toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:60;
       background:var(--fg);color:var(--bg);padding:9px 18px;border-radius:999px;
       font-size:13px;font-weight:700;opacity:0;transition:opacity .2s;pointer-events:none}
#toast.show{opacity:.94}
</style></head><body>

<div id="top">
  <span class="ttl">SQL 시험</span>
  <div class="tabs" id="tabs"></div>
  <button id="bext" title="이 문항에 연장 풀에서 시간을 추가합니다">+__STEP__분</button>
  <select id="eng"></select>
  <span id="qclock">--:--</span>
  <span id="gclock"></span>
  <button id="end">종료</button>
</div>

<div id="main">
  <section id="prob">
    <h2 id="title"></h2>
    <div class="lvl" id="lvl"></div>
    <div class="prompt" id="prompt"></div>
    <div class="spec" id="spec"></div>
    <div id="detail"></div>
  </section>
  <section id="work">
    <textarea id="sql" spellcheck="false" placeholder="쿼리를 쓰고 [답안 저장]"></textarea>
    <div class="bar">
      <button class="go run" id="brun">실행</button>
      <button class="go save" id="bsave">답안 저장</button>
      <button class="go next" id="bnext">다음 문항</button>
      <span class="hint">실행 결과만 볼 수 있습니다.<br>정답 여부는 시험이 끝나야 나옵니다.</span>
    </div>
    <div id="out">실행하면 결과가 여기 표시됩니다.</div>
  </section>
</div>

<div id="cover"><div class="box" id="coverbox"></div></div>
<div id="toast"></div>

<script>
const $=i=>document.getElementById(i);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const mmss=n=>String(Math.floor(Math.abs(n)/60)).padStart(2,'0')+':'
             +String(Math.abs(n)%60).padStart(2,'0');
const STEP=__STEP__*60, TARGET=__TARGET__, RESERVE=__RESERVE__;

let ALL=[],TABLES=[],EXAMPLES={},IDS=[],LIMIT={},
    ANS={},SPENT={},EXTRA={},DEAD={},
    reserve=RESERVE*60, cur=null, tick=null, ended=false, started=false;

function toast(m){const t=$('toast');t.textContent=m;t.className='show';
  clearTimeout(toast._t);toast._t=setTimeout(()=>{t.className='';},2300);}

function ltable(cols,rows){let h='<table class="ltable"><tr>';
  cols.forEach(c=>h+='<th>'+esc(c)+'</th>');h+='</tr>';
  rows.forEach(r=>{h+='<tr>';r.forEach(v=>h+='<td>'+esc(v)+'</td>');h+='</tr>';});
  return h+'</table>';}
function schemaBlock(use){
  const list=use&&use.length?TABLES.filter(t=>use.includes(t.name)):TABLES;
  let h='<div class="sec"><h3>테이블</h3>';
  list.forEach(t=>{h+='<div class="tname">'+esc(t.name)+'</div>'
    +ltable(['Column Name','Type'],t.cols.map(c=>[c[0],c[1]]))
    +'<div class="tnote"><ul>'+t.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ul></div>';});
  return h+'</div>';}
function exampleBlock(id){const e=EXAMPLES[String(id)];if(!e)return '';
  let h='<div class="sec"><h3>예시</h3>'
    +'<div style="color:var(--muted);font-size:12px">입력</div>';
  Object.keys(e.input).forEach(n=>{h+='<div class="tname">'+esc(n)+'</div>'
    +ltable(e.input[n].cols,e.input[n].rows);});
  return h+'<div class="arrow">\\u2193 출력</div>'
    +ltable(e.output.cols,e.output.rows)+'</div>';}

function left(id){return LIMIT[id]+(EXTRA[id]||0)-(SPENT[id]||0);}
function limOf(id){return LIMIT[id]+(EXTRA[id]||0);}

function drawTabs(){
  $('tabs').innerHTML='';
  IDS.forEach((id,i)=>{
    const b=document.createElement('button');
    let c='tab';
    if(cur&&cur.id===id)c+=' on';
    if((ANS[id]||'').trim())c+=' dot';
    if(DEAD[id])c+=' dead';
    b.className=c;
    b.innerHTML=(i+1)+' <span class="t">'+(DEAD[id]?'종료':mmss(Math.max(0,left(id))))+'</span>';
    b.title='Q'+id+' \\u00b7 제한 '+Math.round(limOf(id)/60)+'분';
    b.onclick=()=>go(id);
    $('tabs').appendChild(b);
  });
}

function lvlLine(id){
  const t=ALL.find(x=>x.id===id);
  return '난이도 '+t.level+' \\u00b7 제한 '+Math.round(LIMIT[id]/60)+'분'
    +((EXTRA[id]||0)?' (+'+Math.round(EXTRA[id]/60)+'분 연장)':'')
    +(DEAD[id]?' \\u00b7 시간 종료 \\u2014 잠김':'');}

function go(id){
  if(DEAD[id]&&cur){toast('Q'+id+' 은 시간이 끝나 잠겼습니다');return;}
  if(cur&&!DEAD[cur.id])ANS[cur.id]=$('sql').value;
  cur=ALL.find(t=>t.id===id);
  const dead=!!DEAD[id];
  $('title').textContent=(IDS.indexOf(id)+1)+'. '+cur.title;
  $('lvl').textContent=lvlLine(id);
  $('prompt').textContent=cur.prompt;
  $('spec').innerHTML='출력 컬럼 <code>'+esc(cur.columns)+'</code> \\u00b7 정렬 <code>'
    +esc(cur.order_note)+'</code>';
  $('detail').innerHTML=exampleBlock(cur.id)+schemaBlock(cur.tables);
  $('sql').value=ANS[id]||'';
  $('sql').readOnly=dead;
  $('brun').disabled=dead;$('bsave').disabled=dead;
  $('out').textContent=dead?'시간이 끝난 문항입니다. 저장된 답안으로 채점됩니다.'
                           :'실행하면 결과가 여기 표시됩니다.';
  clocks();drawTabs();
  if(!dead)$('sql').focus();
}

function nextAlive(from){
  const i=IDS.indexOf(from);
  for(let k=1;k<=IDS.length;k++){const id=IDS[(i+k)%IDS.length];if(!DEAD[id])return id;}
  return null;}

function clocks(){
  if(!cur)return;
  const l=left(cur.id);
  $('qclock').textContent=DEAD[cur.id]?'종료':('문항 '+mmss(Math.max(0,l)));
  $('qclock').className=DEAD[cur.id]?'over':(l<=60?'over':(l<=180?'warn':''));
  const spent=IDS.reduce((a,id)=>a+(SPENT[id]||0),0);
  $('gclock').innerHTML='전체 '+mmss(spent)+' 경과<br>연장 풀 '+mmss(reserve);
  $('bext').disabled=!!DEAD[cur.id]||reserve<STEP;}

function expire(id){
  if(cur&&cur.id===id)ANS[id]=$('sql').value;
  DEAD[id]=true;
  const nx=nextAlive(id);
  drawTabs();
  if(nx===null){toast('모든 문항의 시간이 끝났습니다');finish(true);return;}
  toast('Q'+id+' 시간 종료 \\u2014 다음 문항으로 넘어갑니다');
  cur=null;go(nx);}

function second(){
  if(!cur||ended||DEAD[cur.id])return;
  SPENT[cur.id]=(SPENT[cur.id]||0)+1;
  const l=left(cur.id);
  if(l===300||l===60)toast('Q'+cur.id+' 남은 시간 '+(l/60)+'분');
  if(l<=0){expire(cur.id);return;}
  clocks();drawTabs();}

$('bext').onclick=()=>{
  if(!cur||DEAD[cur.id])return;
  if(reserve<STEP){toast('연장 풀이 비었습니다');return;}
  reserve-=STEP;EXTRA[cur.id]=(EXTRA[cur.id]||0)+STEP;
  toast('Q'+cur.id+' 에 '+(STEP/60)+'분 추가 \\u2014 연장 풀 '+mmss(reserve)+' 남음');
  $('lvl').textContent=lvlLine(cur.id);clocks();drawTabs();};

async function post(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});return r.json();}

$('brun').onclick=async()=>{
  if(!cur||DEAD[cur.id])return;
  ANS[cur.id]=$('sql').value;drawTabs();
  $('out').textContent='실행 중...';
  const d=await post('/run',{id:cur.id,sql:$('sql').value,engine:$('eng').value});
  if(d.error){$('out').innerHTML='<div class="bad">쿼리 오류</div>'
    +'<pre style="white-space:pre-wrap;margin:6px 0 0">'+esc(d.error)+'</pre>';return;}
  let h='<div style="color:var(--muted);margin-bottom:6px">내 결과 \\u2014 '
    +d.rows.length+'행</div><table><tr>';
  d.cols.forEach(c=>h+='<th>'+esc(c)+'</th>');h+='</tr>';
  d.rows.slice(0,40).forEach(r=>{h+='<tr>';
    r.forEach(v=>h+='<td>'+esc(v===null?'\\u2205':v)+'</td>');h+='</tr>';});
  h+='</table>';
  if(d.rows.length>40)h+='<div style="color:var(--muted);margin-top:5px">... '
    +(d.rows.length-40)+'행 더</div>';
  if(d.colwarn)h='<div class="bad msg">컬럼 이름/개수가 요구사항과 다릅니다 \\u2014 요구: '
    +esc(cur.columns)+'</div>'+h;
  if(d.lint)h='<div class="warnt msg">'+esc(d.lint)+'</div>'+h;
  $('out').innerHTML=h;};

$('bsave').onclick=()=>{
  if(!cur||DEAD[cur.id])return;
  ANS[cur.id]=$('sql').value;drawTabs();
  $('out').innerHTML='<div class="ok">답안 저장됨</div>'
    +'<div class="msg" style="color:var(--muted)">정답 여부는 시험이 끝나야 나옵니다. '
    +'넘어가기 전에 한 번만 더 보세요 \\u2014 컬럼 이름/순서, 정렬 기준, 반올림 자리, '
    +'0으로 나누기, NULL, 빈 그룹.</div>';};

$('bnext').onclick=()=>{if(!cur)return;const nx=nextAlive(cur.id);
  if(nx===null||nx===cur.id){toast('넘어갈 문항이 없습니다');return;}go(nx);};

$('end').onclick=()=>{
  const blank=IDS.filter(id=>!(ANS[id]||'').trim()).length;
  if(confirm('시험을 끝내고 채점할까요? 되돌릴 수 없습니다.'
    +(blank?'\\n\\n답안이 비어 있는 문항이 '+blank+'개 있습니다.':'')))finish(false);};

document.addEventListener('keydown',e=>{
  if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();$('brun').click();}
  if(e.ctrlKey&&(e.key==='s'||e.key==='S')){e.preventDefault();$('bsave').click();}});

async function finish(auto){
  if(ended)return;ended=true;clearInterval(tick);
  if(cur&&!DEAD[cur.id])ANS[cur.id]=$('sql').value;
  const total=IDS.reduce((a,id)=>a+(SPENT[id]||0),0);
  $('coverbox').innerHTML='<h1>채점 중...</h1>'
    +'<p>여러 데이터셋으로 돌립니다. 잠깐 걸립니다.</p>';
  $('cover').style.display='flex';
  const rows=[];let pass=0;
  for(const id of IDS){
    const t=ALL.find(x=>x.id===id),sql=(ANS[id]||'').trim();
    if(!sql){rows.push([id,t,'미작성',false]);continue;}
    const d=await post('/submit',{id:id,sql:sql,engine:$('eng').value});
    let why;
    if(d.error)why='오류 \\u2014 '+d.error.split('\\n')[0].slice(0,80);
    else if(d.passed)why='통과';
    else why=((d.messages&&d.messages.join(' / '))||'결과 불일치').slice(0,110);
    if(d.passed)pass++;
    rows.push([id,t,why,!!d.passed]);
  }
  const f=n=>Math.floor(n/60)+'분 '+String(n%60).padStart(2,'0')+'초';
  let h='<h1>시험 종료</h1><div class="score">'+pass+' / '+IDS.length+'</div>';
  h+='<p>소요 '+f(total)+(auto?' \\u00b7 시간 종료로 자동 제출':'')
    +' \\u00b7 연장 '+f(RESERVE*60-reserve)+' 사용</p>';
  h+='<table class="rtab"><tr><th>#</th><th>문항</th><th>시간</th><th>결과</th></tr>';
  rows.forEach((r,i)=>{
    const sp=SPENT[r[0]]||0,lim=limOf(r[0]);
    h+='<tr><td>'+(i+1)+'</td>'
      +'<td>Q'+r[0]+'. '+esc(r[1].title)
      +'<br><span style="color:var(--muted);font-size:11.5px">'+esc(r[1].level)+'</span></td>'
      +'<td style="font-variant-numeric:tabular-nums;color:'
      +(sp>=lim?'var(--bad)':'var(--muted)')+'">'+mmss(sp)
      +'<br><span style="font-size:11px">/'+mmss(lim)+'</span></td>'
      +'<td class="'+(r[3]?'ok':'bad')+'">'+(r[3]?'\\u2713 ':'\\u2717 ')+esc(r[2])+'</td></tr>';});
  h+='</table>';
  const fails=rows.filter(r=>!r[3]);
  if(fails.length)h+='<p style="font-size:13px">틀린 문항 해설: '
    +fails.map(r=>'<a href="/guide#q'+r[0]+'" target="_blank">Q'+r[0]+'</a>').join(' \\u00b7 ')
    +'</p>';
  h+='<p style="font-size:13px;margin-top:12px"><a href="/exam">새 시험</a> \\u00b7 '
    +'<a href="/">연습 모드</a> \\u00b7 <a href="/guide" target="_blank">전체 해설</a></p>';
  $('coverbox').innerHTML=h;}

fetch('/tasks').then(r=>r.json()).then(d=>{
  ALL=d.tasks;TABLES=d.tables;EXAMPLES=d.examples||{};
  const sel=$('eng'),saved=localStorage.getItem('engine')||'mysql';
  (d.engines||[]).forEach(e=>{const o=document.createElement('option');
    o.value=e.key;o.textContent=e.name;if(e.key===saved)o.selected=true;sel.appendChild(o);});
  sel.onchange=()=>localStorage.setItem('engine',sel.value);
  return fetch('/exam/new').then(r=>r.json());
}).then(d=>{
  IDS=d.ids;LIMIT=d.limits;
  const plan=IDS.map((id,i)=>{const t=ALL.find(x=>x.id===id);
    return (i+1)+'번 '+t.level+' '+Math.round(LIMIT[id]/60)+'분';}).join(' \\u00b7 ');
  $('coverbox').innerHTML='<h1>SQL 시험</h1>'
    +'<p>테스트돔과 같은 조건으로 맞췄습니다.</p><ul>'
    +'<li><b>'+IDS.length+'문항 \\u00b7 문항마다 제한 시간이 따로 있습니다</b><br>'
    +'<span style="font-size:12.5px">'+esc(plan)+' \\u2014 합계 '+TARGET+'분</span></li>'
    +'<li><b>연장 풀 '+RESERVE+'분</b>이 따로 있습니다. 모자란 문항에서 [+'+(STEP/60)
    +'분] 을 눌러 꺼내 쓰세요 (최대 '+(TARGET+RESERVE)+'분)</li>'
    +'<li>타이머는 <b>지금 열려 있는 문항만</b> 돌아갑니다. 막히면 일단 넘기고 돌아오세요</li>'
    +'<li><b>시간이 끝난 문항은 잠깁니다.</b> 그때 저장돼 있던 답안으로 채점됩니다</li>'
    +'<li><b>실행은 되지만 정답 여부는 끝나야 나옵니다</b> \\u2014 스스로 검산하세요</li>'
    +'<li>컬럼 이름\\u00b7순서\\u00b7정렬\\u00b7반올림 자리까지 정확히 맞아야 합니다</li>'
    +'<li>여러 데이터셋으로 채점됩니다. 논리에 빈틈이 있으면 떨어집니다</li>'
    +'<li style="color:var(--fg)">Ctrl+Enter 실행 \\u00b7 Ctrl+S 저장</li>'
    +'</ul><p style="margin-top:16px"><button id="start">시작</button></p>';
  $('start').onclick=()=>{
    $('cover').style.display='none';started=true;
    IDS.forEach(id=>{SPENT[id]=0;EXTRA[id]=0;});
    tick=setInterval(second,1000);go(IDS[0]);};
});
addEventListener('beforeunload',e=>{if(started&&!ended){e.preventDefault();e.returnValue='';}});
</script></body></html>"""


def page():
    return (PAGE.replace("__TARGET__", str(TARGET_MIN))
                .replace("__RESERVE__", str(RESERVE_MIN))
                .replace("__STEP__", str(STEP_MIN)))
