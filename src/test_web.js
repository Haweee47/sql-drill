/* web/ 번들이 서버판과 같은 채점 결과를 내는지 확인한다.
 *
 *   node test_web.js
 *
 * 정답_MySQL.sql 의 모범답안을 전부 돌려서
 * 본 데이터 + 추가 데이터셋을 모두 통과하는지 본다.
 */
const fs = require("fs");
const path = require("path");

global.window = global;                       // sqlmy.js 는 브라우저용 IIFE
require("./sqlmy.js");
const initSqlJs = require("./sql-wasm.js");

const D = f => JSON.parse(fs.readFileSync(path.join(__dirname, "data", f), "utf8"));
const TASKS = D("tasks.json");
const EXPECT = D("expected.json");
const DS = D("datasets.json");

/* index.html 과 같은 정규화 */
function norm(v) {
  if (v === null || v === undefined) return "∅";
  const s = String(v).trim();
  if (s === "" || s === "None") return "∅";
  const f = Number(s);
  if (!Number.isNaN(f) && Number.isFinite(f)) return String(Number(f.toPrecision(9)));
  return s;
}
const rowKey = r => r.map(norm).join("\u0001");

/* 정답_MySQL.sql 에서 문항별 답안을 읽는다 */
function loadAnswers() {
  const s = fs.readFileSync(path.join(__dirname, "..", "정답_MySQL.sql"), "utf8");
  const marks = [];
  const re = /^--\s*[─\-]*\s*Q(\d+)\./gm;
  let m;
  while ((m = re.exec(s))) marks.push([m.index, +m[1]]);
  const out = {};
  marks.forEach(([pos, qid], k) => {
    const end = k + 1 < marks.length ? marks[k + 1][0] : s.length;
    let body = s.slice(pos, end);
    body = body.slice(body.indexOf("\n") + 1);
    body = body.split("\n").filter(l => !l.trim().startsWith("--")).join("\n").trim();
    if (body.includes(";")) body = body.slice(0, body.indexOf(";"));
    if (body.trim()) out[qid] = body.trim();
  });
  return out;
}

(async () => {
  const SQL = await initSqlJs({ locateFile: f => path.join(__dirname, f) });
  const DB = new SQL.Database(
    new Uint8Array(fs.readFileSync(path.join(__dirname, "data", "practice.sqlite"))));
  SQLMy.install(DB);

  function buildDataset(spec) {
    const db = new SQL.Database();
    Object.keys(DS.ddl).forEach(t => {
      db.run(`CREATE TABLE ${t} (${DS.ddl[t]})`);
      const d = spec.tables[t];
      if (!d || !d.rows.length) return;
      const st = db.prepare(
        `INSERT INTO ${t} (${d.cols.join(",")}) VALUES (${d.cols.map(() => "?").join(",")})`);
      d.rows.forEach(r => st.run(r));
      st.free();
    });
    SQLMy.install(db);
    return db;
  }

  const answers = loadAnswers();
  console.log(`모범답안 ${Object.keys(answers).length}개 / 문항 ${TASKS.length}개`);
  console.log("-".repeat(72));

  let bad = 0;
  for (const task of TASKS) {
    const sql = answers[task.id];
    if (!sql) { console.log(`Q${String(task.id).padEnd(2)} 답안 없음 (건너뜀)`); continue; }

    let got;
    try { got = SQLMy.run(DB, sql); }
    catch (e) {
      console.log(`Q${String(task.id).padEnd(2)} 실행 실패 — ${String(e.message).split("\n")[0].slice(0, 70)}`);
      bad++; continue;
    }

    const fails = [];
    const exp = EXPECT[task.id].main;
    const want = task.columns.split(",").map(s => s.trim().toLowerCase());
    if (got.cols.map(c => c.toLowerCase()).join("|") !== want.join("|"))
      fails.push(`본데이터: 컬럼 [${got.cols.join(", ")}]`);
    else if (got.rows.length !== exp.rows.length)
      fails.push(`본데이터: 행 수 ${got.rows.length} ≠ ${exp.rows.length}`);
    else {
      for (let i = 0; i < got.rows.length; i++) {
        if (rowKey(got.rows[i]) !== rowKey(exp.rows[i])) {
          fails.push(`본데이터: ${i + 1}행 [${got.rows[i].map(norm).join("|")}] ≠ [${exp.rows[i].map(norm).join("|")}]`);
          break;
        }
      }
    }

    for (const s of DS.sets) {
      const e = EXPECT[task.id][s.name];
      if (!e || e.error) continue;
      let db = null;
      try {
        db = buildDataset(s);
        const g = SQLMy.run(db, sql);
        if (g.rows.length !== e.rows.length) fails.push(`${s.name}: 행 ${g.rows.length} ≠ ${e.rows.length}`);
        else {
          const a = g.rows.map(rowKey).sort().join("\u0002");
          const b = e.rows.map(rowKey).sort().join("\u0002");
          if (a !== b) fails.push(`${s.name}: 결과 집합 불일치`);
        }
      } catch (err) {
        fails.push(`${s.name}: 오류 ${String(err.message).split("\n")[0].slice(0, 50)}`);
      } finally { if (db) db.close(); }
    }

    if (fails.length) {
      bad++;
      console.log(`Q${String(task.id).padEnd(2)} 실패`);
      fails.slice(0, 3).forEach(f => console.log(`      - ${f}`));
    } else {
      console.log(`Q${String(task.id).padEnd(2)} 통과 (본데이터 + 데이터셋 ${DS.sets.length}개)`);
    }
  }
  console.log("-".repeat(72));
  console.log(`실패 ${bad}개`);
  process.exit(bad ? 1 : 0);
})();
