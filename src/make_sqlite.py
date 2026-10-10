# -*- coding: utf-8 -*-
"""DuckDB 연습 데이터를 SQLite 로 복제한다.

SQLite 에는 DATE 타입이 없으므로 날짜를 'YYYY-MM-DD' 문자열로 넣는다.
MySQL·테스트돔과 같은 정수 나눗셈 동작을 실제로 경험할 수 있다.
"""
import os
import sqlite3
import sys
from decimal import Decimal

import duckdb

import tables_extra as TX

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "practice.duckdb")
DST = os.path.join(HERE, "practice.sqlite")

DDL = {
    "users": """CREATE TABLE users(
        user_id INTEGER PRIMARY KEY, signup_date TEXT, channel TEXT,
        age INTEGER, gender TEXT)""",
    "events": """CREATE TABLE events(
        user_id INTEGER, event_name TEXT, event_date TEXT, channel TEXT)""",
    "payments": """CREATE TABLE payments(
        user_id INTEGER, paid_date TEXT, plan TEXT, amount INTEGER)""",
    "prices": """CREATE TABLE prices(
        stock_code TEXT, trade_date TEXT, close_price INTEGER)""",
}
COLS = {
    "users": ["user_id", "signup_date", "channel", "age", "gender"],
    "events": ["user_id", "event_name", "event_date", "channel"],
    "payments": ["user_id", "paid_date", "plan", "amount"],
    "prices": ["stock_code", "trade_date", "close_price"],
}

def _sqlval(v):
    """SQLite 는 date/datetime/Decimal 을 모른다. 문자열과 실수로 바꾼다."""
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ") if hasattr(v, "hour") else v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


if os.path.exists(DST):
    os.remove(DST)
src = duckdb.connect(SRC, read_only=True)
dst = sqlite3.connect(DST)
for t, ddl in DDL.items():
    dst.execute(ddl)
    rows = src.execute("SELECT %s FROM %s" % (", ".join(COLS[t]), t)).fetchall()
    rows = [tuple(str(v) if hasattr(v, "isoformat") else v for v in r) for r in rows]
    dst.executemany("INSERT INTO %s VALUES (%s)"
                    % (t, ",".join(["?"] * len(COLS[t]))), rows)
    print("  %-10s %6d행" % (t, len(rows)))
for t, decl in TX.DDL_SQLITE.items():
    dst.execute("CREATE TABLE %s (%s)" % (t, decl))
    rows = src.execute("SELECT %s FROM %s" % (", ".join(TX.COLS[t]), t)).fetchall()
    rows = [tuple(_sqlval(v) for v in r) for r in rows]
    dst.executemany("INSERT INTO %s VALUES (%s)"
                    % (t, ",".join(["?"] * len(TX.COLS[t]))), rows)
    print("  %-22s %6d행" % (t, len(rows)))

for ix in ["CREATE INDEX ix_e_user ON events(user_id)",
           "CREATE INDEX ix_p_user ON payments(user_id)",
           "CREATE INDEX ix_pr ON prices(stock_code, trade_date)"]:
    dst.execute(ix)
dst.commit()
dst.close()
src.close()
print("\npractice.sqlite 생성 — %.1f MB" % (os.path.getsize(DST) / 1e6))
