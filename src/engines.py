# -*- coding: utf-8 -*-
"""실행 엔진 선택.

테스트돔처럼 엔진을 골라서 풀 수 있게 한다.

  duckdb  기본. 설정 불필요. MySQL 함수 일부를 호환 레이어로 흉내 낸다.
  sqlite  진짜 SQLite. 정수 나눗셈 등 실제 동작이 그대로 재현된다.
  mysql   진짜 MySQL. mysql.cnf 와 seed.sql 적재가 필요하다.

정답(기대값)은 항상 duckdb 의 참조 쿼리로 만든다. 사용자의 쿼리만 선택한
엔진에서 돌린다. 그래야 엔진을 바꿔도 같은 정답으로 채점된다.
"""
import csv
import os
import re
import subprocess

import duckdb

import tables_extra as TX

HERE = os.path.dirname(os.path.abspath(__file__))
DUCK = os.path.join(HERE, "practice.duckdb")
SQLITE = os.path.join(HERE, "practice.sqlite")
CNF = os.path.join(HERE, "mysql.cnf")

# DATE_FORMAT 은 포맷이 상수여야 해서 매크로로 못 만든다. 텍스트로 바꾼다.
_DATEFMT = re.compile(r"\bDATE_FORMAT\s*\(\s*([^,]+?)\s*,\s*('[^']*')\s*\)", re.I)
_UNITS = "MICROSECOND SECOND MINUTE HOUR DAY WEEK MONTH QUARTER YEAR".split()
_TSDIFF = re.compile(r"\bTIMESTAMPDIFF\s*\(\s*(" + "|".join(_UNITS) + r")\s*,", re.I)

_MACROS = [
    "CREATE OR REPLACE MACRO memory.MY_DATEDIFF(a,b) AS "
    "date_diff('day', CAST(b AS DATE), CAST(a AS DATE))",
    "CREATE OR REPLACE MACRO memory.DATE_ADD(d,i) AS CAST(d AS TIMESTAMP) + i",
    "CREATE OR REPLACE MACRO memory.DATE_SUB(d,i) AS CAST(d AS TIMESTAMP) - i",
    "CREATE OR REPLACE MACRO memory.LAST_DAY(d) AS "
    "(date_trunc('month', CAST(d AS DATE)) + INTERVAL 1 MONTH - INTERVAL 1 DAY)",
    "CREATE OR REPLACE MACRO memory.PERIOD_DIFF(a,b) AS "
    "(CAST(substr(CAST(a AS VARCHAR),1,4) AS INT)*12+CAST(substr(CAST(a AS VARCHAR),5,2) AS INT)) - "
    "(CAST(substr(CAST(b AS VARCHAR),1,4) AS INT)*12+CAST(substr(CAST(b AS VARCHAR),5,2) AS INT))",
    "CREATE OR REPLACE MACRO memory.IFNULL(a,b) AS coalesce(a,b)",
    "CREATE OR REPLACE MACRO memory.CURDATE() AS current_date",
    "CREATE OR REPLACE MACRO memory.DAYOFMONTH(d) AS extract('day' FROM CAST(d AS DATE))",
]


def _duck_tr(sql):
    """MySQL 문법 → DuckDB 문법."""
    sql = _DATEFMT.sub(lambda m: "strftime(CAST(%s AS TIMESTAMP), %s)"
                       % (m.group(1), m.group(2).replace("%i", "%M")), sql)
    sql = _TSDIFF.sub(lambda m: "date_diff('%s'," % m.group(1).lower(), sql)
    # DATEDIFF 는 DuckDB 에 3인자 내장이 있어 이름이 겹친다. 2인자만 바꾼다.
    sql = re.sub(r"\bDATEDIFF\s*\(([^,()]+),([^,()]+)\)", r"MY_DATEDIFF(\1,\2)", sql, flags=re.I)
    return sql


def _align_nulls(con):
    """NULL 정렬 순서를 시험 환경(MySQL·SQLite)에 맞춘다.

    MySQL·SQLite 는 NULL 을 '가장 작은 값' 으로 본다 → ASC 면 앞, DESC 면 뒤.
    DuckDB 기본값은 ASC 에서도 NULL 을 뒤로 보낸다. 그대로 두면
    ORDER BY 컬럼에 NULL 이 섞인 문항에서 정답(DuckDB)과 제출(SQLite)의
    행 순서가 달라져, 맞는 답이 틀렸다고 채점된다.
    """
    try:
        con.execute("SET default_null_order='nulls_first_on_asc_last_on_desc'")
    except Exception:
        pass
    return con


def duck_conn():
    con = duckdb.connect(":memory:")
    _align_nulls(con)
    con.execute("ATTACH '%s' AS p (READ_ONLY)" % DUCK.replace("'", "''"))
    for m in _MACROS:
        try:
            con.execute(m)
        except Exception:
            pass
    con.execute("SET search_path='p,memory'")
    return con


def _rows(cur_desc, data):
    return ([d[0] for d in cur_desc],
            [[None if v is None else str(v) for v in r] for r in data])


def run_duckdb(sql):
    con = duck_conn()
    try:
        cur = con.execute(_duck_tr(sql))
        return _rows(cur.description, cur.fetchall())
    finally:
        con.close()


def run_sqlite(sql):
    import sqlite3
    if not os.path.exists(SQLITE):
        raise RuntimeError("practice.sqlite 가 없습니다. python make_sqlite.py 를 먼저 실행하세요.")
    con = sqlite3.connect(SQLITE)
    try:
        cur = con.execute(sql)
        return _rows(cur.description, cur.fetchall())
    finally:
        con.close()


def run_mysql(sql):
    if not os.path.exists(CNF):
        raise RuntimeError(
            "mysql.cnf 가 없습니다. 같은 폴더에 아래 내용으로 만드세요.\n"
            "[client]\nuser=root\npassword=비밀번호\n\n"
            "그리고 데이터를 한 번 넣어야 합니다:  mysql --defaults-extra-file=mysql.cnf < seed.sql")
    p = subprocess.run(
        ["mysql", "--defaults-extra-file=" + CNF, "-D", "toss_practice",
         "--batch", "--raw", "-e", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip().splitlines()[-1][:400] if p.stderr else "MySQL 오류")
    lines = [l for l in p.stdout.splitlines() if l != ""]
    if not lines:
        return [], []
    rd = list(csv.reader(lines, delimiter="\t"))
    return rd[0], [[None if v == "NULL" else v for v in r] for r in rd[1:]]


ENGINES = {
    "duckdb": ("DuckDB", "설정 불필요 · MySQL 함수 일부 호환", run_duckdb),
    "sqlite": ("SQLite", "실제 SQLite · 정수 나눗셈 그대로", run_sqlite),
    "mysql":  ("MySQL", "실제 MySQL · mysql.cnf 필요", run_mysql),
}


def available():
    out = []
    for k, (name, desc, _) in ENGINES.items():
        ok = True
        if k == "sqlite":
            ok = os.path.exists(SQLITE)
        elif k == "mysql":
            ok = os.path.exists(CNF)
        out.append({"key": k, "name": name, "desc": desc, "ok": ok})
    return out


def run(sql, engine="duckdb"):
    if engine not in ENGINES:
        engine = "duckdb"
    return ENGINES[engine][2](sql)

# ── 추가 데이터셋을 엔진별로 만들어 쿼리를 돌린다 ────────────────────────
_SQLITE_DDL = {
    "users": "user_id INTEGER, signup_date TEXT, channel TEXT, age INTEGER, gender TEXT",
    "events": "user_id INTEGER, event_name TEXT, event_date TEXT, channel TEXT",
    "payments": "user_id INTEGER, paid_date TEXT, plan TEXT, amount INTEGER",
    "prices": "stock_code TEXT, trade_date TEXT, close_price INTEGER",
}
_DUCK_DDL = {
    "users": "user_id INTEGER, signup_date DATE, channel VARCHAR, age INTEGER, gender VARCHAR",
    "events": "user_id INTEGER, event_name VARCHAR, event_date DATE, channel VARCHAR",
    "payments": "user_id INTEGER, paid_date DATE, plan VARCHAR, amount INTEGER",
    "prices": "stock_code VARCHAR, trade_date DATE, close_price INTEGER",
}
_ALLCOLS = {
    "users": ["user_id", "signup_date", "channel", "age", "gender"],
    "events": ["user_id", "event_name", "event_date", "channel"],
    "payments": ["user_id", "paid_date", "plan", "amount"],
    "prices": ["stock_code", "trade_date", "close_price"],
}


_SQLITE_DDL.update(TX.DDL_SQLITE)
_DUCK_DDL.update(TX.DDL_DUCK)
_ALLCOLS.update(TX.COLS)


def dataset_runner(spec, engine):
    """데이터셋 하나를 엔진 위에 올리고, 쿼리를 실행하는 함수를 돌려준다.

    추가 데이터셋 검증도 사용자가 고른 엔진에서 해야 한다.
    DuckDB 에서만 돌리면 SQLite 문법으로 쓴 답이 엉뚱하게 실패한다.
    """
    if engine == "sqlite":
        import sqlite3
        con = sqlite3.connect(":memory:")
        for t, ddl in _SQLITE_DDL.items():
            con.execute("CREATE TABLE %s (%s)" % (t, ddl))
            if t in spec and spec[t][1]:
                cols, rows = spec[t]
                con.executemany("INSERT INTO %s (%s) VALUES (%s)"
                                % (t, ",".join(cols), ",".join(["?"] * len(cols))),
                                [tuple(str(v) if hasattr(v, "isoformat") else v for v in r)
                                 for r in rows])

        def _run(sql):
            cur = con.execute(sql)
            return _rows(cur.description, cur.fetchall())
        return _run, con.close

    con = duckdb.connect(":memory:")
    _align_nulls(con)
    for m in _MACROS:
        try:
            con.execute(m.replace("memory.", ""))
        except Exception:
            pass
    for t, ddl in _DUCK_DDL.items():
        con.execute("CREATE TABLE %s (%s)" % (t, ddl))
        if t in spec and spec[t][1]:
            cols, rows = spec[t]
            con.executemany("INSERT INTO %s (%s) VALUES (%s)"
                            % (t, ",".join(cols), ",".join(["?"] * len(cols))), rows)

    def _run(sql):
        cur = con.execute(_duck_tr(sql))
        return _rows(cur.description, cur.fetchall())
    return _run, con.close
