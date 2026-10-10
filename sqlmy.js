/* MySQL 문법을 브라우저 SQLite 위에서 돌리기.
 *
 * 서버에서 쓰던 dialects.py 를 그대로 옮겼다. 두 가지를 한다.
 *   1) SQLite 에 없는 MySQL 함수를 자바스크립트로 등록한다
 *   2) 함수로 못 덮는 문법(INTERVAL 등)은 텍스트를 바꾼다
 *
 * 실행 엔진이 SQLite 인 것은 의도다. 테스트돔에서 MySQL 문법을 골라도
 * `*1.0` 이 없으면 0 이 나왔다 — 채점 엔진이 정수 나눗셈을 한다는 뜻이고,
 * 그게 SQLite 동작이다. '문법은 MySQL, 셈은 정수 나눗셈' 이 실전에 가장 가깝다.
 */
(function (global) {
  "use strict";

  // ── 날짜 유틸 ────────────────────────────────────────────────────
  function toDate(v) {
    if (v === null || v === undefined) return null;
    var s = String(v).slice(0, 10);
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (!m) return null;
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  }
  function pad(n, w) {
    var s = String(Math.abs(n));
    while (s.length < w) s = "0" + s;
    return (n < 0 ? "-" : "") + s;
  }
  function iso(d) {
    return pad(d.getUTCFullYear(), 4) + "-" + pad(d.getUTCMonth() + 1, 2)
         + "-" + pad(d.getUTCDate(), 2);
  }
  var DAY = 86400000;

  function dateFormat(v, fmt) {
    var d = toDate(v);
    if (d === null || fmt === null || fmt === undefined) return null;
    var yday = Math.floor((d - Date.UTC(d.getUTCFullYear(), 0, 1)) / DAY) + 1;
    var map = {
      Y: pad(d.getUTCFullYear(), 4), y: pad(d.getUTCFullYear() % 100, 2),
      m: pad(d.getUTCMonth() + 1, 2), c: String(d.getUTCMonth() + 1),
      d: pad(d.getUTCDate(), 2), e: String(d.getUTCDate()),
      H: "00", i: "00", s: "00", j: pad(yday, 3)
    };
    var out = "", i = 0, f = String(fmt);
    while (i < f.length) {
      if (f[i] === "%" && i + 1 < f.length) {
        out += (map[f[i + 1]] !== undefined ? map[f[i + 1]] : f[i + 1]);
        i += 2;
      } else { out += f[i]; i += 1; }
    }
    return out;
  }

  function dateDiff(a, b) {           // MySQL: DATEDIFF(끝, 시작)
    var x = toDate(a), y = toDate(b);
    if (x === null || y === null) return null;
    return Math.round((x - y) / DAY);
  }

  function monthsBetween(a, b) {
    var x = toDate(a), y = toDate(b);
    if (x === null || y === null) return null;
    var n = (y.getUTCFullYear() - x.getUTCFullYear()) * 12
          + (y.getUTCMonth() - x.getUTCMonth());
    if (y.getUTCDate() < x.getUTCDate()) n -= 1;
    return n;
  }

  function tsDiff(unit, a, b) {
    var u = String(unit || "").toLowerCase();
    if (u === "month") return monthsBetween(a, b);
    if (u === "year") { var m = monthsBetween(a, b); return m === null ? null : Math.trunc(m / 12); }
    if (u === "quarter") { var q = monthsBetween(a, b); return q === null ? null : Math.trunc(q / 3); }
    var d = dateDiff(b, a);
    if (d === null) return null;
    return { day: d, week: Math.trunc(d / 7), hour: d * 24,
             minute: d * 1440, second: d * 86400 }[u] !== undefined
         ? { day: d, week: Math.trunc(d / 7), hour: d * 24,
             minute: d * 1440, second: d * 86400 }[u] : d;
  }

  function periodDiff(p1, p2) {
    function pm(p) {
      var s = String(p);
      return parseInt(s.slice(0, 4), 10) * 12 + parseInt(s.slice(4, 6), 10);
    }
    var a = pm(p1), b = pm(p2);
    return (isNaN(a) || isNaN(b)) ? null : a - b;
  }

  function lastDay(v) {
    var d = toDate(v);
    if (d === null) return null;
    var nxt = new Date(Date.UTC(d.getUTCFullYear() + (d.getUTCMonth() === 11 ? 1 : 0),
                                (d.getUTCMonth() + 1) % 12, 1));
    return iso(new Date(nxt - DAY));
  }

  var UDFS = {
    DATE_FORMAT: dateFormat,
    DATEDIFF: dateDiff,
    TIMESTAMPDIFF: tsDiff,
    PERIOD_DIFF: periodDiff,
    LAST_DAY: lastDay,
    YEAR:  function (v) { var d = toDate(v); return d && d.getUTCFullYear(); },
    MONTH: function (v) { var d = toDate(v); return d && (d.getUTCMonth() + 1); },
    DAY:   function (v) { var d = toDate(v); return d && d.getUTCDate(); },
    DAYOFMONTH: function (v) { var d = toDate(v); return d && d.getUTCDate(); },
    CURDATE: function () { return iso(new Date()); },
    NOW: function () { return iso(new Date()); }
  };

  // ── 함수로 못 덮는 문법은 텍스트를 바꾼다 ────────────────────────
  var UNITS = "MICROSECOND|SECOND|MINUTE|HOUR|DAY|WEEK|MONTH|QUARTER|YEAR";
  var RE_TSD = new RegExp("\\bTIMESTAMPDIFF\\s*\\(\\s*(" + UNITS + ")\\s*,", "gi");
  var RE_ADD = /\bDATE_ADD\s*\(\s*(.+?)\s*,\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)/gi;
  var RE_SUB = /\bDATE_SUB\s*\(\s*(.+?)\s*,\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)/gi;
  var RE_INT = /\s*([+\-])\s*INTERVAL\s+'?(\d+)'?\s+(\w+)/i;

  function isWord(ch) { return /[A-Za-z0-9_.]/.test(ch); }

  /* end 바로 앞 피연산자의 시작 위치.
     DATE(x) - INTERVAL 1 MONTH 처럼 왼쪽이 함수 호출일 수 있어서
     괄호 짝을 세며 뒤로 훑는다. 단순 정규식으로는 못 잡는다. */
  function leftOperand(sql, end) {
    var i = end - 1;
    while (i >= 0 && /\s/.test(sql[i])) i--;
    if (i >= 0 && sql[i] === ")") {
      var depth = 0;
      while (i >= 0) {
        if (sql[i] === ")") depth++;
        else if (sql[i] === "(") { depth--; if (depth === 0) break; }
        i--;
      }
      var j = i - 1;
      while (j >= 0 && isWord(sql[j])) j--;
      return j + 1;
    }
    var k = i;
    while (k >= 0 && (isWord(sql[k]) || sql[k] === "'" || sql[k] === '"')) k--;
    return k + 1;
  }

  function applyInterval(sql) {
    var out = sql, guard = 0;
    while (guard++ < 200) {
      var m = RE_INT.exec(out);
      if (!m) return out;
      var start = leftOperand(out, m.index);
      var expr = out.slice(start, m.index).trim();
      if (!expr) return out;
      var sign = m[1] === "+" ? "+" : "-";
      var repl = "date(" + expr + ", '" + sign + m[2] + " " + m[3].toLowerCase() + "')";
      var next = out.slice(0, start) + repl + out.slice(m.index + m[0].length);
      if (next === out) return out;
      out = next;
    }
    return out;
  }

  function translate(sql) {
    var s = String(sql);
    s = s.replace(RE_TSD, function (_, u) { return "TIMESTAMPDIFF('" + u.toLowerCase() + "',"; });
    s = s.replace(RE_ADD, function (_, x, n, u) { return "date(" + x + ", '+" + n + " " + u.toLowerCase() + "')"; });
    s = s.replace(RE_SUB, function (_, x, n, u) { return "date(" + x + ", '-" + n + " " + u.toLowerCase() + "')"; });
    s = applyInterval(s);
    s = s.split("`").join('"');          // MySQL 백틱 식별자
    return s;
  }

  function install(db) {
    Object.keys(UDFS).forEach(function (name) {
      try { db.create_function(name, UDFS[name]); } catch (e) { /* 이미 있으면 무시 */ }
    });
    return db;
  }

  /* 주석 줄을 떼고 실행한다. 결과는 {cols, rows} — 값은 전부 문자열 또는 null. */
  function run(db, sql) {
    var body = String(sql).split("\n")
      .filter(function (l) { return l.trim().slice(0, 2) !== "--"; })
      .join("\n").trim();
    if (!body) throw new Error("쿼리가 비어 있습니다.");
    var st = db.prepare(translate(body));
    var cols = null, rows = [];
    try {
      while (st.step()) {
        if (cols === null) cols = st.getColumnNames();
        rows.push(st.get().map(function (v) {
          if (v === null || v === undefined) return null;
          if (v instanceof Uint8Array) return "(binary)";
          return String(v);
        }));
      }
      if (cols === null) cols = st.getColumnNames();
    } finally { st.free(); }
    return { cols: cols || [], rows: rows };
  }

  global.SQLMy = { translate: translate, install: install, run: run, UDFS: UDFS };
})(window);
