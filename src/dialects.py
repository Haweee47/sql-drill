# -*- coding: utf-8 -*-
"""문법(dialect) 선택.

테스트돔처럼 '어떤 문법으로 쓸지'를 고른다. 서버는 필요 없다.
실행은 전부 SQLite 로 한다. 이유가 있다.

  · 테스트돔에서 MySQL 문법을 골라도 `*1.0` 이 없으면 0 이 나왔다.
    즉 채점 엔진이 정수 나눗셈을 한다. 그건 SQLite(및 MS SQL) 동작이다.
  · 그래서 '문법은 MySQL, 셈은 정수 나눗셈' 조합이 실제 시험과 가장 가깝다.

MySQL 문법은 SQLite 에 없는 함수를 파이썬 UDF 로 채워 넣어 지원한다.
"""
import os
import re
import sqlite3
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SQLITE = os.path.join(HERE, "practice.sqlite")


# ── MySQL 함수를 파이썬으로 구현 ──────────────────────────────────────
def _d(v):
    if v is None:
        return None
    s = str(v)[:10]
    try:
        return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError):
        return None


def _date_format(v, fmt):
    d = _d(v)
    if d is None or fmt is None:
        return None
    out, i = [], 0
    m = {"Y": "%04d" % d.year, "y": "%02d" % (d.year % 100), "m": "%02d" % d.month,
         "c": str(d.month), "d": "%02d" % d.day, "e": str(d.day),
         "H": "00", "i": "00", "s": "00", "j": "%03d" % d.timetuple().tm_yday}
    while i < len(fmt):
        if fmt[i] == "%" and i + 1 < len(fmt):
            out.append(m.get(fmt[i + 1], fmt[i + 1])); i += 2
        else:
            out.append(fmt[i]); i += 1
    return "".join(out)


def _datediff(a, b):
    x, y = _d(a), _d(b)
    return None if x is None or y is None else (x - y).days


def _months(a, b):
    x, y = _d(a), _d(b)
    if x is None or y is None:
        return None
    n = (y.year - x.year) * 12 + (y.month - x.month)
    if y.day < x.day:
        n -= 1
    return n


def _tsdiff(unit, a, b):
    u = (unit or "").lower()
    if u == "month":
        return _months(a, b)
    if u == "year":
        m = _months(a, b)
        return None if m is None else m // 12
    if u == "quarter":
        m = _months(a, b)
        return None if m is None else m // 3
    d = _datediff(b, a)
    if d is None:
        return None
    return {"day": d, "week": d // 7, "hour": d * 24,
            "minute": d * 1440, "second": d * 86400}.get(u, d)


def _period_diff(p1, p2):
    def pm(p):
        s = str(p)
        return int(s[:4]) * 12 + int(s[4:6])
    try:
        return pm(p1) - pm(p2)
    except (ValueError, TypeError):
        return None


def _last_day(v):
    d = _d(v)
    if d is None:
        return None
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).isoformat()


UDFS = {
    "DATE_FORMAT": (2, _date_format),
    "DATEDIFF": (2, _datediff),
    "TIMESTAMPDIFF": (3, _tsdiff),
    "PERIOD_DIFF": (2, _period_diff),
    "LAST_DAY": (1, _last_day),
    "YEAR": (1, lambda v: (_d(v) or date(1, 1, 1)).year if _d(v) else None),
    "MONTH": (1, lambda v: (_d(v) or date(1, 1, 1)).month if _d(v) else None),
    "DAY": (1, lambda v: (_d(v) or date(1, 1, 1)).day if _d(v) else None),
    "DAYOFMONTH": (1, lambda v: (_d(v) or date(1, 1, 1)).day if _d(v) else None),
    "CURDATE": (0, lambda: date.today().isoformat()),
    "NOW": (0, lambda: date.today().isoformat()),
}

# ── 함수로 못 덮는 문법은 텍스트로 바꾼다 ──────────────────────────────
_UNITS = "MICROSECOND SECOND MINUTE HOUR DAY WEEK MONTH QUARTER YEAR"
_TSD = re.compile(r"\bTIMESTAMPDIFF\s*\(\s*(" + _UNITS.replace(" ", "|") + r")\s*,", re.I)
# DATE_ADD(x, INTERVAL 30 DAY) / x + INTERVAL 30 DAY  →  date(x, '+30 day')
_ADD = re.compile(r"\bDATE_ADD\s*\(\s*(.+?)\s*,\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)", re.I)
_SUB = re.compile(r"\bDATE_SUB\s*\(\s*(.+?)\s*,\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)", re.I)
_INTERVAL = re.compile(r"\s*([+\-])\s*INTERVAL\s+'?(\d+)'?\s+(\w+)", re.I)


def _left_operand(sql, end):
    """end 위치 바로 앞의 피연산자 시작 지점을 찾는다.

    DATE(x) - INTERVAL 1 MONTH 처럼 왼쪽이 함수 호출일 수 있어서
    괄호 짝을 세며 뒤로 훑는다. 단순 정규식으로는 못 잡는다.
    """
    i = end - 1
    while i >= 0 and sql[i].isspace():
        i -= 1
    if i >= 0 and sql[i] == ")":
        depth = 0
        while i >= 0:
            if sql[i] == ")":
                depth += 1
            elif sql[i] == "(":
                depth -= 1
                if depth == 0:
                    break
            i -= 1
        # 괄호 앞에 붙은 함수 이름까지 포함
        j = i - 1
        while j >= 0 and (sql[j].isalnum() or sql[j] in "_."):
            j -= 1
        return j + 1
    j = i
    while j >= 0 and (sql[j].isalnum() or sql[j] in "_.'\""):
        j -= 1
    return j + 1


def _apply_interval(sql):
    """<식> ± INTERVAL n UNIT  →  date(<식>, '+n unit')"""
    out = sql
    while True:
        m = _INTERVAL.search(out)
        if not m:
            return out
        start = _left_operand(out, m.start())
        expr = out[start:m.start()].strip()
        if not expr:
            return out
        sign = "+" if m.group(1) == "+" else "-"
        repl = "date(%s, '%s%s %s')" % (expr, sign, m.group(2), m.group(3).lower())
        nxt = out[:start] + repl + out[m.end():]
        if nxt == out:
            return out
        out = nxt


def mysql_to_sqlite(sql):
    """MySQL 문법을 SQLite 가 알아듣게 바꾼다."""
    sql = _TSD.sub(lambda m: "TIMESTAMPDIFF('%s'," % m.group(1).lower(), sql)
    sql = _ADD.sub(lambda m: "date(%s, '+%s %s')" % (m.group(1), m.group(2), m.group(3).lower()), sql)
    sql = _SUB.sub(lambda m: "date(%s, '-%s %s')" % (m.group(1), m.group(2), m.group(3).lower()), sql)
    sql = _apply_interval(sql)
    # MySQL 의 백틱 식별자
    sql = sql.replace("`", '"')
    return sql


def connect(path=None):
    con = sqlite3.connect(path or SQLITE)
    for name, (nargs, fn) in UDFS.items():
        con.create_function(name, nargs, fn)
    return con


DIALECTS = {
    "mysql":  ("MySQL 문법", "DATE_FORMAT·DATEDIFF·INTERVAL 사용 · 정수 나눗셈 주의"),
    "sqlite": ("SQLite 문법", "strftime·date() 사용 · 정수 나눗셈 주의"),
}


def run(sql, dialect="mysql", path=None):
    """선택한 문법으로 쿼리를 실행한다. 엔진은 항상 SQLite."""
    q = mysql_to_sqlite(sql) if dialect == "mysql" else sql
    con = connect(path)
    try:
        cur = con.execute(q)
        return ([d[0] for d in cur.description],
                [[None if v is None else str(v) for v in r] for r in cur.fetchall()])
    finally:
        con.close()
