# -*- coding: utf-8 -*-
"""테스트돔 형식 SQL 연습 프로그램.

    python app.py

브라우저가 열린다. 왼쪽에 문제, 오른쪽에 에디터.
Run은 내 쿼리 결과만 보여주고, Submit을 눌러야 정답과 대조한다.
"""
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import re

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "practice.duckdb")
PORT = 8777

sys.path.insert(0, HERE)
from datasets import DATASETS  # noqa: E402
from funcs_data import FUNCS  # noqa: E402
from guide_data import CHECKS, GUIDE, PATTERNS
from guide_easy import EASY_BY_ID  # noqa: E402
import dialects as DIA  # noqa: E402
import engines as ENG  # noqa: E402
import exam as EXAM  # noqa: E402

FUNC_EX = {}
_fx = os.path.join(HERE, "funcs_examples.json")
if os.path.exists(_fx):
    FUNC_EX = json.load(open(_fx, encoding="utf-8"))
from schema import SCHEMA as TABLES  # noqa: E402
from tasks import TASKS  # noqa: E402

EXAMPLES = {}
_ex = os.path.join(HERE, "examples.json")
if os.path.exists(_ex):
    EXAMPLES = json.load(open(_ex, encoding="utf-8"))

def used_tables(task):
    """참조 정답에서 실제로 쓰는 테이블만 고른다.

    문항마다 안 쓰는 테이블까지 보여주면 실전과 다르다.
    테스트돔은 그 문제에 필요한 테이블만 제시한다.
    """
    names = [t["name"] for t in TABLES]
    return [n for n in names
            if re.search(r"\b" + n + r"\b", task["ref"], re.I)]


SCHEMA = [
    ("users", "user_id, signup_date, channel, age, gender", "3,000"),
    ("events", "user_id, event_name, event_date, channel", "20,815"),
    ("payments", "user_id, paid_date, plan, amount", "4,562"),
]
NOTES = [
    "퍼널 순서 : view_landing › signup_start › signup_done › kyc_done › first_payment",
    "app_open  : 접속 로그 (리텐션 계산용)",
    "plan      : basic 9,900원 / pro 29,900원",
    "channel   : organic / paid_search / sns / referral",
    "기간      : 2026-01-01 ~ 2026-09-30",
]


def run_sql(sql):
    """기대값 계산용. 참조 정답은 항상 DuckDB 로 돌린다."""
    return ENG.run(sql, "duckdb")


def lint_intdiv(sql):
    """정수 나눗셈 경고.

    연습 엔진(DuckDB)은 / 가 실수 나눗셈이라 *1.0 없이도 통과한다.
    그런데 테스트돔은 SQLite·MS SQL 에서도 돌아가야 하는 문제를 내므로
    정수끼리 나누면 0 이 된다. 연습이 시험보다 느슨하면 안 되니 여기서 잡는다.
    """
    import re as _re
    body = _re.sub(r"'[^']*'", "''", sql)          # 문자열 리터럴 제거
    if "/" not in body:
        return None
    safe = _re.search(r"\d+\.\d|CAST\s*\(|CONVERT\s*\(|DECIMAL|AVG\s*\(", body, _re.I)
    if safe:
        return None
    return ("나눗셈에 소수가 없습니다. 지금 엔진은 통과하지만 "
            "시험 환경에서는 정수 나눗셈이 되어 0 이 나올 수 있습니다. "
            "100.0 * A / B 처럼 소수를 섞으세요.")


def norm(v):
    """채점용 정규화.

    예전에는 숫자를 2자리로 반올림해 비교했는데, 그러면 ROUND 를 빼먹은 답도
    통과해 버렸다. 실제 시험은 값을 그대로 보므로 여기서도 그대로 본다.
    부동소수 미세 오차만 흡수한다.
    """
    if v is None or v == "" or v == "None":
        return "∅"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v).strip()
    # 1e-9 상대오차 안에서만 같은 값으로 본다 (엔진 간 부동소수 차이 흡수)
    return "%.9g" % f


_TYPES = {t["name"]: dict(t["cols"]) for t in TABLES}


def build_mem(spec):
    """데이터셋 명세로 메모리 DB를 만든다. 실제와 같은 컬럼 타입을 쓴다."""
    con = duckdb.connect(":memory:")
    for t in TABLES:
        name = t["name"]
        decl = ", ".join("%s %s" % (c, ty.replace("char(1)", "VARCHAR"))
                         for c, ty in t["cols"])
        con.execute("CREATE TABLE %s (%s)" % (name, decl))
        if name in spec:
            cols, rows = spec[name]
            if rows:
                con.executemany("INSERT INTO %s (%s) VALUES (%s)"
                                % (name, ", ".join(cols), ",".join(["?"] * len(cols))), rows)
    for m in ENG._MACROS:
        try:
            con.execute(m.replace("memory.", ""))
        except Exception:
            pass
    return con


def run_on(con, sql):
    cur = con.execute(ENG._duck_tr(sql))
    return ([d[0] for d in cur.description],
            [[None if v is None else str(v) for v in r] for r in cur.fetchall()])


def check_datasets(task, user_sql, dialect="mysql"):
    """추가 데이터셋에서도 정답과 일치하는지 본다.

    기대값은 DuckDB 참조 정답으로 만들고, 사용자 쿼리는 고른 문법으로
    SQLite 에서 돌린다. 엔진이 달라도 '논리가 맞는가'는 똑같이 물을 수 있다.
    """
    import sqlite3
    out = []
    # DDL 은 engines 쪽 한 군데서만 관리한다. 여기 따로 적어 두면 테이블을
    # 추가할 때 한쪽만 고치고 끝나서 '그런 테이블 없다' 오류가 난다.
    ddl = ENG._SQLITE_DDL
    for name, spec in DATASETS:
        ref_run, ref_close = ENG.dataset_runner(spec, "duckdb")
        try:
            ecols, erows = ref_run(task["ref"])
        except Exception:
            ref_close(); continue
        ref_close()

        con = DIA.connect(":memory:")
        for t, cols_ddl in ddl.items():
            con.execute("CREATE TABLE %s (%s)" % (t, cols_ddl))
            if t in spec and spec[t][1]:
                cs, rs = spec[t]
                con.executemany("INSERT INTO %s (%s) VALUES (%s)"
                                % (t, ",".join(cs), ",".join(["?"] * len(cs))),
                                [tuple(str(v) if hasattr(v, "isoformat") else v for v in r)
                                 for r in rs])
        try:
            q = DIA.mysql_to_sqlite(user_sql) if dialect == "mysql" else user_sql
            cur = con.execute(q)
            gcols = [d[0] for d in cur.description]
            grows = [[None if v is None else str(v) for v in r] for r in cur.fetchall()]
        except Exception as e:
            out.append({"name": name, "ok": False,
                        "why": "쿼리 오류: " + str(e).splitlines()[0][:90]})
            con.close(); continue
        con.close()

        if len(gcols) != len(ecols):
            out.append({"name": name, "ok": False,
                        "why": "컬럼 개수가 다릅니다 — 정답 %d개 / 제출 %d개"
                               % (len(ecols), len(gcols))})
            continue
        if len(grows) != len(erows):
            out.append({"name": name, "ok": False,
                        "why": "행 수가 다릅니다 — 정답 %d행 / 제출 %d행"
                               % (len(erows), len(grows))})
            continue
        eset = sorted([norm(x) for x in r] for r in erows)
        gset = sorted([norm(x) for x in r] for r in grows)
        if eset != gset:
            miss = [r for r in eset if r not in gset][:1]
            extra = [r for r in gset if r not in eset][:1]
            why = "결과 집합이 다릅니다"
            if miss:
                why += " — 빠진 행 [%s]" % " | ".join(miss[0])
            if extra:
                why += " / 없어야 할 행 [%s]" % " | ".join(extra[0])
            out.append({"name": name, "ok": False, "why": why})
            continue
        out.append({"name": name, "ok": True})
    return out


def grade(task, cols, rows):
    want = [c.strip() for c in task["columns"].split(",")]
    exp_cols, exp_rows = run_sql(task["ref"])
    msgs = []
    if [c.lower() for c in cols] != [c.lower() for c in want]:
        msgs.append("컬럼 이름 또는 순서가 다릅니다 — 요구: %s / 제출: %s"
                    % (", ".join(want), ", ".join(cols) or "(없음)"))
    if len(rows) != len(exp_rows):
        msgs.append("행 수가 다릅니다 — 정답 %d행 / 제출 %d행" % (len(exp_rows), len(rows)))
    diffs = []
    for i in range(min(len(rows), len(exp_rows))):
        g = [norm(x) for x in rows[i]]
        e = [norm(x) for x in exp_rows[i]]
        if g != e:
            diffs.append({"row": i + 1, "expected": e, "got": g})
    if diffs:
        msgs.append("값이 다른 행이 %d개 있습니다 (정렬 순서도 채점 대상입니다)" % len(diffs))
    return {"passed": not msgs, "messages": msgs, "diffs": diffs[:5],
            "expected_rows": len(exp_rows)}


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SQL 드릴</title>
<style>
:root{--bg:#F7F7F5;--panel:#fff;--fg:#1B1F23;--muted:#6B7280;--line:#E3E3DF;
      --accent:#1B64DA;--ok:#0F7B4F;--bad:#C0392B;--code:#F3F4F6;--rail:280px}
@media(prefers-color-scheme:dark){:root{--bg:#15181B;--panel:#1C2024;--fg:#E8EAEC;
      --muted:#99A1A9;--line:#2C3237;--accent:#6AA3F5;--ok:#4CC38A;--bad:#E57373;
      --code:#23282D;color-scheme:dark}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);overflow:hidden;
     font:14px/1.6 "Malgun Gothic",system-ui,sans-serif;
     display:grid;grid-template-columns:var(--rail) 400px 1fr;transition:grid-template-columns .18s}
body.railoff{--rail:0px}
@media(max-width:1100px){body{grid-template-columns:var(--rail) 340px 1fr}}
@media(max-width:860px){body{grid-template-columns:1fr;overflow:auto;height:auto}
  #rail{position:static!important;height:auto!important}
  body.railoff #rail{display:none}}

/* ── 1단: 접이식 문항 목록 ── */
#rail{background:var(--panel);border-right:1px solid var(--line);overflow:hidden auto;
      padding:14px 10px}
body.railoff #rail{padding:0;border:0}
#rail h1{font-size:14px;margin:0 0 4px;letter-spacing:-.3px;white-space:nowrap}
#rail .glink{display:block;font-size:12.5px;color:var(--accent);text-decoration:none;
      margin:0 0 12px;white-space:nowrap}
.qlist{display:flex;flex-direction:column;gap:2px}
.qbtn{text-align:left;border:1px solid transparent;background:none;color:var(--fg);
      padding:6px 8px;border-radius:7px;cursor:pointer;font:inherit;font-size:12.8px;
      display:flex;gap:6px;align-items:baseline}
.qbtn:hover{background:var(--code)}
.qbtn.on{background:var(--accent);color:#fff}
.qbtn .lv{color:var(--muted);font-size:11px;margin-left:auto;white-space:nowrap}
.qbtn.on .lv{color:#dbe7ff}
.qbtn.done::before{content:"✓";color:var(--ok);font-weight:700}
.qbtn.on.done::before{color:#fff}

/* ── 토글 버튼 ── */
#toggle{position:fixed;left:6px;top:8px;z-index:30;width:30px;height:30px;
        border:1px solid var(--line);background:var(--panel);color:var(--fg);
        border-radius:7px;cursor:pointer;font-size:15px;line-height:1;padding:0}
body:not(.railoff) #toggle{left:calc(var(--rail) - 36px)}
#toggle:hover{background:var(--code)}

/* ── 2단: 문제 + 테이블 ── */
#prob{border-right:1px solid var(--line);overflow-y:auto;padding:14px 16px 40px;min-width:0}
.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.hd h2{font-size:16px;margin:0;letter-spacing:-.3px}
.timer{margin-left:auto;font-variant-numeric:tabular-nums;font-size:14px;
       font-weight:700;color:var(--muted)}
.timer.over{color:var(--bad)}
.prompt{background:var(--panel);border:1px solid var(--line);border-radius:9px;
        padding:11px 13px;white-space:pre-wrap;word-break:keep-all;font-size:13.2px}
.spec{font-size:12.3px;color:var(--muted);margin:8px 0 0;word-break:break-all}
.spec code{background:var(--code);padding:2px 5px;border-radius:4px;color:var(--fg)}
.sec{margin-top:16px}
.sec h3{font-size:11.5px;margin:0 0 6px;color:var(--muted);letter-spacing:.5px}
.ltable{border-collapse:collapse;margin:0 0 9px;font-size:12px}
.ltable th,.ltable td{border:1px solid var(--line);padding:2px 8px;white-space:nowrap}
.ltable th{background:var(--code);font-weight:600;font-size:11.5px}
.tname{font-family:Consolas,monospace;font-weight:700;font-size:12.5px;margin:8px 0 3px}
.tnote{font-size:11.5px;color:var(--muted);word-break:keep-all}
.tnote ul{margin:3px 0 0;padding-left:15px}
.arrow{color:var(--muted);margin:2px 0 5px;font-size:12px}

/* ── 3단: 에디터 + 결과 ── */
#work{display:flex;flex-direction:column;padding:14px 16px;gap:9px;min-width:0;overflow:hidden}
@media(max-width:860px){#work{height:80vh}}
textarea{flex:1 1 55%;min-height:200px;resize:none;background:var(--panel);color:var(--fg);
         border:1px solid var(--line);border-radius:9px;padding:12px;
         font:13.5px/1.6 Consolas,"D2Coding",monospace;tab-size:2}
textarea:focus{outline:2px solid var(--accent);outline-offset:-1px}
.bar{display:flex;gap:8px;align-items:center;flex:0 0 auto}
button.go{border:0;border-radius:8px;padding:9px 20px;font:inherit;font-weight:700;cursor:pointer}
.run{background:var(--code);color:var(--fg);border:1px solid var(--line)!important}
.sub{background:var(--accent);color:#fff}
.hint{color:var(--muted);font-size:11.8px;margin-left:auto}
#eng{background:var(--panel);color:var(--fg);border:1px solid var(--line);
     border-radius:8px;padding:8px 10px;font:inherit;font-size:12.8px;cursor:pointer}
#eng:disabled{opacity:.5}
.engnote{font-size:11.5px;color:var(--muted);margin-left:2px}
#out{flex:1 1 45%;min-height:220px;overflow:auto;background:var(--panel);
     border:1px solid var(--line);border-radius:9px;padding:12px;font-size:12.5px}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:12.3px}
th,td{border:1px solid var(--line);padding:3px 9px;text-align:left;white-space:nowrap}
th{background:var(--code);font-size:11.5px;color:var(--muted)}
.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}
.msg{margin:3px 0}
.diff{font-family:Consolas,monospace;font-size:11.5px;margin:4px 0 0 12px;color:var(--muted)}
.diff b{color:var(--fg)}
</style></head><body>
<button id="toggle" title="문항 목록 (Ctrl+B)">☰</button>

<aside id="rail">
  <h1>SQL 드릴</h1>
  <a class="glink" href="/guide" target="_blank">📘 문항 해설 →</a>
  <a class="glink" href="/exam">⏱ 시험 모드 (6문항·90분) →</a>
  <div class="qlist" id="qlist"></div>
</aside>

<section id="prob">
  <div class="hd"><h2 id="title">문항을 고르세요</h2><span class="timer" id="timer"></span></div>
  <div class="prompt" id="prompt">왼쪽에서 문항을 선택하면 시작합니다.</div>
  <div class="spec" id="spec"></div>
  <div id="detail"></div>
</section>

<section id="work">
  <textarea id="sql" spellcheck="false" placeholder="여기에 쿼리를 쓰세요 (Ctrl+Enter = 실행)"></textarea>
  <div class="bar">
    <select id="eng" title="실행 엔진"></select>
    <button class="go run" id="brun">▶ 실행</button>
    <button class="go sub" id="bsub">제출</button>
    <span class="hint">실행은 내 결과만 · 제출해야 채점</span>
  </div>
  <div id="out">결과가 여기에 표시됩니다.</div>
</section>
<script>
let TASKS=[], TABLES=[], EXAMPLES={}, ENGINES=[], cur=null, t0=null, tick=null, done=JSON.parse(localStorage.getItem('done')||'[]');
const $=i=>document.getElementById(i);

function drawList(){
  $('qlist').innerHTML='';
  TASKS.forEach(t=>{
    const b=document.createElement('button');
    b.className='qbtn'+(cur&&cur.id===t.id?' on':'')+(done.includes(t.id)?' done':'');
    b.innerHTML='Q'+t.id+'. '+t.title+'<span class="lv">'+t.level+' '+t.minutes+'분</span>';
    b.onclick=()=>pick(t.id);
    $('qlist').appendChild(b);
  });
}
function ltable(cols,rows){
  let h='<table class="ltable"><tr>';
  cols.forEach(c=>h+='<th>'+esc(c)+'</th>'); h+='</tr>';
  rows.forEach(r=>{h+='<tr>';r.forEach(v=>h+='<td>'+esc(v)+'</td>');h+='</tr>';});
  return h+'</table>';
}
function schemaBlock(use){
  const list = use && use.length ? TABLES.filter(t=>use.includes(t.name)) : TABLES;
  let h='<div class="sec"><h3>테이블</h3>';
  list.forEach(t=>{
    h+='<div class="tname">'+esc(t.name)+'</div>';
    h+=ltable(['Column Name','Type'], t.cols.map(c=>[c[0],c[1]]));
    h+='<div class="tnote"><ul>'+t.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ul></div>';
  });
  return h+'</div>';
}
function exampleBlock(id){
  const e=EXAMPLES[String(id)]; if(!e)return '';
  let h='<div class="sec"><h3>예시</h3>';
  h+='<div style="color:var(--muted);font-size:12.5px;margin-bottom:6px">입력</div>';
  Object.keys(e.input).forEach(n=>{
    h+='<div class="tname">'+esc(n)+'</div>'+ltable(e.input[n].cols, e.input[n].rows);
  });
  h+='<div class="arrow">↓ 출력</div>'+ltable(e.output.cols, e.output.rows);
  return h+'</div>';
}
function pick(id){
  cur=TASKS.find(t=>t.id===id);
  $('title').textContent='Q'+cur.id+'. '+cur.title;
  $('prompt').textContent=cur.prompt;
  $('spec').innerHTML='출력 컬럼 <code>'+cur.columns+'</code> &nbsp;·&nbsp; 정렬 <code>'+cur.order_note+'</code>';
  $('detail').innerHTML=exampleBlock(cur.id)+schemaBlock(cur.tables);
  $('sql').value=''; $('out').textContent='결과가 여기에 표시됩니다.';
  t0=Date.now(); clearInterval(tick); tick=setInterval(clock,1000); clock();
  drawList(); history.replaceState(null,'','#'+cur.id); $('sql').focus();
}
function clock(){
  if(!cur){return;}
  const s=Math.floor((Date.now()-t0)/1000), lim=cur.minutes*60;
  const m=String(Math.floor(s/60)).padStart(2,'0'), ss=String(s%60).padStart(2,'0');
  $('timer').textContent=m+':'+ss+' / '+cur.minutes+':00';
  $('timer').className='timer'+(s>lim?' over':'');
}
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function table(cols,rows,cap){
  let h='<div style="margin-bottom:6px;color:var(--muted)">'+cap+'</div><table><tr>';
  cols.forEach(c=>h+='<th>'+esc(c)+'</th>'); h+='</tr>';
  rows.slice(0,40).forEach(r=>{h+='<tr>';r.forEach(v=>h+='<td>'+esc(v===null?'∅':v)+'</td>');h+='</tr>';});
  h+='</table>';
  if(rows.length>40)h+='<div style="color:var(--muted);margin-top:6px">… '+(rows.length-40)+'행 더</div>';
  return h;
}
async function post(path){
  if(!cur){alert('문항을 먼저 고르세요');return null;}
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:cur.id,sql:$('sql').value,engine:$('eng').value})});
  return r.json();
}
$('brun').onclick=async()=>{
  const d=await post('/run'); if(!d)return;
  if(d.error){$('out').innerHTML='<div class="bad">쿼리 오류</div><pre style="white-space:pre-wrap">'+esc(d.error)+'</pre>';return;}
  let h=table(d.cols,d.rows,'내 쿼리 결과 — '+d.rows.length+'행');
  if(d.colwarn)h='<div class="bad msg">⚠ 컬럼이 요구사항과 다릅니다 — 요구: '+esc(cur.columns)+'</div>'+h;
  if(d.lint)h='<div class="bad msg">⚠ '+esc(d.lint)+'</div>'+h;
  $('out').innerHTML=h;
};
$('bsub').onclick=async()=>{
  const d=await post('/submit'); if(!d)return;
  if(d.error){$('out').innerHTML='<div class="bad">쿼리 오류</div><pre style="white-space:pre-wrap">'+esc(d.error)+'</pre>';return;}
  const s=Math.floor((Date.now()-t0)/1000);
  const tm='소요 '+Math.floor(s/60)+'분 '+String(s%60).padStart(2,'0')+'초 / 제한 '+cur.minutes+'분'
           +(s>cur.minutes*60?' (초과)':'');
  const ds = d.datasets ? d.datasets.map(x=>'<div class="msg">'
      +(x.ok?'<span class="ok">✓</span>':'<span class="bad">✗</span>')
      +' 데이터셋 「'+esc(x.name)+'」'+(x.ok?'':' — '+esc(x.why))+'</div>').join('') : '';
  if(d.passed){
    if(!done.includes(cur.id)){done.push(cur.id);localStorage.setItem('done',JSON.stringify(done));}
    drawList();
    $('out').innerHTML='<div class="ok">✓ 통과 — 모든 데이터셋 일치</div><div class="msg">'+tm+'</div>'
      +'<div class="msg">· 메인 데이터 '+d.expected_rows+'행 일치</div>'+ds
      +(d.lint?'<div class="bad msg">⚠ '+esc(d.lint)+'</div>':'');
    return;
  }
  let h='<div class="bad">✗ 불일치</div><div class="msg">'+tm+'</div>';
  if(d.lint)h+='<div class="bad msg">⚠ '+esc(d.lint)+'</div>';
  d.messages.forEach(m=>h+='<div class="msg">· '+esc(m)+'</div>');
  if(ds)h+='<div class="msg" style="margin-top:8px;color:var(--muted)">데이터셋별 결과</div>'+ds;
  d.diffs.forEach(x=>{h+='<div class="diff"><b>'+x.row+'행</b> 정답 '+esc(x.expected.join(' | '))
                      +'<br>&nbsp;&nbsp;&nbsp;&nbsp;제출 '+esc(x.got.join(' | '))+'</div>';});
  $('out').innerHTML=h;
};
$('sql').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('brun').click();}
  if(e.key==='Tab'){e.preventDefault();const t=e.target,p=t.selectionStart;
    t.value=t.value.slice(0,p)+'  '+t.value.slice(t.selectionEnd);t.selectionStart=t.selectionEnd=p+2;}
});
fetch('/tasks').then(r=>r.json()).then(d=>{
  TASKS=d.tasks; TABLES=d.tables; EXAMPLES=d.examples||{}; ENGINES=d.engines||[];
  const sel=$('eng'), saved=localStorage.getItem('engine')||'duckdb';
  ENGINES.forEach(e=>{
    const o=document.createElement('option');
    o.value=e.key; o.textContent=e.name+(e.ok?'':' (설정 필요)'); o.disabled=!e.ok;
    if(e.key===saved&&e.ok)o.selected=true;
    sel.appendChild(o);
  });
  if(sel.selectedIndex<0||sel.options[sel.selectedIndex].disabled)sel.value='duckdb';
  const note=document.createElement('span'); note.className='engnote'; note.id='engnote';
  sel.after(note);
  const showNote=()=>{const e=ENGINES.find(x=>x.key===sel.value); note.textContent=e?e.desc:'';};
  sel.onchange=()=>{localStorage.setItem('engine',sel.value);showNote();};
  showNote();
  drawList();
  const h=parseInt((location.hash||'').replace('#',''),10);
  if(h && TASKS.some(t=>t.id===h)) pick(h);
});

// 사이드바 토글
const RK='railoff';
if(localStorage.getItem(RK)==='1')document.body.classList.add('railoff');
document.getElementById('toggle').onclick=()=>{
  document.body.classList.toggle('railoff');
  localStorage.setItem(RK, document.body.classList.contains('railoff')?'1':'0');
};
addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='b'){
    e.preventDefault();document.getElementById('toggle').click();}
});
</script></body></html>"""


GUIDE_CSS = """
/* ── 해설 버전 전환 ───────────────────────────────────────────── */
.modebar{position:sticky;top:0;z-index:9;background:var(--bg);
         padding:10px 0 12px;margin:0 0 4px;border-bottom:1px solid var(--line);
         display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.modebar b{font-size:12.5px;color:var(--muted);margin-right:2px}
.modebar button{border:1px solid var(--line);background:var(--panel);color:var(--fg);
                border-radius:999px;padding:6px 15px;font:inherit;font-size:13px;
                cursor:pointer}
.modebar button:hover{background:var(--code)}
.modebar button.on{background:var(--accent);color:#fff;border-color:var(--accent);
                   font-weight:700}
.vtag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.3px;
      padding:2px 9px;border-radius:999px;margin:0 0 8px}
.vtag.e{background:#E7F2E9;color:#0F7B4F}
.vtag.d{background:#E8EEFA;color:#1B64DA}
@media(prefers-color-scheme:dark){.vtag.e{background:#1C2E24;color:#4CC38A}
  .vtag.d{background:#1B2434;color:#6AA3F5}}
.ver{margin-bottom:6px}
.ver.easy{border-left:3px solid var(--ok);padding-left:14px}
.ver.deep{border-left:3px solid var(--accent);padding-left:14px}
body.mode-easy .ver.deep{display:none}
body.mode-easy .vtag{display:none}
body.mode-deep .ver.easy{display:none}
body.mode-deep .vtag{display:none}
body.mode-easy .ver.easy,body.mode-deep .ver.deep{border-left:0;padding-left:0}
body.mode-both .ver{margin-bottom:22px}

/* 쉬운 해설 안의 작은 표 */
.ver.easy .oneline{font-size:16px;line-height:1.7;margin:0 0 12px}
table.e{border-collapse:collapse;margin:4px 0 8px;font-size:13.5px}
table.e th,table.e td{border:1px solid var(--line);padding:4px 11px;text-align:left}
table.e th{background:var(--code);font-size:12.5px;color:var(--muted);font-weight:600}
table.e td.x{color:var(--bad)}
.ver.easy p.note{font-size:13.5px;color:var(--muted);margin:4px 0 10px;
                 word-break:keep-all}
.ver.easy h4{font-size:13px;color:var(--muted);margin:14px 0 5px}
.ver.easy ol,.ver.easy ul{margin:0;padding-left:21px}
.ver.easy li{margin-bottom:5px}
.ver.easy .wt{background:var(--warn);border-radius:9px;padding:10px 14px 10px 0}
.ver.easy .wt ul{padding-left:30px}

:root{--bg:#F7F7F5;--panel:#fff;--fg:#1B1F23;--muted:#6B7280;--line:#E3E3DF;
      --accent:#1B64DA;--bad:#C0392B;--ok:#0F7B4F;--code:#F3F4F6;--warn:#FFF8E6}
@media(prefers-color-scheme:dark){:root{--bg:#15181B;--panel:#1C2024;--fg:#E8EAEC;
      --muted:#99A1A9;--line:#2C3237;--accent:#6AA3F5;--bad:#E57373;--ok:#4CC38A;
      --code:#23282D;--warn:#2A2416;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:15px/1.75 "Malgun Gothic",system-ui,sans-serif;
     display:grid;grid-template-columns:210px 1fr}
@media(max-width:760px){body{grid-template-columns:1fr}
  aside{position:static!important;height:auto!important;border-right:0!important;
        border-bottom:1px solid var(--line)}}
aside{position:sticky;top:0;height:100vh;overflow-y:auto;background:var(--panel);
      border-right:1px solid var(--line);padding:16px 12px}
aside a{display:block;color:var(--fg);text-decoration:none;font-size:13px;
        padding:4px 8px;border-radius:6px}
aside a:hover{background:var(--code)}
aside .lv{color:var(--muted);font-size:11px}
aside h3{font-size:12px;color:var(--muted);margin:14px 0 6px;letter-spacing:.6px}
main{max-width:860px;padding:28px 24px 80px;min-width:0}
h1{font-size:25px;margin:0 0 6px;letter-spacing:-.5px}
h2{font-size:19px;margin:38px 0 10px;padding-top:10px;border-top:1px solid var(--line);
   letter-spacing:-.3px}
h2 .n{color:var(--accent)}
h2 .lv{font-size:12px;color:var(--muted);font-weight:400;margin-left:6px}
.lead{color:var(--muted);margin:0 0 20px}
.asks{background:var(--panel);border-left:3px solid var(--accent);padding:10px 14px;
      border-radius:0 8px 8px 0;margin:0 0 14px}
h4{font-size:13px;color:var(--muted);margin:18px 0 6px;letter-spacing:.5px}
ol,ul{margin:0 0 10px;padding-left:20px}
li{margin-bottom:5px}
pre{background:var(--code);border:1px solid var(--line);border-radius:9px;
    padding:13px 15px;overflow-x:auto;font:12.8px/1.6 Consolas,"D2Coding",monospace;
    margin:0 0 12px}
code{background:var(--code);padding:1px 5px;border-radius:4px;
     font:12.5px Consolas,monospace}
pre code{background:none;padding:0;font-size:inherit}
.trap{background:var(--warn);border:1px solid var(--line);border-radius:9px;
      padding:11px 15px;margin:0 0 12px}
.trap ul{margin:0;padding-left:18px}
.trap li{margin-bottom:7px}
.var{font-size:13.5px;color:var(--muted);border-left:2px solid var(--line);
     padding-left:12px;margin:0}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:0 0 16px}
th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;
      vertical-align:top}
th{color:var(--muted);font-size:12px;letter-spacing:.4px}
td:first-child{white-space:nowrap;font-weight:600}
td:nth-child(2){font-family:Consolas,monospace;font-size:12.5px;color:var(--accent)}
.chk{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px}
.chk li{margin-bottom:6px}
.top{display:inline-block;margin-top:10px;font-size:12.5px;color:var(--muted);
     text-decoration:none}
h3{font-size:17px;margin:30px 0 8px;padding-top:14px;border-top:1px dashed var(--line)}
h3 .grp{font-size:11px;color:var(--muted);background:var(--code);padding:2px 8px;
        border-radius:10px;margin-left:8px;vertical-align:middle;font-weight:400}
h5{font-size:12px;color:var(--muted);margin:14px 0 5px;letter-spacing:.4px}
pre.sig{background:var(--panel);border-left:3px solid var(--accent);font-weight:600}
table.args td:first-child{font-family:Consolas,monospace;color:var(--accent);
     font-size:12.5px;white-space:normal}
table.args td:nth-child(2){font-family:inherit;color:inherit;font-size:13px}
table.res{font-size:12.3px;margin:0 0 12px;width:auto}
table.res th,table.res td{border:1px solid var(--line);padding:3px 9px;white-space:nowrap}
table.res th{background:var(--code)}
.fnav{font-size:12.5px;line-height:2;margin:0 0 8px}
.arrow{color:var(--muted);font-size:15px;margin:0 0 8px;padding-left:14px}
.fnav a{color:var(--accent);text-decoration:none}
td a{color:var(--accent);text-decoration:none;border-bottom:1px dotted var(--accent)}
"""


def _tbl(ex):
    if not ex:
        return ""
    h = '<table class="res"><tr>' + "".join("<th>%s</th>" % c for c in ex["cols"]) + "</tr>"
    for r in ex["rows"]:
        h += "<tr>" + "".join("<td>%s</td>" % v for v in r) + "</tr>"
    return h + "</table>"


def _inp(ex):
    """예제의 입력 테이블. 입력을 모르면 결과를 읽을 수 없다."""
    if not ex or "input" not in ex:
        return ""
    return '<h5>입력 테이블</h5>' + _tbl(ex["input"]) + '<div class="arrow">↓</div>'


def _funcs_html():
    esc = lambda x: x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = []
    for f in FUNCS:
        args = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % a for a in f["args"])
        notes = "".join("<li>%s</li>" % n for n in f["notes"])
        out.append("""
<h3 id="f-%s">%s <span class="grp">%s</span></h3>
<pre class="sig"><code>%s</code></pre>
<table class="args"><tr><th>인자</th><th>설명</th><th>생략하면</th></tr>%s</table>
%s<h5>쿼리</h5>
<pre><code>%s</code></pre>
<h5>결과</h5>%s
<h5>실수 포인트</h5><div class="trap"><ul>%s</ul></div>
<a class="top" href="#funcs">↑ 함수 목록</a>""" % (
            f["key"], f["name"], f["group"], esc(f["sig"]), args,
            _inp(FUNC_EX.get(f["key"])), esc(f["demo"]),
            _tbl((FUNC_EX.get(f["key"]) or {}).get("output")), notes))
    nav = " · ".join('<a href="#f-%s">%s</a>' % (f["key"], f["name"]) for f in FUNCS)
    return ('<h2 id="funcs">함수 레퍼런스</h2>'
            '<p class="lead">패턴 지도의 함수 이름을 누르면 여기로 옵니다. '
            '인자와 생략 시 동작, 그리고 실제 실행 결과입니다.</p>'
            '<p class="fnav">%s</p>%s' % (nav, "".join(out)))


def guide_html():
    nav = "".join(
        '<a href="#q%d">Q%d. %s <span class="lv">%s</span></a>'
        % (g["id"], g["id"], g["title"], g["level"]) for g in GUIDE)
    def _link(tech):
        for f in FUNCS:
            for kw in f["name"].replace("/", " ").split():
                if kw and kw.upper() in tech.upper():
                    return '<a href="#f-%s">%s</a>' % (f["key"], tech)
        for f in FUNCS:
            if f["key"] in ("islands", "median", "dedupe", "nullfn", "frame") and                any(w in tech for w in ("gaps", "ROW_NUMBER + COUNT", "NULLIF", "ROWS BETWEEN")):
                return '<a href="#f-%s">%s</a>' % (f["key"], tech)
        return tech
    pat = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                  % (p[0], _link(p[1]), p[2]) for p in PATTERNS)
    funcs = _funcs_html()
    chk = "".join("<li>%s</li>" % c for c in CHECKS)

    body = []
    for g in GUIDE:
        steps = "".join("<li>%s</li>" % x for x in g["steps"])
        traps = "".join("<li>%s</li>" % x for x in g["traps"])
        sql = (g["sql"].replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;"))

        # 쉬운 버전
        e = EASY_BY_ID.get(g["id"])
        if e:
            easy = ("""
<div class="ver easy"><span class="vtag e">쉬운 설명</span>
<p class="oneline">%s</p>%s
<h4>이렇게 푼다</h4><ol>%s</ol>
<h4>이것만 피하면 된다</h4><div class="wt"><ul>%s</ul></div></div>"""
                    % (e["oneline"], e.get("idea", ""),
                       "".join("<li>%s</li>" % x for x in e["how"]),
                       "".join("<li>%s</li>" % x for x in e["watch"])))
        else:
            easy = ""

        # 자세한 버전
        deep = """
<div class="ver deep"><span class="vtag d">자세한 설명</span>
<div class="asks"><b>묻는 것</b> · %s</div>
<h4>풀이 순서</h4><ol>%s</ol>
<h4>정답 (MySQL)</h4><pre><code>%s</code></pre>
<h4>함정</h4><div class="trap"><ul>%s</ul></div>
<h4>이렇게 변형된다</h4><p class="var">%s</p></div>""" % (
            g["asks"], steps, sql, traps, g["variants"])

        body.append("""
<h2 id="q%d"><span class="n">Q%d.</span> %s<span class="lv">%s</span></h2>
%s%s<a class="top" href="#top">↑ 위로</a>""" % (
            g["id"], g["id"], g["title"], g["level"], easy, deep))

    return """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SQL 문항 해설</title><style>%s</style></head><body>
<aside>
  <a href="/" style="font-weight:700;color:var(--accent)">← 드릴로</a>
  <h3>빠른 이동</h3>
  <a href="#map">패턴 지도</a><a href="#check">제출 전 체크</a><a href="#funcs"><b>함수 레퍼런스</b></a>
  <h3>문항</h3>%s
</aside>
<main id="top">
  <h1>SQL 문항 해설</h1>
  <p class="lead">정답보다 <b>왜 그렇게 푸는지</b>와 <b>어디서 틀리는지</b>를 보세요.
     같은 유형이 다시 나왔을 때 바로 꺼내 쓰는 게 목적입니다.</p>
  <div class="modebar">
    <b>해설 버전</b>
    <button data-m="easy">쉽게</button>
    <button data-m="deep">자세히</button>
    <button data-m="both">나란히 비교</button>
  </div>

  <h2 id="map">패턴 지도</h2>
  <p class="lead">문제에 이 표현이 나오면 이 기법을 꺼냅니다. 해설보다 이 표를 먼저 외우세요.</p>
  <table><tr><th>문제에 이렇게 나오면</th><th>이 기법</th><th>주의</th></tr>%s</table>

  <h2 id="check">제출 전 체크</h2>
  <div class="chk"><ul>%s</ul></div>
  %s
  %s
</main>
<script>
(function(){
  var KEY='guideMode';
  function set(m){
    document.body.className='mode-'+m;
    var bs=document.querySelectorAll('.modebar button');
    for(var i=0;i<bs.length;i++)
      bs[i].className=(bs[i].getAttribute('data-m')===m)?'on':'';
    try{localStorage.setItem(KEY,m);}catch(e){}
  }
  var bs=document.querySelectorAll('.modebar button');
  for(var i=0;i<bs.length;i++)
    bs[i].onclick=function(){set(this.getAttribute('data-m'));};
  var saved='easy';
  try{saved=localStorage.getItem(KEY)||'easy';}catch(e){}
  set(saved);
})();
</script>
</body></html>""" % (GUIDE_CSS, nav, pat, chk, funcs, "".join(body))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json"):
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            self._send(PAGE, "text/html")
        elif self.path == "/guide":
            self._send(guide_html(), "text/html")
        elif self.path == "/exam":
            self._send(EXAM.page(), "text/html")
        elif self.path == "/exam/new":
            ids = EXAM.pick_six(TASKS)
            self._send(json.dumps({"ids": ids,
                                   "limits": EXAM.budgets(TASKS, ids)},
                                  ensure_ascii=False))
        elif self.path == "/tasks":
            ts = []
            for t in TASKS:
                d = {k: t[k] for k in ("id", "title", "level", "minutes",
                                       "prompt", "columns", "order_note")}
                d["tables"] = used_tables(t)
                ts.append(d)
            self._send(json.dumps({"tasks": ts, "tables": TABLES,
                                   "examples": EXAMPLES,
                                   "engines": [{"key": k, "name": v[0], "desc": v[1], "ok": True}
                                               for k, v in DIA.DIALECTS.items()]}, ensure_ascii=False))
        else:
            self.send_error(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        task = next((t for t in TASKS if t["id"] == req.get("id")), None)
        sql = "\n".join(l for l in (req.get("sql") or "").splitlines()
                        if not l.strip().startswith("--")).strip()
        if not task or not sql:
            self._send(json.dumps({"error": "쿼리가 비어 있습니다."}, ensure_ascii=False)); return
        dialect = req.get("engine") or "mysql"
        try:
            cols, rows = DIA.run(sql, dialect)
        except Exception as e:
            self._send(json.dumps({"error": str(e)[:900]}, ensure_ascii=False)); return

        if self.path == "/run":
            want = [c.strip().lower() for c in task["columns"].split(",")]
            self._send(json.dumps({"cols": cols, "rows": rows,
                                   "colwarn": [c.lower() for c in cols] != want,
                                   "lint": lint_intdiv(sql)},
                                  ensure_ascii=False))
        elif self.path == "/submit":
            res = grade(task, cols, rows)
            res["lint"] = lint_intdiv(sql)
            if res["passed"]:
                res["datasets"] = check_datasets(task, sql, dialect)
                bad = [d for d in res["datasets"] if not d["ok"]]
                if bad:
                    res["passed"] = False
                    res["messages"].append(
                        "추가 데이터셋에서 실패: "
                        + ", ".join("%s(%s)" % (d.get("name", "?"),
                                                d.get("why") or d.get("msg") or "불일치")
                                    for d in bad))
            self._send(json.dumps(res, ensure_ascii=False))
        else:
            self.send_error(404)


def main():
    if not os.path.exists(DB):
        sys.exit("practice.duckdb 가 없습니다. 먼저 python seed.py 를 실행하세요.")
    url = "http://127.0.0.1:%d/" % PORT
    print("\n  SQL 드릴 실행 중  →  %s" % url)
    print("  종료하려면 이 창에서 Ctrl+C\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    except KeyboardInterrupt:
        print("  종료했습니다.")


if __name__ == "__main__":
    main()
